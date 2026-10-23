#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# steps/33_kraken_matrix.py - build a species x sample relative-abundance matrix from Bracken outputs.
# Conda env: pmn_reports_py (pandas).
#
# Usage: 33_kraken_matrix.py --in DIR --out MATRIX.tsv [--value percent|fraction]
#                             [--taxa-out MATRIX_TAXA.tsv --threshold-pct P]
# --taxa-out (22/10): the same taxa as the Kraken profile of the report (D023, D128): only bacteria, archaea and fungi
# (tree of <sample>.k2report next to the .bracken), cells below P % of the total assigned set to 0. Used for the
# Kraken beta diversity, so Homo, Leishmania and viruses never enter it.
import argparse
import glob
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "motore"))
import referto  # noqa: E402  (categorie_kraken, MICROBI: one rule for report and diversity)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a species x sample matrix from Bracken outputs.")
    ap.add_argument("--in", dest="indir", required=True, help="directory with *.bracken files")
    ap.add_argument("--out", dest="out", required=True, help="output TSV (taxa x samples)")
    ap.add_argument("--value", choices=["percent", "fraction"], default="percent")
    ap.add_argument("--taxa-out", help="output TSV with the product taxa only (bacteria, archaea, fungi)")
    ap.add_argument("--threshold-pct", type=float, default=0.0, help="Kraken abundance threshold in %% (with --taxa-out)")
    a = ap.parse_args()

    if not os.path.isdir(a.indir):
        sys.exit(f"input directory not found: {a.indir}")
    files = sorted(glob.glob(os.path.join(a.indir, "*.bracken")))
    if not files:
        sys.exit(f"no *.bracken files in {a.indir}")

    columns, prodotto = {}, {}
    for f in files:
        sample = os.path.basename(f)[: -len(".bracken")]
        try:
            df = pd.read_csv(f, sep="\t")
        except pd.errors.EmptyDataError:
            print(f"[WARN] empty Bracken file, skipping: {f}", file=sys.stderr)
            continue
        if "name" not in df.columns or "new_est_reads" not in df.columns:
            sys.exit(f"unexpected Bracken format (missing columns) in: {f}")
        # fraction from the integer reads: fraction_total_reads has 5 decimals (steps of 0.001 %), so a taxon at
        # 0.00455 % was written 0.00005 and passed the 0.005 % threshold (P29)
        reads = df.set_index("name")["new_est_reads"].astype(float)
        if reads.sum() <= 0:
            print(f"[WARN] no reads in Bracken file, skipping: {f}", file=sys.stderr)
            continue
        series = reads / reads.sum()
        if a.taxa_out:
            rep = f[: -len(".bracken")] + ".k2report"
            cat = referto.categorie_kraken(rep) if os.path.isfile(rep) else {}
            tieni = df["taxonomy_id"].astype(str).map(lambda t: cat.get(t, "altro") in referto.MICROBI).to_numpy()
            sopra = (series * 100.0 >= a.threshold_pct).to_numpy()
            p = series[tieni & sopra] * (100.0 if a.value == "percent" else 1.0)
            prodotto[sample] = p.groupby(level=0).sum()
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
    matrix.to_csv(out_abs, sep="\t", float_format="%.10g")   # 6 decimals rounded 0.0049998 up to the threshold
    print(f"[OK] matrix {matrix.shape[0]} taxa x {matrix.shape[1]} samples -> {a.out}")
    if a.taxa_out:
        taxa = pd.DataFrame(prodotto, columns=list(columns)).fillna(0.0)
        taxa.index.name = "species"
        taxa.sort_index().to_csv(os.path.abspath(a.taxa_out), sep="\t",float_format="%.10g")
        print(f"[OK] product taxa {taxa.shape[0]} x {taxa.shape[1]} samples -> {a.taxa_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
