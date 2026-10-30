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


# ---------------- B4-1: pagina Risultati a 830 px con 6 campioni e la tabella dei metadati ----------------
def test_risultati_stretti_sei_campioni(stile, f, qtbot, tmp_path):
    sys.path.insert(0, str(RADICE / "tests"))
    import json
    from test_multicampione import progetto_referto
    cartella = progetto_referto(tmp_path, metadati=True)
    risultati = cartella / "risultati" / "risultati.json"
    d = json.loads(risultati.read_text(encoding="utf-8"))
    d["campioni"] = d["campioni"][:6]                          # come Multi_B2 sulla VM: 6 campioni
    risultati.write_text(json.dumps(d), encoding="utf-8")
    f.contesto.progetto = progetto.Progetto(cartella)
    misura(f, qtbot, 830)
    f.vai("risultati")
    qtbot.wait(200)
    pagina = f.pagine["risultati"]
    assert pagina.tabella_meta.rowCount() == 6
    s = f.pila.currentWidget()
    larghi = sorted(((w.minimumSizeHint().width(), type(w).__name__, str(getattr(w, "text", lambda: "")())[:40])
                     for w in pagina.findChildren(QPushButton) + pagina.findChildren(QLabel)
                     if not w.isHidden()), reverse=True)[:5]
    assert s.widget().minimumSizeHint().width() <= s.viewport().width(), larghi
    assert f.width() <= 830 and tagliati(f.zona_testata) == []


# ---------------- B4-c (VM con aed57f0): finestra a 830 px con la scala di Windows al 125 % ----------------
# 830 px veri = circa 655 px per l'app. Il progetto ha le frasi e le barre vere delle specie (installer/finto).
def progetto_sei_campioni(tmp_path):
    sys.path.insert(0, str(RADICE / "tests"))
    import json
    from test_multicampione import progetto_referto
    cartella = progetto_referto(tmp_path, metadati=True)
    risultati = cartella / "risultati" / "risultati.json"
    d = json.loads(risultati.read_text(encoding="utf-8"))
    vero = json.loads((RADICE / "installer" / "finto" / "risultati.json").read_text(encoding="utf-8"))
    d["campioni"] = d["campioni"][:6]
    for c in d["campioni"]:
        c["sintesi"] = vero["campioni"][0]["sintesi"]
    d["citazioni"] = vero["citazioni"]
    risultati.write_text(json.dumps(d), encoding="utf-8")
    return progetto.Progetto(cartella)


@pytest.mark.parametrize("larghezza", [655, 819, 1024])
def test_b4c_campioni_e_risultati_stretti(stile, f, qtbot, tmp_path, larghezza):
    """B4-1: Risultati (barre fisse da 380 px: 743 px) e Campioni (tendine e riga dell'ospite: 559 px) uscivano a destra."""
    f.contesto.progetto = progetto_sei_campioni(tmp_path)
    misura(f, qtbot, larghezza)
    for pagina in ("campioni", "risultati"):
        f.vai(pagina)
        qtbot.wait(200)
        s = f.pila.currentWidget()
        assert s.widget().minimumSizeHint().width() <= s.viewport().width(), (pagina, larghezza)


@pytest.mark.parametrize("larghezza", [655, 1024])
def test_b4c_voce_selezionata_intera(stile, f, qtbot, larghezza):
    """B4-1: nella colonna stretta la voce selezionata (in grassetto) si tagliava: "Campioni e prodott"."""
    from PySide6.QtGui import QFontMetrics
    f.contesto.progetto = nuovo("progetto_b4c")
    misura(f, qtbot, larghezza)
    for pagina in ("campioni", "scelte", "esecuzione", "risultati", "sicurezza"):
        f.vai(pagina)
        qtbot.waitUntil(lambda: not f.occupato(), timeout=30000)
        qtbot.wait(100)
        b = f.passi[pagina][0]
        assert b.font().bold()
        assert QFontMetrics(b.font()).horizontalAdvance(b.text()) + 20 <= b.width(), (pagina, b.text(), b.width())


@pytest.mark.parametrize("larghezza", [655, 819, 1024])
def test_b4c_pulsanti_del_referto_non_sotto_le_schede(stile, f, qtbot, larghezza):
    """B4-7a: i pulsanti del referto andati a capo finivano sotto la barra delle schede MetaPhlAn/Kraken (Casuale)."""
    import json
    from PySide6.QtCore import QPoint, QRect
    p = nuovo("Casuale")
    r = p.risultati
    (r / "qc").mkdir(parents=True)
    for nome in ("referto.html", "referto.pdf", "tabelle.xlsx", "qc/multiqc_report.html"):
        (r / nome).write_text("x", encoding="utf-8")
    (r / "risultati.json").write_text(json.dumps({
        "motore": "1.1.0", "campioni": [{"nome": "CASUALE", "esito": "ok", "sintesi": {}}],
        "referto": {"html": "referto.html", "pdf": "referto.pdf", "xlsx": "tabelle.xlsx"},
        "qc": {"multiqc": "qc/multiqc_report.html"},
        "consigli": [{"codice": "KRAKEN_VUOTO", "messaggio": "Kraken non ha trovato taxa sopra la soglia."},
                     {"codice": "METAPHLAN_VUOTO", "messaggio": "MetaPhlAn non ha trovato specie."}]}),
        encoding="utf-8")
    f.contesto.progetto = p
    misura(f, qtbot, larghezza)
    f.vai("risultati")
    qtbot.wait(300)
    pag = f.pagine["risultati"]
    schede = QRect(pag.linguette.mapTo(pag, QPoint(0, 0)), pag.linguette.size())
    sotto = [b.text() for b in pag.findChildren(QPushButton)
             if b.isVisible() and QRect(b.mapTo(pag, QPoint(0, 0)), b.size()).intersects(schede)]
    assert sotto == [], (larghezza, sotto)


def test_b4c_errore_della_verifica_in_vista(stile, f, qtbot):
    """B4-9: a 8 GB il ROSSO della memoria stava in fondo alla pagina Motore e non si vedeva senza scorrere (il VERDE
    sì, B2 P7)."""
    from PySide6.QtCore import QCoreApplication, QPoint
    misura(f, qtbot, 655)
    f.vai("motore")
    m = f.pagine["motore"]
    scorre = f.pila.currentWidget()
    m.errore_corsa = {"codice": "RAM_INSUFFICIENTE", "messaggio": "La prova si è fermata perché la memoria non basta.",
                      "cosa_fare": "Chiudi gli altri programmi e riprova."}
    m._esito("verifica", {"esito": "errore"})
    esito = m.zona_esito.itemAt(m.zona_esito.count() - 1).widget()
    qtbot.wait(300)
    QCoreApplication.processEvents()
    y, alto = esito.mapTo(scorre.viewport(), QPoint(0, 0)).y(), scorre.viewport().height()
    assert 0 <= y and y + min(esito.height(), alto) <= alto, (y, esito.height(), alto)
