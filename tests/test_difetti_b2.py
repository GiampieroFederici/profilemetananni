# -*- coding: utf-8 -*-
"""Difetti dell'app trovati sulla VM (prove B2 del 30/10/2026, zip fcc6d09). Gira con l'ambiente dell'app su Windows:
  app\\.venv\\Scripts\\python -m pytest tests/test_difetti_b2.py
B2-2a  il referto diceva "motore profilemetananni 0.1.0": la versione viene da un solo file, motore/VERSIONE.
B2-13  i registri citati con percorsi Linux (/home/pmn/...) che da Windows non si aprono.
B2-2b  a circa 830 px testata e pagine tagliate a destra: la testata va su due righe, le pagine si stringono.
B2-3   "Cerca aggiornamenti" spento durante un'analisi non sembrava spento.
B2-11a "Prima di partire" con il testo della stima precedente sotto quella nuova."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("pytestqt")
RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtWidgets import QLabel, QPushButton  # noqa: E402

from app import aggiorna, finestra, motore, progetto  # noqa: E402
from app.pagine import esecuzione  # noqa: E402


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("PMN_MOTORE", "finto")
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    (tmp_path / "temp").mkdir()
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("TMP", str(tmp_path / "temp"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "locale"))
    monkeypatch.setattr(progetto, "cartella_progetti", lambda: tmp_path / "progetti")
    monkeypatch.setattr(finestra, "AVVIO_MIN_MS", 0)


@pytest.fixture
def f(qtbot):
    w = finestra.Finestra(movimento=False)
    qtbot.addWidget(w)
    w.show()
    w.avvia()
    qtbot.waitUntil(lambda: w.attuale == "home", timeout=30000)
    return w


def nuovo(nome):
    p = progetto.nuovo(nome)
    p.scrivi(progetto.base(p.nome))
    return p


# ---------------- B2-2a: una sola versione ----------------
def test_versione_da_un_solo_file():
    sys.path.insert(0, str(RADICE / "motore"))
    import pmn_motore
    scritta = (RADICE / "motore" / "VERSIONE").read_text(encoding="utf-8").strip()
    assert scritta == "1.1.0" and pmn_motore.VERSIONE == scritta and aggiorna.VERSIONE == scritta


# ---------------- B2-13: percorsi del motore come si aprono da Windows ----------------
@pytest.mark.parametrize("linux, windows", [
    ("Manda a noi il file /home/pmn/.pmn/log/pmn_x_esegui.log.",
     r"Manda a noi il file \\wsl.localhost\pmn\home\pmn\.pmn\log\pmn_x_esegui.log."),
    ("/home/pmn/.pmn/log/a.log", r"\\wsl.localhost\pmn\home\pmn\.pmn\log\a.log"),
    ("Risultati in /mnt/c/Users/Ana/Documents/ProfileMetaNanni/p1/risultati, apri la cartella",
     r"Risultati in C:\Users\Ana\Documents\ProfileMetaNanni\p1\risultati, apri la cartella"),
    ("niente percorsi qui", "niente percorsi qui"),
])
def test_percorsi_per_windows(linux, windows):
    assert motore.percorso_windows(linux) == windows


def test_eventi_del_motore_vero_con_percorsi_windows(qtbot, monkeypatch):
    monkeypatch.delenv("PMN_MOTORE")
    c = motore.MotoreClient()
    visti = []
    c.evento.connect(visti.append)
    c._riga(b'{"tipo": "inizio", "corsa": "x", "log": "/home/pmn/.pmn/log/pmn_x.log"}')
    c._riga('{"tipo": "errore", "messaggio": "Si è fermato.", "cosa_fare": "Manda a noi il file '
            '/home/pmn/.pmn/log/pmn_x.log."}'.encode())
    assert visti[0]["log"] == r"\\wsl.localhost\pmn\home\pmn\.pmn\log\pmn_x.log"
    assert visti[1]["cosa_fare"].endswith(r"\\wsl.localhost\pmn\home\pmn\.pmn\log\pmn_x.log.")


def test_apri_il_registro(f, qtbot, monkeypatch, tmp_path):
    aperti = []
    monkeypatch.setattr(esecuzione.QDesktopServices, "openUrl", lambda u: aperti.append(u) or True)
    pagina = f.pagine["esecuzione"]
    pagina._evento({"tipo": "inizio", "corsa": "x", "log": str(tmp_path / "pmn_x.log")})
    assert pagina.apri_registro.isHidden()                         # nascosto finché i dettagli sono chiusi
    pagina.dettagli.setChecked(True)
    assert not pagina.apri_registro.isHidden()
    pagina.apri_registro.click()
    assert aperti == [QUrl.fromLocalFile(str(tmp_path / "pmn_x.log"))]


# ---------------- B2-2b: finestra stretta ----------------
@pytest.fixture
def stile(qapp):
    """Lo stile vero dell'app (caratteri e spaziature cambiano le larghezze); poi si toglie per gli altri test."""
    from app import main
    main.prepara(qapp)
    yield
    qapp.setStyleSheet("")


