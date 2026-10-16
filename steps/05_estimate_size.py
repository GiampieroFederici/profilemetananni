#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# steps/05_estimate_size.py - estimate the download size of SRA runs BEFORE downloading.
#
# Queries the ENA filereport API for each accession and sums `fastq_bytes` (the real
# gzipped download size), then compares the total against the available disk space.
# If ENA is unreachable or does not know the run, NCBI (E-utilities, SRA runinfo) is asked
# instead: the reads are downloaded from NCBI anyway, so an ENA outage must not stop the run
# (seen on 15/10/2026: ENA answered HTTP 500 for ~6 minutes). NCBI gives the size of the .sra
# file, i.e. what prefetch downloads.
# Run this BEFORE steps/10_download_sra.sh so the user can confirm there is enough room.
# Many accessions are asked in groups (lookup_many): one ENA portal "search" request per 100 accessions,
# and one NCBI request per 100 for those ENA does not know or when ENA is down (16/10/2026: before, one
# request per accession at 0.4-12 s each).
#
# No third-party dependencies (uses only the Python standard library: urllib).
# Idempotent: results are cached on disk and re-used on the next run.
#
# Usage:
#   05_estimate_size.py --srr-list FILE --out DIR [--work-dir DIR] [--quota-free GB]
#                       [--margin 1.15] [--force]
#
# Exit codes:
#   0  proceed: the resolved accessions fit in the available/declared free space
#      (some accessions may have been skipped/unresolved — see the WARN lines + CSV)
#   2  STOP: the resolved download does NOT fit in the available/declared free space
#   3  STOP: no accession resolved because ENA and NCBI were both unreachable (retry later)
#   4  STOP: no accession resolved: the runs do not exist (check the SRR list)
#   1  usage / input error
import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# overridable only to test the fallback (an unreachable address simulates an outage)
ENA_API = os.environ.get("PMN_ENA_API", "https://www.ebi.ac.uk/ena/portal/api/filereport")
NCBI_API = os.environ.get("PMN_NCBI_API", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi")
ENA_SEARCH = os.environ.get("PMN_ENA_SEARCH", "https://www.ebi.ac.uk/ena/portal/api/search")
GROUP = 100                     # accessions per grouped request (sent with POST: no URL length limit)
ENA_FIELDS = "run_accession,read_count,base_count,fastq_bytes"
SRR_RE = re.compile(r"^(SRR|ERR|DRR)[0-9]{5,}$", re.IGNORECASE)
TIMEOUT = 30
MAX_RETRIES = 5


def http_get(url, params, post=False):
    """GET (or POST of a form) with exponential backoff; returns the body as text, or None if unreachable."""
    query = urllib.parse.urlencode(params)
    full, data = (url, query.encode("ascii")) if post else (f"{url}?{query}", None)
    backoff = 1.0
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(full, data=data, headers={"User-Agent": "profilemetananni/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                return ""   # the service answered "no such run" (NCBI: HTTP 400): not an outage
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(backoff)
            backoff *= 2
        except Exception:
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(backoff)
            backoff *= 2
    return None


def http_get_json(url, params, post=False):
    """GET a JSON body; returns parsed JSON, [] for an empty body, or None."""
    raw = http_get(url, params, post)
    if raw is None:
        return None
    try:
        return json.loads(raw) if raw.strip() else []
    except ValueError:
        return None


def lookup_srr(acc):
    """Return dict with status + fastq_bytes (sum) + read/base counts for one accession."""
    acc = acc.strip().upper()
    if not SRR_RE.match(acc):
        return {"status": "INVALID", "accession": acc, "fastq_bytes": 0, "read_count": 0, "base_count": 0}
    data = http_get_json(ENA_API, {
        "accession": acc,
        "result": "read_run",
        "fields": "run_accession,read_count,base_count,fastq_bytes",
        "format": "json",
    })
    if not data:   # ENA unreachable (None) or run unknown to ENA ([]): ask NCBI
        alt = lookup_ncbi(acc)
        if alt["status"] == "OK" or data is not None:
            return alt
        return {"status": "ERROR", "accession": acc, "fastq_bytes": 0, "read_count": 0, "base_count": 0}
    return ena_record(acc, data[0])


def ena_record(acc, d):
    """One ENA read_run row (filereport or search) -> the dict of lookup_srr."""
    def _safe_int(x):
        try:
            return int(x)                 # exact integers (no precision loss)
        except (TypeError, ValueError):
            try:
                return int(float(x))      # float-formatted counts e.g. "12.0"
            except (TypeError, ValueError):
                return 0

    # fastq_bytes may be "111;222" for paired-end -> sum the parts
    fb_raw = str(d.get("fastq_bytes", "0") or "0")
    fb = sum(int(x) for x in fb_raw.split(";") if x.isdigit())
    return {
        "status": "OK",
        "accession": acc,
        "fastq_bytes": fb,
        "read_count": _safe_int(d.get("read_count", 0) or 0),
        "base_count": _safe_int(d.get("base_count", 0) or 0),
        "source": "ENA",
    }


def lookup_ncbi(acc):
    """Same fields from NCBI SRA runinfo (XML); fastq_bytes = size of the .sra file prefetch downloads."""
    raw = http_get(NCBI_API, {"db": "sra", "id": acc, "rettype": "runinfo"})
    empty = {"accession": acc, "fastq_bytes": 0, "read_count": 0, "base_count": 0, "source": "NCBI"}
    if raw is None:
        return {"status": "ERROR", **empty}
    if not raw.strip():
        return {"status": "NOT_FOUND", **empty}
    try:
        row = ET.fromstring(raw).find("Row")
    except ET.ParseError:
        return {"status": "ERROR", **empty}
    if row is None or (row.findtext("Run") or "").upper() != acc:
        return {"status": "NOT_FOUND", **empty}
    return ncbi_record(acc, row)


def ncbi_record(acc, row):
    def num(tag):
        try:
            return int(float(row.findtext(tag) or 0))
        except ValueError:
            return 0
    return {"status": "OK", "accession": acc, "fastq_bytes": num("size_MB") * 1_000_000,
            "read_count": num("spots"), "base_count": num("bases"), "source": "NCBI"}


def lookup_ncbi_many(accs):
    """{accession: dict} from ONE NCBI runinfo request for up to GROUP accessions."""
    raw = http_get(NCBI_API, {"db": "sra", "id": ",".join(accs), "rettype": "runinfo"}, post=True)
    if raw is None:
        status = "ERROR"
    elif not raw.strip():
        status = "NOT_FOUND"
    else:
        try:
            rows = ET.fromstring(raw).findall("Row")
        except ET.ParseError:
            rows, status = None, "ERROR"
        else:
            found = {(r.findtext("Run") or "").upper(): r for r in rows}
            return {a: ncbi_record(a, found[a]) if a in found else
                    {"status": "NOT_FOUND", "accession": a, "fastq_bytes": 0, "read_count": 0, "base_count": 0,
                     "source": "NCBI"} for a in accs}
    return {a: {"status": status, "accession": a, "fastq_bytes": 0, "read_count": 0, "base_count": 0, "source": "NCBI"}
            for a in accs}


def lookup_many(accessions):
    """Same answers as lookup_srr for each accession (same order), with grouped requests: ENA first, then
    NCBI for the runs ENA does not know or when ENA is unreachable (same rules as lookup_srr)."""
    wanted = [a.strip().upper() for a in accessions]
    valid = list(dict.fromkeys(a for a in wanted if SRR_RE.match(a)))
    out, ena_down = {}, set()
    for i in range(0, len(valid), GROUP):
        group = valid[i:i + GROUP]
        data = http_get_json(ENA_SEARCH, {"result": "read_run", "includeAccessions": ",".join(group),
                                          "fields": ENA_FIELDS, "format": "json", "limit": "0"}, post=True)
        if data is None:
            ena_down.update(group)
            continue
        for d in data if isinstance(data, list) else []:
            acc = str(d.get("run_accession", "")).upper()
            if acc in group:
                out[acc] = ena_record(acc, d)
    missing = [a for a in valid if a not in out]
    for i in range(0, len(missing), GROUP):
        group = missing[i:i + GROUP]
        for acc, alt in lookup_ncbi_many(group).items():
            # as lookup_srr: when ENA was down, an NCBI "not found" is not trusted (ERROR, retried next time)
            out[acc] = alt if alt["status"] == "OK" or acc not in ena_down else {**alt, "status": "ERROR"}
    return [out.get(a) or {"status": "INVALID", "accession": a, "fastq_bytes": 0, "read_count": 0, "base_count": 0}
            for a in wanted]


def load_cache(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)  # atomic


def main():
    ap = argparse.ArgumentParser(description="Estimate SRA download size before downloading (ENA).")
    ap.add_argument("--srr-list", required=True, help="file with one SRA accession per line")
    ap.add_argument("--out", required=True, help="output directory for the report/cache")
    ap.add_argument("--work-dir", default="", help="if given, free space is read from this path's filesystem")
    ap.add_argument("--quota-free", type=float, default=None, help="declared free space in GB (used if --work-dir is absent)")
    ap.add_argument("--margin", type=float, default=1.15, help="safety multiplier for transient space (default 1.15)")
    ap.add_argument("--force", action="store_true", help="ignore cache and re-query")
    a = ap.parse_args()

    if not os.path.isfile(a.srr_list):
        print(f"[FAIL] SRR list not found: {a.srr_list}", file=sys.stderr)
        return 1

    with open(a.srr_list, encoding="utf-8") as f:
        items = []
        seen = set()
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s not in seen:
                seen.add(s)
                items.append(s)
    if not items:
        print("[FAIL] SRR list is empty", file=sys.stderr)
        return 1

    os.makedirs(a.out, exist_ok=True)
    cache_path = os.path.join(a.out, "size_cache.json")
    csv_path = os.path.join(a.out, "download_size_estimate.csv")
    cache = {} if a.force else load_cache(cache_path)

    # a network error is not an answer: ask again instead of reusing it from the cache
    todo = [x for x in items if x not in cache or cache[x].get("status") == "ERROR"]
    print(f"[INFO] {len(items)} accessions ({len(todo)} to query, {len(items) - len(todo)} cached)")

    for i in range(0, len(todo), GROUP):
        for acc, e in zip(todo[i:i + GROUP], lookup_many(todo[i:i + GROUP])):
            cache[acc] = e
            if e["status"] == "OK" and e.get("source") == "NCBI":
                print(f"[INFO] {acc}: size taken from NCBI (ENA unavailable or without this run)")
        save_cache(cache, cache_path)
        print(f"  [{min(i + GROUP, len(todo))}/{len(todo)}] -> " +
              ", ".join(f"{s} {sum(cache[a]['status'] == s for a in todo[i:i + GROUP])}" for s in ("OK", "NOT_FOUND", "ERROR")))
    save_cache(cache, cache_path)

    # Aggregate + write CSV
    # TOLERANT policy: a single unresolved/empty accession must NOT kill a whole
    # multi-sample run. Bad accessions are warned about and EXCLUDED from the size
    # sum; the disk-space gate is computed only on the successfully-resolved ones.
    total_bytes = 0
    n_ok = n_bad = 0
    bad_accessions = []   # (accession, status) of every skipped/unresolved entry
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write("accession,status,read_count,base_count,fastq_bytes,gb\n")
        for acc in items:
            e = cache.get(acc, {"status": "NOT_PROCESSED", "fastq_bytes": 0, "read_count": 0, "base_count": 0})
            gb = e.get("fastq_bytes", 0) / 1e9
            f.write(f"{acc},{e['status']},{e.get('read_count',0)},{e.get('base_count',0)},{e.get('fastq_bytes',0)},{gb:.3f}\n")
            if e["status"] == "OK" and e.get("fastq_bytes", 0) > 0:
                # resolved successfully -> counts toward the size gate
                total_bytes += e.get("fastq_bytes", 0)
                n_ok += 1
            else:
                # unresolved/empty -> warn + skip, but do NOT abort the run for it
                n_bad += 1
                bad_accessions.append((acc, e.get("status", "NOT_PROCESSED")))

    download_gb = total_bytes / 1e9
    needed_gb = download_gb * a.margin

    # Determine free space
    if a.work_dir:
        try:
            free_gb = shutil.disk_usage(a.work_dir).free / 1e9
            free_src = f"disk free at {a.work_dir}"
        except Exception:
            if a.quota_free is not None:
                free_gb = a.quota_free
                free_src = "declared (--quota-free)"
            else:
                free_gb = None
                free_src = "unknown"
    elif a.quota_free is not None:
        free_gb = a.quota_free
        free_src = "declared (--quota-free)"
    else:
        free_gb = None
        free_src = "unknown"

    print("=" * 64)
    print(f"  Accessions resolved (OK) : {n_ok}")
    print(f"  Accessions failed        : {n_bad}")
    print(f"  Estimated download       : {download_gb:.2f} GB")
    print(f"  With margin (x{a.margin:g})       : {needed_gb:.2f} GB")
    if free_gb is not None:
        print(f"  Free space ({free_src}) : {free_gb:.2f} GB")
    print(f"  CSV report               : {csv_path}")
    print("=" * 64)

    # Warn about every skipped/unresolved accession, but keep going: these are
    # excluded from the size sum and from the download — they are NOT a reason to
    # abort a whole multi-sample run (one ENA hiccup must not kill everything).
    if n_bad > 0:
        print(f"[WARN] {n_bad} accession(s) skipped (excluded from the size estimate "
              f"AND from the download) — review the CSV: {csv_path}")
        for acc, status in bad_accessions:
            print(f"  [SKIP] {acc} -> {status}")

    # Genuine error: nothing resolved means there is literally nothing to download.
    if n_ok == 0:
        if any(status == "ERROR" for _, status in bad_accessions):
            print("[FAIL] ENA and NCBI could not be reached — nothing to download. Retry in a few minutes.")
            return 3
        print("[FAIL] No accession could be resolved — the runs were not found. Check the SRR list.")
        return 4

    # The real gate: the resolved download must fit in the available space.
    if free_gb is not None and needed_gb > free_gb:
        print(f"[FAIL] Not enough space: need ~{needed_gb:.1f} GB, have {free_gb:.1f} GB.")
        return 2

    if n_bad > 0:
        print(f"[OK] {n_ok} resolved accession(s) fit in the available space "
              f"({n_bad} skipped — see above).")
    else:
        print("[OK] The estimated download fits in the available space.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
