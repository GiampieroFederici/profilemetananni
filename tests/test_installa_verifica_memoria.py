# -*- coding: utf-8 -*-
"""B3-4 (VM 30/10, 8 GB): "Controlla il motore" was a generic RED (bowtie2 killed, 137) and the Motore page proposed
"Installa o completa", which does not help. With RAM_INSUFFICIENTE the page says it in plain words and keeps
"Controlla il motore". Against the fake engine, with the app environment on Windows:
  app\\.venv\\Scripts\\python -m pytest tests/test_installa_verifica_memoria.py"""
import pytest

pytest.importorskip("pytestqt")
from test_app_s5b import ambiente, f, premi, scenario, scritte  # noqa: E402,F401  (fixtures and helpers of S5b)

from app.pagine import motore as pagina_motore  # noqa: E402


def test_ram_insufficiente_non_e_da_installare():
    assert "RAM_INSUFFICIENTE" not in pagina_motore.DA_INSTALLARE


def test_verifica_senza_memoria_non_propone_installa(qtbot, f, monkeypatch):
    scenario(monkeypatch, "RAM_INSUFFICIENTE")
    f.vai("motore")
    assert f.principale.text() == "Controlla il motore"
    premi(f)
    m = f.pagine["motore"]
    qtbot.waitUntil(lambda: "memoria non basta" in scritte(m), timeout=30000)
    assert "ROSSO: La prova si è fermata perché la memoria non basta" in scritte(m)
    assert "non serve reinstallarlo" in scritte(m)
    assert f.principale.text() == "Controlla il motore" and not m.da_installare
