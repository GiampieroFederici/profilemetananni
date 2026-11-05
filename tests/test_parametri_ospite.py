# -*- coding: utf-8 -*-
"""1.2 (integrazione di F1): parameters.tsv e il referto dicono come si toglie l'ospite e come si puliscono le read
(Bowtie2 very-sensitive-local, coppie strict, fastp 4:20 e almeno 70 basi). Un progetto vecchio, senza queste righe,
ha il referto di prima.
Gira con l'app:  app\\.venv\\Scripts\\python -m pytest tests/test_parametri_ospite.py"""
import os
import re
import sys

RADICE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RADICE, "motore"))

import referto  # noqa: E402

BASE = {"hosts": "sus_scrofa", "filter_human": "yes"}
NUOVI = {"host_sensitivity": "very-sensitive-local", "host_pairs": "strict",
         "trim": "fastp cut_right 4:20, length_required 70"}


def nomi(p):
    return [r[0] for r in referto.righe_parametri({"parametri": p})]


def test_run_sh_scrive_le_righe_dell_ospite():
    testo = open(os.path.join(RADICE, "bin", "run.sh"), encoding="utf-8").read()
    blocco = testo[testo.index("printf 'parameter\\tvalue\\n'"):testo.index('} > "$RES_DIR/parameters.tsv"')]
    for chiave in NUOVI:
        assert re.search(chiave + r"\\t", blocco), chiave


def test_referto_spiega_ospite_e_pulizia():
    righe = {r[0]: r for r in referto.righe_parametri({"parametri": {**BASE, **NUOVI}})}
    ospite = righe["Come si toglie l'ospite"]
    assert ospite[1] == "Bowtie2 very-sensitive-local, strict"
    assert "KneadData 0.12.5" in ospite[3]
    assert righe["Pulizia delle read"][1] == NUOVI["trim"]


def test_progetto_vecchio_senza_righe_nuove():
    assert nomi(BASE) == [n for n in nomi({**BASE, **NUOVI})
                          if n not in ("Come si toglie l'ospite", "Pulizia delle read")]
