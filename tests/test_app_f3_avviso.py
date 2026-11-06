# -*- coding: utf-8 -*-
"""F3 (PMN 1.2, L6): la pagina delle scelte dice che cosa si rifà quando le scelte cambiano dopo l'analisi.
La soglia di Kraken non entra nei timbri di bin/run.sh (tabelle e referto in pochi secondi); confidence, read minime,
lunghezza delle read e database rifanno Kraken; ospiti e uomo rifanno ospite, MetaPhlAn e Kraken.
Gira con l'ambiente dell'app su Windows:  app\\.venv\\Scripts\\python -m pytest tests/test_app_f3_avviso.py"""
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
sys.path.insert(0, str(RADICE / "tests"))

from app.pagine import scelte  # noqa: E402
from test_app_s5b import ambiente, aspetta_stima, f, scritte, vai_alle_scelte  # noqa: E402,F401

# i parametri come li scrive results/parameters.tsv (progetto_2026-11-01_2, 4/11)
FATTI = {"metaphlan_mode": "fette", "kraken_profile": "completo", "kraken_confidence": "0.5", "bracken_min_reads": "10",
         "bracken_readlen": "150", "abundance_threshold_pct": "0.1", "hosts": "sus_scrofa", "filter_human": "yes"}
UGUALI = {"hosts": ["sus_scrofa"], "filter_human": "yes", "kraken_profile": "completo", "kraken_confidence": "0.5",
          "bracken_min_reads": "10", "bracken_readlen": 150, "abundance_threshold_pct": "0.1"}


@pytest.mark.parametrize("cambio, atteso", [
    ({}, None),
    ({"abundance_threshold_pct": "0.01"}, "soglia"),
    ({"kraken_confidence": "0.3"}, "kraken"),
    ({"bracken_min_reads": "50", "abundance_threshold_pct": "0.01"}, "kraken"),
    ({"bracken_readlen": 250}, "kraken"),
    ({"kraken_profile": "rapido"}, "kraken"),
    ({"hosts": ["bos_taurus"]}, "ospite"),
    ({"filter_human": "no", "kraken_confidence": "0.3"}, "ospite"),
])
def test_che_cosa_si_rifa(cambio, atteso):
    assert scelte.da_rifare(FATTI, {**UGUALI, **cambio}) == atteso


def test_solo_metaphlan_le_scelte_di_kraken_non_contano():
    solo_mpa = {k: v for k, v in FATTI.items() if not k.startswith(("kraken", "bracken", "abundance"))}
    assert scelte.da_rifare(solo_mpa, {**UGUALI, "kraken_confidence": "0.3"}) is None


def test_tempi_dell_avviso():
    tempi = {"download": 600, "pulizia": 60, "ospite": 1200, "metaphlan": 600, "kraken": 1500, "riepilogo": 30,
             "referto": 30}
    titolo, testo = scelte.avviso_da_rifare("soglia", tempi)
    assert "soglia" in titolo and "pochi secondi" in testo
    assert "circa 26 minuti" in scelte.avviso_da_rifare("kraken", tempi)[1]            # Kraken + tabelle + referto
    assert "circa 57 minuti" in scelte.avviso_da_rifare("ospite", tempi)[1]            # tutto meno il download
    for cosa in ("soglia", "kraken", "ospite"):
        t = " ".join(scelte.avviso_da_rifare(cosa, tempi))
        assert "—" not in t and "microbi" not in t and ", e " not in t


def test_pagina_avvisa_con_risultati_fatti_con_altre_scelte(qtbot, f):
    s = vai_alle_scelte(qtbot, f)
    assert "dopo l'analisi" not in scritte(s)                                          # niente risultati: niente avviso
    p = f.contesto.progetto
    p.risultati.mkdir(parents=True, exist_ok=True)
    (p.risultati / "risultati.json").write_text(json.dumps({"parametri": {**FATTI, "kraken_confidence": "0.3"}}),
                                                encoding="utf-8")
    s._avvia_stima()
    aspetta_stima(qtbot, f)
    assert "Hai cambiato le scelte di Kraken dopo l'analisi" in scritte(s)
    assert "si rifà Kraken su tutti i campioni" in scritte(s)
    (p.risultati / "risultati.json").write_text(json.dumps({"parametri": FATTI}), encoding="utf-8")
    s._avvia_stima()
    aspetta_stima(qtbot, f)
    assert "dopo l'analisi" not in scritte(s)                                          # stesse scelte: niente avviso
