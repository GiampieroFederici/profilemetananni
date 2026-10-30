# -*- coding: utf-8 -*-
"""MetaPhlAn senza specie nella diversita' alfa a profondita' uguale (VM B3-3, 30/10/2026).

Un profilo senza specie (read casuali: 40.000 read entrate, nessuna specie) era il campione "piu' povero": steps/42
abbassava tutti gli altri campioni alla sua profondita'. Ora non entra nel pareggio; in tabella resta con 0 (P03).
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_metaphlan_vuoto_alfa.py"""
import shutil
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
DATI = RADICE / "tests" / "dati"
ALFA = RADICE / "steps" / "42_alpha_equal_depth.py"


def cartella(tmp_path):
    """metaphlan/ con CASUALE (vero, senza specie, mapout di 40.000 read) e ERR478976 (vero, 919.979 read)."""
    m = tmp_path / "metaphlan"
    m.mkdir()
    shutil.copy(DATI / "metaphlan_casuale_profile.txt", m / "CASUALE_profile.txt")
    (m / "CASUALE.mapout").write_text("#nreads\t40000\n#avg_read_length\t150.0", encoding="utf-8")
    shutil.copy(DATI / "metaphlan_feci_ERR478976_profile.txt", m / "ERR478976_profile.txt")
    (m / "ERR478976.mapout").write_text("r1\tm1\n#nreads\t919979\n#avg_read_length\t100.0", encoding="utf-8")
    return m


def test_il_campione_vuoto_non_abbassa_la_profondita_degli_altri(tmp_path):
    m = cartella(tmp_path)
    p = subprocess.run([sys.executable, str(ALFA), "sottocampiona", "--metaphlan-dir", str(m), "--out",
                        str(tmp_path / "pari")], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "one MetaPhlAn sample" in p.stdout                     # un solo campione con specie: niente da pareggiare
    assert not (tmp_path / "pari" / "ERR478976.mapout").exists()  # prima: sottocampione di 40.000 read


def test_tabella_alfa_il_campione_vuoto_non_decide_la_profondita(tmp_path):
    """Il campione vuoto resta in tabella con 0 (P03, test_revisione_gc), ma la profondità comune è quella dei
    campioni con specie: prima ERR478976 risultava "not_equalized" alla profondità di CASUALE."""
    m = cartella(tmp_path)
    p = subprocess.run([sys.executable, str(ALFA), "calcola", "--metaphlan-dir", str(m), "--threshold-pct", "0",
                        "--out", str(tmp_path / "res")], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    righe = (tmp_path / "res" / "alpha_diversity_metaphlan.tsv").read_text().splitlines()
    assert righe[1:] == ["CASUALE\t40000\t40000\tnot_equalized\t0\t0\t0",
                         righe[2]] and righe[2].startswith("ERR478976\t919979\t919979\tfull\t81\t"), righe
