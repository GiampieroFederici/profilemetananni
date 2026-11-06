# -*- coding: utf-8 -*-
"""V1 (VM 6/11): la rotella del mouse sopra un menu chiuso della pagina "Scelte dell'analisi" cambiava il valore
(confidenza 0,1 -> 0,2; read minime 10 -> 20) e la persona non se ne accorgeva: il valore finiva nel referto.
Ora la rotella fa scorrere la pagina e non tocca i menu, in tutte le pagine dell'app.
Gira con l'app:  app\\.venv\\Scripts\\python -m pytest tests/test_app_v1_rotella.py"""
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

from app.pagine import progetto, scelte, sicurezza  # noqa: E402
from app.pagine.base import Menu  # noqa: E402


def rotella(menu, scatti=-1):
    centro = QPointF(menu.rect().center())
    e = QWheelEvent(centro, QPointF(menu.mapToGlobal(menu.rect().center())), QPoint(0, 0), QPoint(0, 120 * scatti),
                    Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(menu, e)


def test_la_rotella_non_cambia_il_menu(qtbot):
    m = Menu()
    qtbot.addWidget(m)
    m.addItems(["0", "5", "10 (consigliato)", "20", "50"])
    m.setCurrentIndex(2)
    m.show()
    rotella(m, -1)                       # menu senza fuoco
    assert m.currentIndex() == 2
    m.setFocus()                         # anche dopo averlo usato (fuoco ancora lì) la rotella non lo cambia
    QApplication.processEvents()
    rotella(m, -1)
    rotella(m, -1)
    assert m.currentIndex() == 2
    assert QComboBox().focusPolicy() != m.focusPolicy() == Qt.StrongFocus


@pytest.mark.parametrize("modulo", [scelte, progetto, sicurezza])
def test_nessuna_pagina_usa_il_menu_semplice(modulo):
    testo = Path(modulo.__file__).read_text(encoding="utf-8")
    assert "QComboBox()" not in testo and "Menu()" in testo
    assert issubclass(Menu, QComboBox)
