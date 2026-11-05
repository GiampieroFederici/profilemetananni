# -*- coding: utf-8 -*-
"""5/11 (F2, PMN 1.2): la soglia di abbondanza di Kraken consigliata (0,1 %) e' giustificata dalla letteratura dove
l'utente la vede, e le citazioni sono giuste.

- Portik, Brown & Pierce-Ward 2022, BMC Bioinformatics 23:541, doi:10.1186/s12859-022-05103-0: 0,1 % delle read
  totali con Kraken 2, Bracken e PlusPF (testo completo su PMC9749362).
- Edwin et al. 2024, Environ Microbiome 19:19, doi:10.1186/s40793-024-00561-w: raccomandazione finale 0,001 % (suolo),
  non 0,005 % (abstract su PubMed 38549112).
- Galanis et al. 2022, Mol Ecol Resour 22(7):2506-2523, doi:10.1111/1755-0998.13626: la "threshold of 0.5" e' la
  confidence di Kraken 2 (testo completo della versione bioRxiv 10.1101/2021.06.09.447678, §2.7.2 e §3.2).
- La percentuale di ProfileMetaNanni e' calcolata sulle read che Bracken assegna a una specie (motore/referto.py,
  leggi_kraken), quella di Portik sulle read totali: il testo lo dice.
Gira con l'app:  app\\.venv\\Scripts\\python -m pytest tests/test_f2_soglia_fonti.py"""
import json
import os
import re
import sys

import pytest

RADICE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RADICE)
sys.path.insert(0, os.path.join(RADICE, "motore"))

PORTIK_DOI = "10.1186/s12859-022-05103-0"
EDWIN_DOI = "10.1186/s40793-024-00561-w"
GALANIS_DOI = "10.1111/1755-0998.13626"


def leggi(*parti):
    with open(os.path.join(RADICE, *parti), encoding="utf-8") as f:
        return f.read()


def profili():
    return {c[0]: c for c in (r.split("\t") for r in leggi("refs", "kraken_profili.tsv").splitlines()
                              if r and not r.startswith("#"))}


def citazioni_motore():
    import pmn_motore
    return pmn_motore.CITAZIONI["kraken"]


def fonti_crediti():
    pytest.importorskip("PySide6.QtGui")
    from app.pagine import crediti
    return [v for _t, voci in crediti.FONTI for v in voci]


def scelte():
    pytest.importorskip("PySide6.QtWidgets")
    from app.pagine import scelte as s
    return s


def stile(testo):
    """Regole dei testi: niente trattini lunghi o medi, nessuna virgola prima di "e", "taxa" mai "microbi"."""
    assert "—" not in testo and "–" not in testo, testo
    assert not re.search(r", e\b", testo), testo
    assert "microbi" not in testo, testo


# ---------------- 1. accanto al menu della soglia ----------------
def test_menu_soglia_giustifica_lo_0_1_con_portik_e_la_taratura():
    t = scelte().FONTE_SOGLIA
    assert "Vale solo per Kraken: MetaPhlAn non ha soglia" in t        # inizio invariato (test_revisione_g2)
    assert "Consigliato 0,1 %" in t and "Portik" in t and "2022" in t and "PlusPF" in t
    assert "meno di 15" in t and "Zymo" in t                         # frase chiave di Portik + nostra taratura
    assert "suolo" in t and "Edwin et al. 2024" in t and "0,001 %" in t and "falsi positivi" in t
    stile(t)


def test_menu_soglia_dice_su_che_cosa_si_calcola():
    t = scelte().FONTE_SOGLIA
    assert "read che Bracken assegna a una specie" in t and "read totali" in t


def test_menu_confidence_cita_galanis():
    t = scelte().FONTE_CONFIDENZA
    assert "Galanis et al. 2022" in t and "0,5" in t and "Wright, Comeau e Langille 2023" in t
    stile(t)


# ---------------- 2. citazioni: Edwin con 0,001 %, Portik e Galanis aggiunti ----------------
@pytest.mark.parametrize("fonte", ["crediti", "motore"])
def test_citazioni_edwin_portik_galanis(fonte):
    voci = fonti_crediti() if fonte == "crediti" else citazioni_motore()
    edwin = [v for v in voci if EDWIN_DOI in v]
    assert len(edwin) == 1 and "0,001 %" in edwin[0] and "0,005" not in edwin[0]
    portik = [v for v in voci if PORTIK_DOI in v]
    assert len(portik) == 1 and portik[0].startswith("Portik, Brown & Pierce-Ward 2022, BMC Bioinformatics 23:541")
    galanis = [v for v in voci if GALANIS_DOI in v]
    assert len(galanis) == 1 and galanis[0].startswith("Galanis et al. 2022, Mol Ecol Resour 22(7):2506-2523")
    for v in edwin + portik + galanis:
        stile(v)


def test_profili_kraken_fonti():
    p = profili()
    assert p["completo"][1:4] == ["0.5", "10", "0.1"] and p["rapido"][1:4] == ["0.1", "10", "0.005"]  # valori uguali
    assert "Portik, Brown & Pierce-Ward 2022" in p["completo"][4] and "Galanis et al. 2022" in p["completo"][4]
    assert "Edwin et al. 2024" in p["rapido"][4] and "0,001 %" in p["rapido"][4]
    assert "soglia 0,005 % da Edwin" not in p["rapido"][4]            # Edwin non consiglia 0,005 %
    for c in (p["completo"][4], p["rapido"][4]):
        stile(c)


# ---------------- 3. referto ----------------
def test_referto_limite_e_parametro_dicono_fonte_e_base():
    import referto
    assert "Portik, Brown e Pierce-Ward 2022" in referto.LIMITE_KRAKEN and "read totali" in referto.LIMITE_KRAKEN
    stile(referto.LIMITE_KRAKEN)
    assert "delle read assegnate da Bracken un taxon di Kraken" in leggi("motore", "referto.py")


# ---------------- 4. README, inglese poi italiano ----------------
def test_readme_cita_le_fonti_della_soglia():
    r = leggi("README.md")
    en, it = r.split("## How to cite", 1)[1].split("##", 1)[0], r.split("## Come citare", 1)[1].split("##", 1)[0]
    for sezione in (en, it):
        assert "Portik" in sezione and "Galanis" in sezione and "Edwin" in sezione
    assert "0.001 %" in en and "0,001 %" in it and "0.1 %" in en and "0,1 %" in it
    stile(it)


# ---------------- 5. inglese nei due cataloghi ----------------
def test_testi_nuovi_tradotti():
    app = json.loads(leggi("app", "risorse", "lingua_en.json"))
    motore = json.loads(leggi("motore", "lingua_en.json"))
    s = scelte()
    nuove = lambda voci: [v for v in voci if PORTIK_DOI in v or GALANIS_DOI in v or EDWIN_DOI in v]  # noqa: E731
    for t in (s.FONTE_SOGLIA, s.FONTE_CONFIDENZA, *nuove(fonti_crediti())):
        assert t in app, t
        assert "—" not in app[t] and "0,1" not in app[t]           # inglese: punto decimale
    import referto
    for t in [*nuove(citazioni_motore()), referto.LIMITE_KRAKEN, profili()["completo"][4], profili()["rapido"][4]]:
        assert t in motore, t
        assert "—" not in motore[t]
