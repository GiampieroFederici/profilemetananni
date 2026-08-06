# -*- coding: utf-8 -*-
# steps/_biomni_core.py - pure logic for Phase C (taxa dossier). No Biomni import here,
# so the whole module is testable offline and at zero cost.
# Conda env: pmn_reports_py (pandas, via _profiling_io). Not meant to be run directly.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _profiling_io import load_metaphlan_species, load_kraken_matrix  # noqa: E402

LABELS = ("noto", "assente", "atteso", "ipotesi")
CATEGORIES = ("ruolo", "batteriocine", "ammine_biogene", "cazymes", "resistoma", "virulenza")


def _display(normalized: str) -> str:
    """Turn a normalized name ('latilactobacillus sakei') into a display name."""
    return normalized[:1].upper() + normalized[1:] if normalized else normalized


def select_taxa(metaphlan_path: str, kraken_path: str, threshold_pct: float, max_taxa: int):
    """Return [(display_name, detected_by)] above threshold, capped at max_taxa.

    detected_by is 'metaphlan', 'kraken' or 'metaphlan+kraken'. Ordering is by descending
    max abundance across the tools, then alphabetical, so the cap keeps the most abundant.
    """
    mpa = load_metaphlan_species(metaphlan_path, threshold_pct) if metaphlan_path else {}
    krk = load_kraken_matrix(kraken_path, threshold_pct) if kraken_path else {}
    rows = []
    for name in set(mpa) | set(krk):
        if name in mpa and name in krk:
            src = "metaphlan+kraken"
        elif name in mpa:
            src = "metaphlan"
        else:
            src = "kraken"
        rows.append((_display(name), src, max(mpa.get(name, 0.0), krk.get(name, 0.0))))
    rows.sort(key=lambda r: (-r[2], r[0]))
    return [(name, src) for name, src, _ in rows[:max_taxa]]
