# -*- coding: utf-8 -*-
"""R15, comandi da tastiera: su ogni pagina il tasto Tab raggiunge tutti i comandi visibili, nell'ordine in cui
si leggono (testata, percorso, pagina, barra con il principale per ultimo); Invio preme il pulsante che ha il
fuoco; le frecce cambiano scelta fra le schede. Contro il finto motore, progetti e TEMP in tmp_path.
Gira con l'ambiente dell'app su Windows:  app\\.venv\\Scripts\\python -m pytest tests/test_app_tastiera.py"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (QAbstractButton, QComboBox, QLineEdit, QPlainTextEdit, QScrollArea,  # noqa: E402
                               QTabBar, QTextBrowser, QWidget)

from app import finestra, main, progetto  # noqa: E402

COMANDI = (QAbstractButton, QLineEdit, QComboBox, QPlainTextEdit, QTabBar, QTextBrowser)
PAGINE = ["home", "campioni", "scelte", "esecuzione", "risultati", "sicurezza", "motore", "crediti"]


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("PMN_MOTORE", "finto")
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    (tmp_path / "temp").mkdir()
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("TMP", str(tmp_path / "temp"))
    monkeypatch.setattr(progetto, "cartella_progetti", lambda: tmp_path / "progetti")


@pytest.fixture
def f(qtbot, qapp):
    main.prepara(qapp)
    w = finestra.Finestra(movimento=False)
    qtbot.addWidget(w)
    w.show()
    w.fuori.setCurrentIndex(1)
    return w


def con_risultati(f, qtbot, tmp_path):
    """Un progetto con l'analisi finita (finto motore), così Risultati e Sicurezza hanno tutti i comandi."""
    p = progetto.nuovo("prova", tmp_path / "progetti")
    p.scrivi({"project_name": "prova", "motore": {"metaphlan_modo": "fette", "kraken_db": "completo"},
              "app": {"prodotto": "maiale", "scelte": True}})
    f.contesto.progetto = p
    f.contesto.avvia_analisi = True
    f.vai("esecuzione")
    qtbot.waitUntil(lambda: f.pagine["esecuzione"].stato == "ok", timeout=60000)
    return p


def tab(f, indietro=False):
    QTest.keyClick(f.focusWidget(), Qt.Key_Tab, Qt.ShiftModifier if indietro else Qt.NoModifier)
    return f.focusWidget()


def giro(f):
    """Le fermate del Tab in un giro completo, a partire dalla prima della testata; finisce quando il giro si
    chiude (con il principale acceso, è l'ultima fermata)."""
    f.zona_testata.findChildren(QAbstractButton)[0].setFocus()
    tab(f, indietro=True)
    visti = []
    for _ in range(200):
        w = tab(f)
        if w in visti:
            assert w is visti[0], "il Tab torna indietro a metà giro"
            return visti
        visti.append(w)
    raise AssertionError("il Tab non chiude il giro")


@pytest.mark.parametrize("chiave", PAGINE)
def test_tab_raggiunge_tutto_in_ordine(f, qtbot, tmp_path, chiave):
    con_risultati(f, qtbot, tmp_path)
    f.vai(chiave)
    qtbot.wait(300)                              # la stima di Scelte e la verifica di Motore arrivano dal motore
    fermate = giro(f)
    comandi = [w for w in f.findChildren(QWidget) if isinstance(w, COMANDI) and w.isVisible() and w.isEnabled()
               and w.focusPolicy() & Qt.TabFocus]
    assert [w for w in comandi if w not in fermate] == []                 # nessun comando irraggiungibile
    assert len(fermate) == len(set(fermate))                               # nessuno due volte
    zone = [f.zona_testata, f.zona_percorso, f.pila.currentWidget(), f.zona_barra]
    ordine = [next(i for i, z in enumerate(zone) if z is w or z.isAncestorOf(w)) for w in fermate]
    assert ordine == sorted(ordine)                                        # testata, percorso, pagina, barra
    if f.principale.isEnabled():
        assert fermate[-1] is f.principale                                 # il principale per ultimo (R1)
    assert isinstance(fermate[ordine.index(2)], QScrollArea)               # l'area che scorre, con il contorno
    fermate[1].setFocus()
    assert tab(f, indietro=True) is fermate[0] and tab(f, indietro=True) is fermate[-1]     # Maiusc+Tab


def test_ordine_di_lettura_con_comandi_comparsi_dopo(f, qtbot, tmp_path):
    """L'elenco dei progetti (creato dopo) viene prima del campo del nome; i secondari prima del principale."""
    con_risultati(f, qtbot, tmp_path)
    f.vai("home")
    qtbot.wait(100)                               # Qt mostra l'elenco al giro dopo del ciclo degli eventi
    fermate = giro(f)
    apri = next(i for i, w in enumerate(fermate) if w.objectName() == "apri")
    assert apri < fermate.index(f.pagine["home"].nome)
    f.vai("motore")
    qtbot.wait(300)
    fermate = giro(f)
    assert [w.text() for w in fermate[-2:]] == ["Installa o completa", "Controlla il motore"]


def test_invio_preme_il_pulsante_col_fuoco(f, qtbot, tmp_path):
    con_risultati(f, qtbot, tmp_path)
    f.vai("risultati")
    f.passi["campioni"][0].setFocus()
    QTest.keyClick(f.focusWidget(), Qt.Key_Return)
    assert f.attuale == "campioni"
    f.pagine["campioni"].testo_codici.setPlainText("SRR4875279")
    f.principale.setFocus()                       # "Avanti: scelte dell'analisi"
    QTest.keyClick(f.focusWidget(), Qt.Key_Enter)
    assert f.attuale == "scelte"


def test_frecce_fra_le_schede_e_tab_fuori_dal_testo(f, qtbot, tmp_path):
    con_risultati(f, qtbot, tmp_path)
    f.vai("campioni")
    c = f.pagine["campioni"]
    c.scelta_ncbi.pulsante.setChecked(True)
    c.scelta_ncbi.pulsante.setFocus()
    QTest.keyClick(c.scelta_ncbi.pulsante, Qt.Key_Left)
    assert c.scelta_pc.pulsante.isChecked() and c.zona_pc.isVisible()
    QTest.keyClick(c.scelta_pc.pulsante, Qt.Key_Right)
    assert c.scelta_ncbi.pulsante.isChecked()
    c.testo_codici.setFocus()                     # nel riquadro dei codici Tab esce, non scrive una tabulazione
    tab(f)
    assert f.focusWidget() is c.prodotto and "\t" not in c.testo_codici.toPlainText()
