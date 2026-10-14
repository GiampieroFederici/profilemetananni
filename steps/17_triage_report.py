#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# steps/17_triage_report.py - turn the per-sample triage metrics into one table with a
# score and a SUGGESTED decision (pass / review / exclude) per sample.
# Conda env: pmn_reports_py (standard library only).
#
# Inputs (written by 15_triage_qc.sh and 16_triage_host.sh into --in DIR):
#   <sample>.triage_reads.txt   total fragments (reads, or read pairs) in the full input
#   <sample>.triage_qc.json     fastp JSON on the first N fragments
#   <sample>.triage_host.tsv    "tested<TAB>N" and "nonhost<TAB>M" from Bowtie2 on the first N
#
# Three fixed rules, each turned into a sub-score in [0,1] with a grey zone of +/-20% around
# its threshold (exactly at the threshold = 0.5). The sample score is the WEAKEST sub-score:
#   score >= 0.75 -> pass   |   0.25 <= score < 0.75 -> review   |   score < 0.25 -> exclude
# The decision is only a suggestion: run.sh skips "exclude" samples only if the user set
# triage.action: skip.
#
# Usage: 17_triage_report.py --in DIR --out TRIAGE.tsv [--max-host-pct 95]
#          [--min-nonhost-reads 1000000] [--min-q30-pct 70] [--lang en|it]
import argparse
import glob
import json
import os
import sys

GREY = 0.2  # half-width of the grey zone, relative to the threshold

COLUMNS = ["sample", "total_fragments", "tested_fragments", "pass_rate_pct", "q30_pct",
           "dup_pct", "host_pct", "est_nonhost_fragments", "score", "decision", "reasons"]

MSG = {
    "en": {"host": "host {v:.1f}% (max {t:g}%)",
           "reads": "~{v:,.0f} non-host fragments (min {t:,.0f})",
           "q30": "Q30 {v:.1f}% (min {t:g}%)",
           "missing": "missing triage metrics: {v}"},
    "it": {"host": "host {v:.1f}% (max {t:g}%)",
           "reads": "~{v:,.0f} frammenti non-host (min {t:,.0f})",
           "q30": "Q30 {v:.1f}% (min {t:g}%)",
           "missing": "metriche di triage mancanti: {v}"},
}


def ramp(value, threshold, grey=GREY):
    """Sub-score for a 'value must be >= threshold' rule: 0.5 at the threshold,
    1 at threshold*(1+grey) or above, 0 at threshold*(1-grey) or below."""
    if threshold <= 0:
        return 1.0
    return min(1.0, max(0.0, 0.5 + (value / threshold - 1.0) / (2.0 * grey)))


def decide(score):
    if score >= 0.75:
        return "pass"
    if score >= 0.25:
        return "review"
    return "exclude"


def read_metrics(indir, sample):
    """Return a dict of raw metrics for one sample, or raise ValueError naming what is missing."""
    base = os.path.join(indir, sample)
    missing = [suf for suf in (".triage_reads.txt", ".triage_qc.json", ".triage_host.tsv")
               if not os.path.isfile(base + suf)]
    if missing:
        raise ValueError(", ".join(missing))
    with open(base + ".triage_reads.txt", encoding="utf-8") as f:
        total = int(f.read().strip())
    with open(base + ".triage_qc.json", encoding="utf-8") as f:
        qc = json.load(f)
    before = qc["summary"]["before_filtering"]
    passed = qc["filtering_result"]["passed_filter_reads"]
    host = {}
    with open(base + ".triage_host.tsv", encoding="utf-8") as f:
        for line in f:
            k, _, v = line.strip().partition("\t")
            if k:
                host[k] = int(v)
    return {
        "total": total,
        "pass_rate": passed / before["total_reads"] if before["total_reads"] else 0.0,
        "q30": before["q30_rate"] * 100.0,
        "dup": qc.get("duplication", {}).get("rate", 0.0) * 100.0,
        "tested": host["tested"],
        "nonhost": host["nonhost"],
    }


def evaluate(m, max_host_pct, min_nonhost_reads, min_q30_pct, lang="en"):
    """Score one sample from its raw metrics. Returns the output row as a dict."""
    t = MSG[lang]
    nonhost_frac = m["nonhost"] / m["tested"] if m["tested"] else 0.0
    host_pct = 100.0 * (1.0 - nonhost_frac)
    est_nonhost = m["total"] * m["pass_rate"] * nonhost_frac
    rules = [
        # (sub-score, message) ; host is written as "non-host share must be >= 100 - max_host"
        (ramp(100.0 - host_pct, 100.0 - max_host_pct), t["host"].format(v=host_pct, t=max_host_pct)),
        (ramp(est_nonhost, min_nonhost_reads), t["reads"].format(v=est_nonhost, t=min_nonhost_reads)),
        (ramp(m["q30"], min_q30_pct), t["q30"].format(v=m["q30"], t=min_q30_pct)),
    ]
    score = min(s for s, _ in rules)
    return {
        "sample": m.get("sample", ""),
        "total_fragments": m["total"],
        "tested_fragments": m["tested"],
        "pass_rate_pct": round(100.0 * m["pass_rate"], 2),
        "q30_pct": round(m["q30"], 2),
        "dup_pct": round(m["dup"], 2),
        "host_pct": round(host_pct, 2),
        "est_nonhost_fragments": int(round(est_nonhost)),
        "score": round(score, 3),
        "decision": decide(score),
        # only the rules that are not clearly passed explain the decision
        "reasons": "; ".join(msg for s, msg in rules if s < 0.75),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Score per-sample triage metrics.")
    ap.add_argument("--in", dest="indir", required=True, help="directory with *.triage_* files")
    ap.add_argument("--out", required=True, help="output TSV")
    ap.add_argument("--max-host-pct", type=float, default=95.0)
    ap.add_argument("--min-nonhost-reads", type=float, default=1_000_000)
    ap.add_argument("--min-q30-pct", type=float, default=70.0)
    ap.add_argument("--lang", choices=["en", "it"], default="en")
    a = ap.parse_args()

    if not 0 <= a.max_host_pct < 100:
        sys.exit("--max-host-pct must be in [0, 100)")
    if not os.path.isdir(a.indir):
        sys.exit(f"input directory not found: {a.indir}")
    samples = sorted({os.path.basename(p).split(".triage_")[0]
                      for p in glob.glob(os.path.join(a.indir, "*.triage_*"))})
    if not samples:
        sys.exit(f"no triage files in {a.indir}")

    rows = []
    for s in samples:
        try:
            m = read_metrics(a.indir, s)
        except ValueError as e:
            rows.append({c: "" for c in COLUMNS} | {
                "sample": s, "decision": "review",
                "reasons": MSG[a.lang]["missing"].format(v=e)})
            continue
        except (KeyError, json.JSONDecodeError, OSError) as e:
            sys.exit(f"unreadable triage metrics for {s}: {e}")
        m["sample"] = s
        rows.append(evaluate(m, a.max_host_pct, a.min_nonhost_reads, a.min_q30_pct, a.lang))

    out_abs = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    with open(out_abs, "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(COLUMNS) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]) for c in COLUMNS) + "\n")

    counts = {d: sum(r["decision"] == d for r in rows) for d in ("pass", "review", "exclude")}
    print(f"[OK] triage: {counts['pass']} pass, {counts['review']} review, "
          f"{counts['exclude']} exclude -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
