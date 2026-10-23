# -*- coding: utf-8 -*-
"""18/10 (B1): la soglia di abbondanza (0,005 %, Edwin 2024) vale SOLO per Kraken. MetaPhlAn non ha nessuna soglia:
sintesi, referto (HTML ed Excel), report di confronto e diversita' mostrano tutte le specie che MetaPhlAn trova.
Nei testi per le persone si scrive "taxa", non "microbi".
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_soglia_solo_kraken.py"""
import os
import re
import subprocess
import sys

import pytest

RADICE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RADICE, "motore"))
import referto  # noqa: E402

RARA = "k__Bacteria|p__Firmicutes|c__Bacilli|o__Lactobacillales|f__Lactobacillaceae|g__Pediococcus|s__Pediococcus_rarus"
MICROBI = re.compile(r"\bmicrob[oi]\b", re.I)


def campione():
    k = [{"nome": "Latilactobacillus sakei", "categoria": "batteri", "pct": 50.0, "pct_microbi": 99.99, "letture": 9,
          "taxid": 1},
         {"nome": "Kraken rarus", "categoria": "batteri", "pct": 0.001, "pct_microbi": 0.01, "letture": 1, "taxid": 2}]
    return {"metaphlan": [("Latilactobacillus sakei", 50.0), ("Pediococcus rarus", 0.001)], "non_classificato": 10.0,
            "kraken": k}


def test_sintesi_metaphlan_senza_soglia_kraken_con_soglia():
    s = referto.sintesi(campione(), 0.005)
    assert s["metaphlan"]["specie"] == 2                                          # anche la specie allo 0,001 %
    assert "Pediococcus rarus" in [x["nome"] for x in s["metaphlan"]["dominanti"]]
    assert s["metaphlan"]["frase"].startswith("MetaPhlAn: 2 specie trovate") and "soglia" not in s["metaphlan"]["frase"]
    assert s["kraken"]["microbi"] == 1                                            # Kraken: solo sopra 0,005 %
    assert s["kraken"]["frase"].startswith("Kraken: 1 taxa sopra la soglia")
    assert not MICROBI.search(s["metaphlan"]["frase"] + s["kraken"]["frase"])


def test_referto_mostra_metaphlan_sotto_0005(tmp_path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_referto import fai_referto, prepara, righe
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("PySide6.QtGui")
    p = prepara(tmp_path)
    prof = p / "risultati" / "metaphlan" / "SRR4875279_profile.txt"
    prof.write_text(prof.read_text(encoding="utf-8") + f"{RARA}\t2|1239|91061|186826|33958|1253|99999\t0.001\t\n",
                    encoding="utf-8")
    fai_referto(p)
    html = (p / "risultati" / "referto" / "referto.html").read_text(encoding="utf-8")
    sezione_mpa = html.split("<h2>2. Specie trovate con MetaPhlAn</h2>")[1].split("<h2>3.")[0]
    assert "Pediococcus rarus" in sezione_mpa and "soglia" not in sezione_mpa
    assert "28 specie trovate" in html                                            # 27 + la rara
    assert not MICROBI.search(html)
    wb = openpyxl.load_workbook(p / "risultati" / "referto" / "referto.xlsx")
    mpa = righe(wb["MetaPhlAn_specie"])
    assert "Pediococcus rarus" in {r["Specie"] for r in mpa} and "Sopra soglia" not in mpa[0]
    assert "Kraken_taxa" in wb.sheetnames and "Sopra soglia" in righe(wb["Kraken_taxa"])[0]


def test_confronto_tiene_tutte_le_specie_metaphlan(tmp_path):
    pytest.importorskip("openpyxl")
    pd = pytest.importorskip("pandas")
    m = tmp_path / "mpa.tsv"
    m.write_text("clade_name\tS1\nUNCLASSIFIED\t50\n" + f"{RARA}\t0.001\n"
                 "k__Bacteria|p__F|c__B|o__L|f__L|g__Latilactobacillus|s__Latilactobacillus_sakei\t49.999\n", encoding="utf-8")
    out = tmp_path / "rep.xlsx"
    r = subprocess.run([sys.executable, os.path.join(RADICE, "steps", "40_compare_report.py"), "--metaphlan", str(m),
                        "--out", str(out), "--threshold-pct", "0.005"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    riepilogo = dict(pd.read_excel(out, sheet_name="summary").values)
    assert riepilogo["species_metaphlan"] == 2


def test_diversita_metaphlan_senza_soglia():
    righe = [r for r in open(os.path.join(RADICE, "bin", "run.sh"), encoding="utf-8") if "41_diversity.R" in r]
    mpa = [r for r in righe if "div_mpa" in r]
    krk = [r for r in righe if "div_krk" in r]
    assert len(mpa) == 1 and "--min-abundance 0 " in mpa[0]                      # MetaPhlAn: nessuna soglia
    # Kraken (22/10): la matrice dei soli taxa del prodotto, già filtrata con la soglia del profilo dal passo 33
    assert len(krk) == 1 and '--matrix "$RES_DIR/kraken_matrix_taxa.tsv"' in krk[0] and "--min-abundance 0 " in krk[0]
    k33 = [r for r in open(os.path.join(RADICE, "bin", "run.sh"), encoding="utf-8") if "--taxa-out" in r]
    assert len(k33) == 1 and '--threshold-pct "$PMN_THRESHOLD"' in k33[0]
