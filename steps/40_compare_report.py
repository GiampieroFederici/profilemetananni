#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# steps/40_compare_report.py - compare MetaPhlAn vs Kraken2/Bracken and write an overview report.
# Conda env: pmn_reports_py (pandas, openpyxl).
#
# Produces one Excel workbook with:
#   - "summary"  : counts + overlap metrics (shared / only-MetaPhlAn / only-Kraken / Jaccard)
#   - "all_taxa" : every species, which method detected it, and its max abundance per method
#
# Usage:
#   40_compare_report.py [--metaphlan MERGED.txt] [--kraken MATRIX.tsv] --out REPORT.xlsx
#                        [--threshold-pct 0.001]
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _profiling_io import load_metaphlan_species, load_kraken_matrix  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare MetaPhlAn vs Kraken and write an overview report.")
    ap.add_argument("--metaphlan", default="", help="merged MetaPhlAn table (optional)")
    ap.add_argument("--kraken", default="", help="Kraken/Bracken matrix TSV (optional)")
    ap.add_argument("--out", required=True, help="output .xlsx")
    ap.add_argument("--threshold-pct", type=float, default=0.001, help="abundance threshold in %% (default 0.001)")
    a = ap.parse_args()

    if not a.metaphlan and not a.kraken:
        print("[FAIL] provide at least one of --metaphlan / --kraken", file=sys.stderr)
        return 1

    mpa = load_metaphlan_species(a.metaphlan, a.threshold_pct) if a.metaphlan else {}
    krk = load_kraken_matrix(a.kraken, a.threshold_pct) if a.kraken else {}

    sm, sk = set(mpa), set(krk)
    shared = sm & sk
    only_m = sm - sk
    only_k = sk - sm
    union = sm | sk
    jaccard = (len(shared) / len(union)) if union else 0.0

    summary = pd.DataFrame(
        [
            ("threshold_pct", a.threshold_pct),
            ("species_metaphlan", len(sm)),
            ("species_kraken", len(sk)),
            ("shared", len(shared)),
            ("only_metaphlan", len(only_m)),
            ("only_kraken", len(only_k)),
            ("union", len(union)),
            ("jaccard", round(jaccard, 4)),
            ("metaphlan_confirmed_by_kraken_pct", round(100 * len(shared) / len(sm), 1) if sm else 0.0),
            ("kraken_confirmed_by_metaphlan_pct", round(100 * len(shared) / len(sk), 1) if sk else 0.0),
        ],
        columns=["metric", "value"],
    )

    taxa_rows = []
    for t in sorted(union):
        taxa_rows.append(
            {
                "species": t,
                "in_metaphlan": int(t in mpa),
                "in_kraken": int(t in krk),
                "max_pct_metaphlan": round(mpa.get(t, 0.0), 4),
                "max_pct_kraken": round(krk.get(t, 0.0), 4),
                "detected_by": "both" if (t in mpa and t in krk) else ("metaphlan" if t in mpa else "kraken"),
            }
        )
    all_taxa = pd.DataFrame(
        taxa_rows,
        columns=["species", "in_metaphlan", "in_kraken", "max_pct_metaphlan", "max_pct_kraken", "detected_by"],
    )
    if not taxa_rows:
        print("[WARN] no taxa above the threshold in either method", file=sys.stderr)

    out_abs = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    with pd.ExcelWriter(out_abs, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="summary", index=False)
        all_taxa.to_excel(xw, sheet_name="all_taxa", index=False)

    print(f"[OK] report -> {a.out}")
    print(f"     MetaPhlAn={len(sm)}  Kraken={len(sk)}  shared={len(shared)}  Jaccard={jaccard:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
