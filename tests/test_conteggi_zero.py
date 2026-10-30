# -*- coding: utf-8 -*-
"""B4-c (VM 30/10, Casuale): con un profilo senza specie l'app scriveva "Qui tutte le 0 specie trovate." e il motore
"MetaPhlAn: 0 specie trovate.", "Kraken: 0 taxa sopra la soglia."; il referto "Taxa mostrati: 0 su N" con una tabella
vuota. Un conteggio a zero diventa una frase ("nessuna specie", "nessun taxon").
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_conteggi_zero.py"""
import re
import shutil
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "motore"))
import referto  # noqa: E402

ZERO = re.compile(r"\b0 (specie|taxa)\b")


def test_sintesi_senza_specie_ne_taxa():
    sotto = [{"nome": "Sotto la soglia", "categoria": "batteri", "pct": 0.01, "pct_microbi": 100.0, "letture": 3,
              "taxid": 1}]
    s = referto.sintesi({"metaphlan": [], "non_classificato": 100.0, "kraken": sotto}, 0.1)
    assert s["metaphlan"]["specie"] == 0 and s["kraken"]["microbi"] == 0
    assert "nessuna specie" in s["metaphlan"]["frase"] and "nessun taxon" in s["kraken"]["frase"]
    assert not ZERO.search(s["metaphlan"]["frase"] + s["kraken"]["frase"])


def test_referto_kraken_tutti_sotto_la_soglia(tmp_path):
    finto = RADICE / "installer" / "finto"
    r = tmp_path / "risultati"
    for sotto in ("metaphlan", "kraken", "tabelle"):
        (r / sotto).mkdir(parents=True)
    shutil.copy(finto / "SRR4875279_profile.txt", r / "metaphlan")
    for est in ("bracken", "k2report"):
        shutil.copy(finto / f"SRR4875279.{est}", r / "kraken")
    shutil.copy(finto / "risultati.json", r)
    par = (finto / "parameters.tsv").read_text(encoding="utf-8")
    par = re.sub(r"(?m)^(abundance_threshold_pct\t).*$", r"\g<1>99", par)   # nessun taxon arriva al 99 %
    (r / "tabelle" / "parameters.tsv").write_text(par, encoding="utf-8")
    d = referto.raccogli(r, {})
    sezione = referto.html_referto(d).split("<h2>3.")[1].split("<h2>4.")[0]
    assert "nessun taxon sopra la soglia (99,000 %)" in sezione
    assert "Taxa mostrati" not in sezione and not ZERO.search(referto.senza_html(sezione))
