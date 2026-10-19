# -*- coding: utf-8 -*-
"""20/10 (K4 nel motore, D142, D143): profilo `completo` di Kraken a confidence 0,5 + soglia 0,1 % (Bracken -t 10),
scelto su L3 e confermato sulla Zymo (validazione/L3_sintetici_salumi/K4/RISULTATO_K4.md). Il profilo `rapido`
(PlusPF-8) K4 non l'ha provato: resta com'era. Soglia uguale per tutti i taxa di Kraken, nessuna regola a parte;
MetaPhlAn senza soglia (D128). Regola unica della soglia: un taxon e' mostrato se pct >= soglia ("almeno").
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_k4_kraken.py"""
import glob
import os
import re
import shutil
import subprocess
import sys

import pytest

RADICE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RADICE, "motore"))
sys.path.insert(0, os.path.join(RADICE, "steps"))
import diversita  # noqa: E402
import referto  # noqa: E402


def profili():
    with open(os.path.join(RADICE, "refs", "kraken_profili.tsv"), encoding="utf-8") as f:
        return {c[0]: c for c in (r.split("\t") for r in f.read().splitlines() if r and not r.startswith("#"))}


def test_completo_a_confidence_05_e_soglia_01():
    p = profili()
    assert p["completo"][1:4] == ["0.5", "10", "0.1"]                     # K4: 0,5 + 0,1 %, Bracken -t 10
    assert p["rapido"][1:4] == ["0.1", "10", "0.005"]                     # fuori da K4: invariato


def test_fonti_dicono_da_dove_vengono_i_valori():
    p = profili()
    assert "K4" in p["completo"][4] and "0,5" in p["completo"][4] and "0,1 %" in p["completo"][4]
    assert "Edwin" not in p["completo"][4]                                # 0,005 % non e' piu' il valore del completo
    assert "come il completo" not in p["rapido"][4] and "Edwin et al. 2024" in p["rapido"][4]


def test_soglia_inclusa_ovunque():
    """Un taxon esattamente alla soglia si mostra: referto, diversita' e confronto usano la stessa regola (>=)."""
    k = [{"nome": "Alla soglia", "categoria": "batteri", "pct": 0.1, "pct_microbi": 0.1, "letture": 10, "taxid": 1},
         {"nome": "Sotto", "categoria": "batteri", "pct": 0.09, "pct_microbi": 0.09, "letture": 9, "taxid": 2}]
    s = referto.sintesi({"metaphlan": [], "non_classificato": 0.0, "kraken": k}, 0.1)
    assert s["kraken"]["microbi"] == 1
    tab = diversita.tabella_kraken({"A": k}, 0.1, {"batteri"})
    assert tab[0]["ricchezza"] == 1 and tab[0]["letture"] == 10


def test_confronto_stessa_regola(tmp_path):
    pytest.importorskip("pandas")
    from _profiling_io import load_kraken_matrix
    m = tmp_path / "krk.tsv"
    m.write_text("taxon\tS1\tS2\nAlla soglia\t0.1\t0\nSotto\t0.09\t0\nAssente\t0\t0\n", encoding="utf-8")
    assert set(load_kraken_matrix(str(m), 0.1)) == {"alla soglia"}         # alla soglia: dentro
    assert set(load_kraken_matrix(str(m), 0.0)) == {"alla soglia", "sotto"}  # senza soglia: solo i taxa trovati


def test_kraken_riceve_solo_opzioni_che_conosce():
    """32_kraken_bracken.sh passava --gzip-compression: Kraken 2.17.2 conosce --gzip-compressed (avviso "Unknown
    option" nei log). Le opzioni dello script devono stare tutte nell'aiuto del kraken2 installato."""
    kraken2 = shutil.which("kraken2") or next(iter(sorted(glob.glob(os.path.expanduser("~/.pmn/mamba/envs/pmn_kraken/bin/kraken2"))
                                                            + glob.glob(os.path.expanduser("~/miniforge3/envs/pmn_kraken/bin/kraken2")))), None)
    if not kraken2:
        pytest.skip("kraken2 non installato qui (gira nella WSL)")
    aiuto = subprocess.run([kraken2, "--help"], capture_output=True, text=True).stdout +         subprocess.run([kraken2, "--help"], capture_output=True, text=True).stderr
    script = open(os.path.join(RADICE, "steps", "32_kraken_bracken.sh"), encoding="utf-8").read()
    blocco = script.split("k2args=(")[1].split("if [ -n")[0]
    for opzione in re.findall(r"(--[a-z][a-z-]+)", blocco):
        assert re.search(r"(?<![\w-])" + re.escape(opzione) + r"(?![\w-])", aiuto), opzione


@pytest.mark.parametrize("nc, attesa", [(0.0, " Lo 0,0 %"), (0.04, " Lo 0,0 %"), (8.1, " L'8,1 %"), (1.2, " L'1,2 %"),
                                        (11.0, " L'11,0 %"), (83.0, " L'83,0 %"), (18.0, " Il 18,0 %"),
                                        (53.7, " Il 53,7 %"), (100.0, " Il 100,0 %")])
def test_articolo_davanti_alla_percentuale(nc, attesa):
    """D3: "Il 0,0 % delle read" si scrive "Lo 0,0 %"; e "l'8,1 %", "l'11 %" (si legge otto, undici)."""
    s = referto.sintesi({"metaphlan": [("Latilactobacillus sakei", 50.0)], "non_classificato": nc, "kraken": None}, 0.1)
    assert attesa + " delle read non è assegnato a specie note." in s["metaphlan"]["frase"]
