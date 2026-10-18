# -*- coding: utf-8 -*-
"""Lingua IT/EN (sessione del 18/10/2026): con l'italiano, app, messaggi del motore e referto restano IDENTICI.

La fotografia tests/dati/lingua_it.json è stata fatta sul codice di f567f8e, prima della lingua
(python tests/lingua_foto.py --scrivi): qui si rifà e si confronta, caso per caso.
Gira con l'ambiente dell'app su Windows:  app\\.venv\\Scripts\\python -m pytest tests/test_lingua.py"""
import difflib
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lingua_foto  # noqa: E402


def differenze(attesa, adesso):
    out = []
    for caso in sorted(set(attesa) | set(adesso)):
        if attesa.get(caso) != adesso.get(caso):
            out.append(f"--- {caso}")
            out += list(difflib.unified_diff(attesa.get(caso, []), adesso.get(caso, []), lineterm="", n=1))[2:40]
    return "\n".join(out)


def test_italiano_identico_a_prima(qapp):
    attesa = json.loads(lingua_foto.FOTO_IT.read_text(encoding="utf-8"))
    adesso = lingua_foto.foto()
    assert adesso == attesa, differenze(attesa, adesso)
