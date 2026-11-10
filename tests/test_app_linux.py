# -*- coding: utf-8 -*-
"""L'app su Ubuntu nativo (1.3): il motore gira nello stesso Linux dell'app, senza wsl.exe e senza tradurre i percorsi.
Linux si simula cambiando sys.platform: i test girano anche su Windows e non toccano il sistema vero (nessun motore
lanciato, nessuna WSL, nessun file aperto davvero, bash mai chiamato: su Windows potrebbe essere quello della WSL).
  app\\.venv\\Scripts\\python -m pytest tests/test_app_linux.py"""
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from PySide6.QtCore import QUrl  # noqa: E402
from PySide6.QtNetwork import QNetworkReply  # noqa: E402
from PySide6.QtWidgets import QLabel  # noqa: E402

from app import aggiorna, lingua, main, motore, progetto  # noqa: E402
from app.pagine import esecuzione, home, risultati  # noqa: E402
from app.pagine import motore as pagina_motore  # noqa: E402
from app.pagine.base import Contesto  # noqa: E402

INSTALLA = RADICE / "installer" / "linux" / "installa_pmn.sh"
NON_AVVIATO = {"codice": "MOTORE_NON_AVVIATO"}


@pytest.fixture
def linux(monkeypatch, tmp_path):
    """Ubuntu nativo simulato, con il motore vero (non il finto) in una PMN_HOME di prova. Torna la cartella di prova."""
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("PMN_MOTORE", raising=False)
    monkeypatch.setenv("PMN_HOME", str(tmp_path / "pmn"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "locale"))
    monkeypatch.setattr(progetto, "cartella_progetti", lambda: tmp_path / "progetti")
    return tmp_path


def scritte(w):
    return "\n".join(e.text() for e in w.findChildren(QLabel))


# ---------------- il motore: comando, percorsi, testi ----------------
def test_il_motore_si_lancia_direttamente(linux, monkeypatch):
    programma, opzioni = motore.comando_motore()
    assert programma == [str(linux / "pmn" / "bin" / "pmn-motore")] and opzioni == []
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: linux / "casa"))
    monkeypatch.setenv("PMN_HOME", "")                       # vuota o assente: ~/.pmn, come ${PMN_HOME:-$HOME/.pmn}
    assert motore.comando_motore()[0] == [str(linux / "casa" / ".pmn" / "bin" / "pmn-motore")]
    monkeypatch.delenv("PMN_HOME")
    assert motore.comando_motore()[0] == [str(linux / "casa" / ".pmn" / "bin" / "pmn-motore")]


def test_il_finto_motore_resta_anche_su_linux(linux, monkeypatch):
    monkeypatch.setenv("PMN_MOTORE", "finto")
    assert motore.comando_motore()[0] == [sys.executable, str(RADICE / "installer" / "finto_motore.py")]


def test_motore_non_installato_porta_alla_pagina_motore(linux, qtbot):
    """~/.pmn/bin/pmn-motore non c'è ancora: un errore e un fine, come con wsl.exe che manca su Windows."""
    assert motore.comando_motore()[0] == [str(linux / "pmn" / "bin" / "pmn-motore")]   # mai wsl.exe da questo test
    c = motore.MotoreClient()
    eventi = []
    c.evento.connect(eventi.append)
    with qtbot.waitSignal(c.finito, timeout=30000) as s:
        c.avvia("info")
    assert s.args[0] == 4 and [e["tipo"] for e in eventi] == ["errore", "fine"]
    assert eventi[0]["codice"] == "MOTORE_NON_AVVIATO"


def test_i_percorsi_passano_invariati(linux, monkeypatch):
    f = linux / "Mario Rossi" / "p" / "config.yaml"
    assert motore.percorso_per_motore(f) == str(f.resolve())
    assert motore.percorso_per_motore(str(f)) == str(f.resolve())
    monkeypatch.chdir(linux)                                 # relativo: diventa assoluto e risolto
    assert motore.percorso_per_motore(Path("p") / ".." / "q" / "config.yaml") == \
        str((linux / "q" / "config.yaml").resolve())
    assert not motore.percorso_per_motore(f).startswith("/mnt/")


