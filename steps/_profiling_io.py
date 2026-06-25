# -*- coding: utf-8 -*-
# steps/_profiling_io.py - shared loaders for profiling tables (imported by other steps).
# Conda env: pmn_reports_py (pandas). Not meant to be run directly.
import re

import pandas as pd

# Minimal synonym map for genera reclassified in 2020 (Zheng et al. 2020): MetaPhlAn may
# still use the old 'Lactobacillus' name while Kraken/NCBI use the new genus. Keys/values
# are in the normalized (lowercase, space-separated, de-punctuated) form.
_SYNONYMS = {
    "lactobacillus sakei": "latilactobacillus sakei",
    "lactobacillus curvatus": "latilactobacillus curvatus",
    "lactobacillus plantarum": "lactiplantibacillus plantarum",
    "lactobacillus brevis": "levilactobacillus brevis",
    "lactobacillus fermentum": "limosilactobacillus fermentum",
    "lactobacillus reuteri": "limosilactobacillus reuteri",
    "lactobacillus casei": "lacticaseibacillus casei",
    "lactobacillus paracasei": "lacticaseibacillus paracasei",
    "lactobacillus rhamnosus": "lacticaseibacillus rhamnosus",
}


def normalize(name: str) -> str:
    """Normalize a taxon name for cross-tool matching."""
    n = str(name).strip().lower()
    n = re.sub(r"[._\-]", " ", n)        # underscores / periods / hyphens -> space
    n = re.sub(r"\bgroup\b", " ", n)     # drop ' group' suffix used by some DBs
    n = re.sub(r"\bsp\b\.?", " ", n)     # drop 'sp.' / 'sp'
    n = re.sub(r"\s+", " ", n).strip()
    return _SYNONYMS.get(n, n)


def read_metaphlan_table(path):
    """Return (header_list, data_rows) for a merged MetaPhlAn table.

    Comment lines are skipped; the header is the line whose first field (minus a leading
    '#') equals 'clade_name'. Falls back to the first non-comment line if not found.
    """
    header = None
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            f0 = parts[0].lstrip("#").strip().lower()
            if header is None:
                if f0 == "clade_name":
                    header = [parts[0].lstrip("#").strip()] + parts[1:]
                    continue
                if line.startswith("#"):
                    continue
                header = parts
                continue
            rows.append(parts)
    return header, rows


def load_metaphlan_species(path: str, threshold_pct: float = 0.0) -> dict:
    """Return {normalized_species: max_relative_abundance_pct} from a merged MetaPhlAn table."""
    header, rows = read_metaphlan_table(path)
    if not header or not rows:
        return {}
    df = pd.DataFrame(rows, columns=header)
    clade_col = header[0]
    sample_cols = header[1:]
    out: dict = {}
    for _, r in df.iterrows():
        clade = str(r[clade_col])
        if "s__" in clade and "t__" not in clade:
            sp = clade.split("s__")[-1]
            vals = pd.to_numeric(r[sample_cols], errors="coerce").fillna(0.0)
            mx = float(vals.max()) if len(vals) else 0.0
            if mx > threshold_pct:
                key = normalize(sp)
                out[key] = max(out.get(key, 0.0), mx)
    return out


def load_kraken_matrix(path: str, threshold_pct: float = 0.0) -> dict:
    """Return {normalized_species: max_relative_abundance_pct} from a Kraken/Bracken matrix TSV.

    Duplicate-row-label safe: reads the whole frame and reduces with max(axis=1).
    """
    df = pd.read_csv(path, sep="\t", index_col=0)
    num = df.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    mx = num.max(axis=1)
    out: dict = {}
    for name, val in mx.items():
        v = float(val)
        if v > threshold_pct:
            key = normalize(name)
            out[key] = max(out.get(key, 0.0), v)
    return out
