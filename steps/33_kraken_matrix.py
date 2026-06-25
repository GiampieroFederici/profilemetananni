#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# steps/33_kraken_matrix.py - build a species x sample relative-abundance matrix from Bracken outputs.
# Conda env: pmn_reports_py (pandas).
#
# Usage: 33_kraken_matrix.py --in DIR --out MATRIX.tsv [--value percent|fraction]
import argparse
import glob
import os
import sys

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a species x sample matrix from Bracken outputs.")
    ap.add_argument("--in", dest="indir", required=True, help="directory with *.bracken files")
    ap.add_argument("--out", dest="out", required=True, help="output TSV (taxa x samples)")
    ap.add_argument("--value", choices=["percent", "fraction"], default="percent")
    a = ap.parse_args()

    if not os.path.isdir(a.indir):
        sys.exit(f"input directory not found: {a.indir}")
    files = sorted(glob.glob(os.path.join(a.indir, "*.bracken")))
    if not files:
        sys.exit(f"no *.bracken files in {a.indir}")

    columns = {}
    for f in files:
        sample = os.path.basename(f)[: -len(".bracken")]
        try:
            df = pd.read_csv(f, sep="\t")
        except pd.errors.EmptyDataError:
            print(f"[WARN] empty Bracken file, skipping: {f}", file=sys.stderr)
            continue
        if "name" not in df.columns or "fraction_total_reads" not in df.columns:
            sys.exit(f"unexpected Bracken format (missing columns) in: {f}")
        series = df.set_index("name")["fraction_total_reads"].astype(float)
        if a.value == "percent":
            series = series * 100.0
        # collapse possible duplicate taxon names by summing
        series = series.groupby(level=0).sum()
        columns[sample] = series

    matrix = pd.DataFrame(columns).fillna(0.0)
    matrix.index.name = "species"
    matrix = matrix.sort_index()

    if matrix.shape[1] == 0:
        print("[FAIL] no usable Bracken samples (all files empty/invalid)", file=sys.stderr)
        return 2

    out_abs = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    matrix.to_csv(out_abs, sep="\t", float_format="%.6f")
    print(f"[OK] matrix {matrix.shape[0]} taxa x {matrix.shape[1]} samples -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
