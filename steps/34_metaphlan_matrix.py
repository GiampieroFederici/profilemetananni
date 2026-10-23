#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# steps/34_metaphlan_matrix.py - extract a species x samples matrix from a merged MetaPhlAn table.
# Conda env: pmn_reports_py (pandas). Feeds the diversity script (41_diversity.R).
#
# Species rows only (s__ and not t__); the UNCLASSIFIED pseudo-row is dropped and each
# sample is re-normalized to 100% over detected species, so the matrix is like-for-like
# with Kraken for diversity/comparison even when --unclassified_estimation was used.
#
# Usage: 34_metaphlan_matrix.py --in MERGED.txt --out MATRIX.tsv
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _profiling_io import read_metaphlan_table  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Species x samples matrix from a merged MetaPhlAn table.")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    a = ap.parse_args()

    if not os.path.isfile(a.inp):
        sys.exit(f"input not found: {a.inp}")

    header, rows = read_metaphlan_table(a.inp)
    if not header or not rows:
        sys.exit("empty or malformed MetaPhlAn table")

    df = pd.DataFrame(rows, columns=header)
    clade_col = header[0]
    sample_cols = header[1:]

    mask = df[clade_col].str.contains("s__", na=False) & ~df[clade_col].str.contains("t__", na=False)
    keep = df[mask].copy()
    if keep.empty:
        sys.exit("no species-level rows (s__) found in the MetaPhlAn table")
    keep["species"] = keep[clade_col].str.split("s__").str[-1]
    mat = keep[["species"] + sample_cols].set_index("species")
    mat = mat.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    mat = mat.groupby(level=0).sum().sort_index()

    # re-normalize each sample column to 100% over detected species
    colsum = mat.sum(axis=0).replace(0, 1.0)
    mat = mat.divide(colsum, axis=1) * 100.0

    out_abs = os.path.abspath(a.out)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    mat.to_csv(out_abs, sep="\t")
    print(f"[OK] MetaPhlAn matrix {mat.shape[0]} species x {mat.shape[1]} samples -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