def test_i_testi_del_motore_tengono_i_percorsi_di_linux(linux, qtbot):
    """Su Linux /home/pmn/... e /mnt/... sono già percorsi che si aprono: restano come li scrive il motore."""
    c = motore.MotoreClient()
    visti = []
    c.evento.connect(visti.append)
    c._riga(b'{"tipo": "inizio", "corsa": "x", "log": "/home/pmn/.pmn/log/pmn_x.log"}')
    c._riga('{"tipo": "errore", "messaggio": "Risultati in /mnt/dati/p1/risultati.", "cosa_fare": "Manda a noi il '
            'file /home/pmn/.pmn/log/pmn_x.log."}'.encode())
    assert visti[0]["log"] == "/home/pmn/.pmn/log/pmn_x.log"
    assert visti[1]["messaggio"] == "Risultati in /mnt/dati/p1/risultati."
    assert visti[1]["cosa_fare"] == "Manda a noi il file /home/pmn/.pmn/log/pmn_x.log."


# ---------------- spazio libero ----------------
def test_lo_spazio_libero_e_quello_che_dice_il_motore(linux, qtbot, monkeypatch):
    """Su Linux `info` e installa_motore.sh misurano già il disco vero di PMN_HOME: l'app non corregge e non passa
    --spazio-libero (serve solo sotto WSL, dove il motore vede il disco virtuale)."""
    monkeypatch.setitem(sys.modules, "winreg", None)         # su Linux il registro di Windows non c'è (ImportError)
    assert motore.spazio_windows_gb() is None
    contesto = Contesto()
    contesto.info = {"database": [], "programmi": {}, "ram_gb": 15.6, "processori": 8, "spazio_libero_gb": 643}
    m = pagina_motore.PaginaMotore(contesto)
    qtbot.addWidget(m)
    m._disegna()
    assert "643 GB liberi" in m.stato.text()
    lanci = []
    monkeypatch.setattr(m.client, "avvia", lambda *a: lanci.append(a))
    m.installa()
    assert lanci == [("installa",)]


# ---------------- aprire file e cartelle ----------------
def test_registro_e_cartelle_si_aprono_col_programma_del_sistema(linux, qtbot, monkeypatch):
    aperti = []
    monkeypatch.setattr(esecuzione.QDesktopServices, "openUrl", lambda u: aperti.append(u) or True)
    pagina = esecuzione.PaginaEsecuzione(Contesto())
    qtbot.addWidget(pagina)
    pagina.client._riga(b'{"tipo": "inizio", "corsa": "x", "log": "/home/pmn/.pmn/log/pmn_x.log"}')
    pagina.dettagli.setChecked(True)
    pagina.apri_registro.click()
    assert aperti == [QUrl("file:///home/pmn/.pmn/log/pmn_x.log")]   # il percorso del motore, senza \\wsl.localhost

    p = progetto.nuovo("prova")
    (p.risultati / "referto").mkdir(parents=True)
    contesto = Contesto()
    contesto.progetto = p
    r = risultati.PaginaRisultati(contesto)
    qtbot.addWidget(r)
    r.apri(p.risultati / "referto")
    assert aperti[1:] == [QUrl.fromLocalFile(str((p.risultati / "referto").resolve()))]
    r.apri(linux)                                            # fuori dal progetto: non si apre
    assert len(aperti) == 2


# ---------------- testi che su Linux sarebbero falsi ----------------
def test_pagina_motore_senza_windows_e_senza_wsl(linux, qtbot):
    m = pagina_motore.PaginaMotore(Contesto())
    qtbot.addWidget(m)
    m._disegna(NON_AVVIATO)
    m.errore_corsa = NON_AVVIATO
    m._esito("verifica", {})
    testo = scritte(m)
    assert "Windows" not in testo and "WSL" not in testo
    assert "Il motore fa i calcoli su questo computer. Si installa una volta e si controlla da qui." in testo
    assert testo.count("(installa_pmn.sh)") == 2             # il riquadro in alto e quello dell'esito