def misura(f, qtbot, larghezza):
    f.setMinimumSize(0, 0)                                    # la VM aveva lo schermo piccolo
    f.resize(larghezza, 640)
    qtbot.wait(200)


def tagliati(zona):
    return [(w.text(), w.width(), w.sizeHint().width()) for tipo in (QPushButton, QLabel)
            for w in zona.findChildren(tipo) if w.isVisible() and w.width() < w.sizeHint().width() - 1]


def test_finestra_stretta_niente_tagliato(stile, f, qtbot):
    f.contesto.progetto = nuovo("progetto_2026-10-30")
    misura(f, qtbot, 830)
    assert f.width() <= 830                                   # prima la testata la teneva a 1336 px
    assert tagliati(f.zona_testata) == []
    for pagina in ("home", "campioni", "scelte", "motore", "crediti", "sicurezza", "risultati", "esecuzione"):
        f.vai(pagina)
        qtbot.waitUntil(lambda: not f.occupato(), timeout=30000)
        qtbot.wait(100)
        s = f.pila.currentWidget()
        assert s.widget().minimumSizeHint().width() <= s.viewport().width(), pagina   # il testo va a capo
    assert tagliati(f.zona_testata) == []


def test_finestra_larga_come_prima(stile, f, qtbot):
    misura(f, qtbot, 1366)
    assert f.testata_una_riga and f.zona_percorso.width() == 306 and tagliati(f.zona_testata) == []


# ---------------- B2-3: pulsante spento che si vede spento ----------------
def colore_sfondo(pulsante):
    img = pulsante.grab().toImage()
    return img.pixelColor(6, img.height() // 2).name()


def test_secondario_spento_si_vede(qtbot):
    stile = (RADICE / "app" / "stile.qss").read_text(encoding="utf-8")
    b = QPushButton("Cerca aggiornamenti", objectName="secondario")
    b.setStyleSheet(stile)
    qtbot.addWidget(b)
    b.show()
    acceso = colore_sfondo(b)
    b.setEnabled(False)
    assert colore_sfondo(b) != acceso


# ---------------- B2-11a: una sola stima in "Prima di partire" ----------------
def test_prima_di_partire_una_sola_stima(f, qtbot):
    pagina = f.pagine["scelte"]
    for nome in ("vite_mosto", "secondo_progetto"):
        f.contesto.progetto = nuovo(nome)
        f.vai("scelte")
        qtbot.waitUntil(lambda: not pagina.client.in_corso(), timeout=30000)
        qtbot.waitUntil(lambda: any(lab.text() == "Tempo stimato" for lab in pagina.stima.findChildren(QLabel)),
                        timeout=30000)
    qtbot.wait(300)
    visibili = [(lab.text()[:30], lab.geometry().getRect()) for lab in pagina.stima.findChildren(QLabel)
                if not lab.isHidden()]
    testi = [t for t, _r in visibili]
    assert testi.count("Campioni") == 1 and testi.count("Tempo stimato") == 1, " | ".join(map(str, visibili))
