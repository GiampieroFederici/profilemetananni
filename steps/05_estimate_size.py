#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# steps/05_estimate_size.py - estimate the download size of SRA runs BEFORE downloading.
#
# Queries the ENA filereport API for each accession and sums `fastq_bytes` (the real
# gzipped download size), then compares the total against the available disk space.
# Run this BEFORE steps/10_download_sra.sh so the user can confirm there is enough room.
#
# No third-party dependencies (uses only the Python standard library: urllib).
# Idempotent: results are cached on disk and re-used on the next run.
#
# Usage:
#   05_estimate_size.py --srr-list FILE --out DIR [--work-dir DIR] [--quota-free GB]
#                       [--margin 1.15] [--force]
#
# Exit codes:
#   0  estimated download fits in the available/declared free space
#   2  estimated download does NOT fit (or some accessions could not be resolved)
#   1  usage / input error
import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request

ENA_API = "https://www.ebi.ac.uk/ena/portal/api/filereport"
SRR_RE = re.compile(r"^(SRR|ERR|DRR)[0-9]{5,}$", re.IGNORECASE)
TIMEOUT = 30
MAX_RETRIES = 5


def http_get_json(url, params):
    """GET with exponential backoff; returns parsed JSON or None."""
    query = urllib.parse.urlencode(params)
    full = f"{url}?{query}"
    backoff = 1.0
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "profilemetananni/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                raw = resp.read().decode("utf-8", "replace")
            return json.loads(raw) if raw.strip() else []
        except Exception:
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(backoff)
            backoff *= 2
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
    if data is None:
        return {"status": "ERROR", "accession": acc, "fastq_bytes": 0, "read_count": 0, "base_count": 0}
    if not data:
        return {"status": "NOT_FOUND", "accession": acc, "fastq_bytes": 0, "read_count": 0, "base_count": 0}
    d = data[0]

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
    }


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

    todo = [x for x in items if x not in cache]
    print(f"[INFO] {len(items)} accessions ({len(todo)} to query, {len(items) - len(todo)} cached)")

    for i, acc in enumerate(todo, 1):
        cache[acc] = lookup_srr(acc)
        if i % 20 == 0 or i == len(todo):
            save_cache(cache, cache_path)
            print(f"  [{i}/{len(todo)}] last: {acc} -> {cache[acc]['status']}")
        time.sleep(0.12)
    save_cache(cache, cache_path)

    # Aggregate + write CSV
    total_bytes = 0
    n_ok = n_bad = 0
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.write("accession,status,read_count,base_count,fastq_bytes,gb\n")
        for acc in items:
            e = cache.get(acc, {"status": "NOT_PROCESSED", "fastq_bytes": 0, "read_count": 0, "base_count": 0})
            gb = e.get("fastq_bytes", 0) / 1e9
            f.write(f"{acc},{e['status']},{e.get('read_count',0)},{e.get('base_count',0)},{e.get('fastq_bytes',0)},{gb:.3f}\n")
            if e["status"] == "OK" and e.get("fastq_bytes", 0) > 0:
                total_bytes += e.get("fastq_bytes", 0)
                n_ok += 1
            else:
                n_bad += 1

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

    if n_bad > 0:
        print(f"[WARN] {n_bad} accession(s) could not be resolved — review the CSV before downloading.")
    if free_gb is not None and needed_gb > free_gb:
        print(f"[FAIL] Not enough space: need ~{needed_gb:.1f} GB, have {free_gb:.1f} GB.")
        return 2
    if n_bad > 0:
        return 2
    print("[OK] The estimated download fits in the available space.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