def test_aggiornamento_su_linux_senza_doppio_clic(linux, qtbot):
    assert not aggiorna.puo_installare()
    e = aggiorna.errore_rete(QNetworkReply.NetworkError.SslHandshakeFailedError)
    assert e.codice == "CERTIFICATO" and "Windows" not in e.messaggio and "GitHub" in e.messaggio
    h = home.PaginaHome(Contesto())
    qtbot.addWidget(h)
    h._controllato({"stato": "nuova", "installata": "1.2.0", "nuova": "9.0.0", "novita": "", "pagina": "",
                    "pacchetto": {"nome": "profilemetananni.zip", "url": "https://x", "byte": 1, "sha256": None}})
    testo = scritte(h)
    assert "doppio clic" not in testo and "installer/linux/installa_pmn.sh" in testo


def test_testi_di_linux_anche_in_inglese(linux, qtbot):
    lingua.imposta("en")
    try:
        m = pagina_motore.PaginaMotore(Contesto())
        qtbot.addWidget(m)
        m._disegna(NON_AVVIATO)
        testo = scritte(m)
        assert "Windows" not in testo and "WSL" not in testo and "(installa_pmn.sh)" in testo
        assert "The engine runs its calculations on this computer. It is installed once" in testo
        e = aggiorna.errore_rete(QNetworkReply.NetworkError.SslHandshakeFailedError)
        assert e.messaggio == "This computer cannot verify the security certificate of GitHub."
        h = home.PaginaHome(Contesto())
        qtbot.addWidget(h)
        h._controllato({"stato": "nuova", "installata": "1.2.0", "nuova": "9.0.0", "novita": "", "pagina": "",
                        "pacchetto": {"nome": "profilemetananni.zip", "url": "https://x", "byte": 1, "sha256": None}})
        assert "run bash installer/linux/installa_pmn.sh again" in scritte(h)
    finally:
        lingua.imposta("it")


# ---------------- voce di menu e installatore di Ubuntu ----------------
def test_la_finestra_porta_il_nome_della_voce_di_menu(linux, monkeypatch):
    """Su Ubuntu l'icona nella barra viene dalla voce di menu: l'app dichiara il nome del file .desktop che
    installer/linux/installa_pmn.sh scrive."""
    nomi = []

    class App:
        def __init__(self, argomenti):
            pass

        def setApplicationName(self, nome):
            pass

        def setDesktopFileName(self, nome):
            nomi.append(nome)

        def exec(self):
            return 0

    class FinestraFinta:
        def show(self):
            pass

        def avvia(self):
            pass

    monkeypatch.setattr(main, "QApplication", App)
    monkeypatch.setattr(main, "prepara", lambda app: None)
    monkeypatch.setattr(main, "Finestra", FinestraFinta)
    monkeypatch.setattr(main.lingua, "salvata", lambda: "it")
    assert main.main() == 0 and nomi == ["profilemetananni"]
    assert f"/applications/{nomi[0]}.desktop" in INSTALLA.read_text(encoding="utf-8")


def test_installatore_di_ubuntu_controlli_statici():
    """Ciò che si può controllare senza Linux: fine riga LF, modo severo, sudo mai eseguito (solo nei messaggi), niente
    eval, nessun indirizzo da scaricare e niente passato a una shell, permessi 644 o 755, versioni lette da
    app/requirements.txt, stesso elenco di programmi di sistema di installer/installa_motore.sh."""
    dati = INSTALLA.read_bytes()
    testo = dati.decode("utf-8")
    assert dati.startswith(b"#!/usr/bin/env bash\n") and b"\r" not in dati
    assert "\nset -euo pipefail\n" in testo
    codice = "\n".join(r for r in testo.splitlines() if not r.lstrip().startswith("#"))
    assert not re.search(r"\beval\b|https?://|\|\s*(ba)?sh\b", codice)
    assert not re.search(r"(^|[;&|(]|\bthen|\bdo|\belse)\s*sudo\b", codice, re.M)
    assert set(re.findall(r"\bchmod\s+(\S+)", codice)) == {"644", "755"}
    assert "app/requirements.txt" in testo and not re.search(r"(PySide6|PyYAML)==\d", testo)
    del_motore = re.search(r"^for c in ([a-z0-9 ]+); do$",
                           (RADICE / "installer" / "installa_motore.sh").read_text(encoding="utf-8"), re.M).group(1)
    nostri = re.search(r'^PROGRAMMI="([^"]+)"', testo, re.M).group(1)
    assert [x.split(":")[0] for x in nostri.split()] == del_motore.split()
