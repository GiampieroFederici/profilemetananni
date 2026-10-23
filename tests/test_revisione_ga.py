# -*- coding: utf-8 -*-
"""Revisione del 22/10, gruppo "GA-avvio-mcp": un test per problema (P14, P09, P12, P13, P11, P17, P26, P38),
rosso prima della correzione e verde dopo.

Gira con due ambienti: le prove dell'app con app\\.venv (PySide6, pytest-qt), quelle del server MCP con pmn_mcp\\.venv
(mcp). Ogni prova salta da sola se il suo ambiente non c'è (per esempio nel motore in WSL)."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
sys.path.insert(0, str(RADICE / "tests"))
try:
    import pytestqt  # noqa: F401
    HA_QT = True
except ImportError:
    HA_QT = False
solo_qt = pytest.mark.skipif(not HA_QT, reason="serve l'ambiente dell'app (PySide6, pytest-qt)")


def server_mcp():
    """pmn_mcp/server.py caricato senza avviarlo (parte solo sotto __main__)."""
    pytest.importorskip("mcp")
    spec = importlib.util.spec_from_file_location("pmn_mcp_server_ga", RADICE / "pmn_mcp" / "server.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------- P14: wsl.exe senza shell ----------------
@solo_qt
def test_p14_app_lancia_il_motore_senza_shell(monkeypatch):
    from app import motore
    monkeypatch.delenv("PMN_MOTORE", raising=False)
    prog = motore.comando_motore()[0]
    assert "--" not in prog and prog[prog.index(motore.MOTORE_WSL) - 1] == "-e"


def test_p14_mcp_lancia_il_motore_senza_shell(monkeypatch):
    s = server_mcp()
    monkeypatch.delenv("PMN_MOTORE", raising=False)
    prog = s.comando("info")
    assert "--" not in prog and prog[prog.index(s.MOTORE_WSL) - 1] == "-e"


@pytest.mark.skipif(sys.platform != "win32" or not os.environ.get("PMN_TEST_DISTRO")
                    or os.environ.get("PMN_TEST_DISTRO") == "pmn",
                    reason="prova vera di wsl.exe: solo con PMN_TEST_DISTRO (mai la WSL pmn)")
def test_p14_percorsi_con_apostrofo_e_comandi_arrivano_intatti(monkeypatch):
    s = server_mcp()
    monkeypatch.delenv("PMN_MOTORE", raising=False)
    prog = s.comando("--progetto", "/mnt/c/Users/D'Angelo/x$(id)")
    i = prog.index(s.MOTORE_WSL)
    prog[i] = "/bin/echo"
    prog[prog.index("-d") + 1] = os.environ["PMN_TEST_DISTRO"]
    prog[prog.index("-u") + 1] = "root"
    r = subprocess.run(prog, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "/mnt/c/Users/D'Angelo/x$(id)" in r.stdout, (r.returncode, r.stdout, r.stderr)


# ---------------- P09: '100.000' con l'italiano ----------------
def test_p09_migliaia_con_un_solo_punto_in_italiano(monkeypatch):
    from app import lingua
    monkeypatch.setattr(lingua, "_attuale", "it")
    assert [lingua.leggi_numero(x) for x in ("100.000", "1.000", "2.500", "3.5", "0.97", "0.970", "6.0", "1.000,5",
                                             "1.000.000", "3,5")] == \
        [100000.0, 1000.0, 2500.0, 3.5, 0.97, 0.97, 6.0, 1000.5, 1000000.0, 3.5]
    monkeypatch.setattr(lingua, "_attuale", "en")       # l'inglese non cambia
    assert [lingua.leggi_numero(x) for x in ("100.000", "2.500", "1,000", "3.5")] == [100.0, 2.5, 1000.0, 3.5]


# ---------------- server MCP: progetti, client e analisi finte ----------------
@pytest.fixture
def progetti_mcp(tmp_path, monkeypatch):
    """Come la fixture `progetti` di tests/test_mcp.py; in più PMN_PROGETTI e il finto per le prove dirette."""
    radice = tmp_path / "ProfileMetaNanni"
    (radice / "Salame_prova").mkdir(parents=True)
    (radice / "Salame_prova" / "config.yaml").write_text("project_name: Salame_prova\n", encoding="utf-8")
    (tmp_path / "temp").mkdir()
    monkeypatch.setenv("PMN_PROGETTI", str(radice))
    monkeypatch.setenv("PMN_MOTORE", "finto")
    return radice


def client_mcp():
    """con_client, dati e COTTO di tests/test_mcp.py (client MCP vero, server in un processo figlio)."""
    pytest.importorskip("mcp")
    import test_mcp
    return test_mcp


class CtxConferma:
    """Il Context di un client che sa chiedere la conferma (elicitation), e la persona dice sì."""
    client_capabilities = type("Caps", (), {"elicitation": object()})()

    async def elicit(self, messaggio, schema):
        return type("R", (), {"action": "accept", "data": type("D", (), {"avvia": True})()})()


def motore_che_stampa(s, monkeypatch, codice):
    """Il motore di esegui sostituito da un python con questo codice (e la stima da una risposta fissa)."""
    async def stima(*a, **k):
        return {"esito": "ok", "messaggio": "", "risultato": {"campioni": 1, "tempo_totale_s": 60, "spazio_gb": 1,
                                                             "spazio_libero_gb": 9}}
    monkeypatch.setattr(s, "lancia", stima)
    monkeypatch.setattr(s, "comando", lambda nome, *a: [sys.executable, "-c", "import json, time\n" + codice])


INIZIO = 'print(json.dumps({"tipo": "inizio", "corsa": "2026-10-22T10-00-00", "comando": "esegui"}), flush=True)\n'


def esegui_e_aspetta(s, progetto="Salame_prova"):
    import asyncio

    async def lavoro():
        r = await s.esegui(progetto, CtxConferma())
        await asyncio.wait([s.Stato.analisi.compito], timeout=30)
        return r
    return asyncio.run(lavoro())


# ---------------- P12: righe JSON oltre 64 KiB ----------------
def test_p12_sicurezza_curva_lunga_oltre_64kib(progetti_mcp):
    """90 giorni di stagionatura: il 'fine' del motore supera i 64 KiB su una riga."""
    import json
    t = client_mcp()
    ingresso = {"prodotto": t.COTTO["prodotto"], "profilo_temperatura": [[12, 2160]]}

    async def lavoro(s):
        return t.dati(await s.call_tool("sicurezza", {"ingresso": ingresso}))
    d = t.con_client(progetti_mcp, lavoro)
    assert d["esito"] == "ok" and len(json.dumps(d["risultato"])) > 65536


def test_p12_esegui_con_fine_lunga_non_resta_in_corso(progetti_mcp, monkeypatch):
    s = server_mcp()
    motore_che_stampa(s, monkeypatch, INIZIO + 'print(json.dumps({"tipo": "fine", "esito": "ok", "messaggio": "ok", '
                                               '"risultato": {"x": "a" * 100_000}}))')
    esegui_e_aspetta(s)
    a = s.Stato.analisi
    assert not a.in_corso() and a.esito["esito"] == "ok" and len(a.esito["risultato"]["x"]) == 100_000


def test_p12_errore_di_lettura_non_lascia_l_analisi_in_corso(progetti_mcp, monkeypatch):
    s = server_mcp()
    motore_che_stampa(s, monkeypatch, "")

    async def rotto(*a, **k):
        raise ValueError("Separator is not found, and chunk exceed the limit")
    monkeypatch.setattr(s, "raccogli", rotto)
    esegui_e_aspetta(s)
    a = s.Stato.analisi
    assert not a.in_corso() and a.esito["esito"] == "errore" and a.esito["risultato"]["codice"] == "ERRORE_INTERNO"


# ---------------- P13: esegui rifiutato dal motore ----------------
@pytest.mark.parametrize("opzioni, codice", [("--scenario GIA_IN_CORSO --velocita 0", "GIA_IN_CORSO"),
                                             ("--scenario inesistente", "ERRORE_INTERNO")])
def test_p13_esegui_rifiutato_dal_motore_non_dice_avviata(progetti_mcp, opzioni, codice):
    t = client_mcp()

    async def lavoro(s):
        r1 = t.dati(await s.call_tool("esegui", {"progetto": "Salame_prova"}))
        return t.dati(await s.call_tool("esegui", {"progetto": "Salame_prova", "codice_conferma": r1["codice_conferma"]}))
    r2 = t.con_client(progetti_mcp, lavoro, opzioni=opzioni)
    assert r2["avviata"] is False and r2["codice"] == codice and r2["motivo"]


# ---------------- P11: avvio con wsl.exe appeso ----------------
@solo_qt
def test_p11_avvio_con_motore_appeso_non_resta_bloccato(qtbot, monkeypatch):
    """wsl.exe che non risponde: dopo AVVIO_MAX_MS l'app chiude info e va a I miei progetti con MOTORE_NON_AVVIATO."""
    from app import finestra, motore
    from test_app_scheletro import pagine_finte
    python = getattr(sys, "_base_executable", sys.executable)     # non il lanciatore del venv: kill() chiude tutto
    monkeypatch.setattr(motore, "comando_motore", lambda: ([python, "-c", "import time; time.sleep(3600)"], []))
    monkeypatch.setattr(finestra, "AVVIO_MIN_MS", 0)
    monkeypatch.setattr(finestra, "AVVIO_MAX_MS", 1500)
    monkeypatch.setattr(finestra, "PAGINE", pagine_finte())
    f = finestra.Finestra(movimento=False)
    qtbot.addWidget(f)
    eventi = []
    f.avvia()
    f.client_info.evento.connect(eventi.append)
    qtbot.waitUntil(lambda: f.fuori.currentIndex() == 1, timeout=10000)
    assert not f.client_info.in_corso() and f.contesto.info is None
    assert [e.get("codice") for e in eventi if e["tipo"] == "errore"] == ["MOTORE_NON_AVVIATO"]


# ---------------- P17: progetto NCBI con & o ! nella cartella Documenti ----------------
@solo_qt
@pytest.mark.parametrize("documenti", ["OneDrive - Azienda Rossi & C", "Documenti!"])
def test_p17_codici_ncbi_in_una_cartella_con_simboli_fermati_con_la_causa_vera(qtbot, monkeypatch, tmp_path, documenti):
    """Il motore rifiuta srr_list con & o ! (validate_path_safe): l'app lo dice subito, vicino ai codici, e resta qui."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QLabel
    from app import finestra, progetto
    monkeypatch.setenv("PMN_MOTORE", "finto")
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    (tmp_path / "temp").mkdir()
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("TMP", str(tmp_path / "temp"))
    radice = tmp_path / documenti / "ProfileMetaNanni"
    monkeypatch.setattr(progetto, "cartella_progetti", lambda: radice)
    monkeypatch.setattr(finestra, "AVVIO_MIN_MS", 0)
    f = finestra.Finestra(movimento=False)
    qtbot.addWidget(f)
    f.show()
    f.avvia()
    qtbot.waitUntil(lambda: f.attuale == "home", timeout=30000)
    f.pagine["home"].azione_principale()                         # Nuovo progetto: i progetti locali restano possibili
    assert f.attuale == "campioni"
    c = f.pagine["campioni"]
    c.testo_codici.setPlainText("SRR4875279")
    c.azione_principale()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QCoreApplication.processEvents()
    testo = " ".join(e.text() for e in c.findChildren(QLabel) if e.isVisibleTo(c))
    assert f.attuale == "campioni" and "un carattere che il motore non accetta" in testo
    assert f.contesto.progetto.leggi()["paths"]["srr_list"] == ""


@solo_qt
def test_p17_controprova_cartella_senza_simboli(monkeypatch, tmp_path):
    from app import progetto
    p = progetto.nuovo("prova1", radice=tmp_path / "Documenti" / "ProfileMetaNanni")
    assert p.cartella.is_dir() and progetto.percorso_sicuro(p.codici_campioni)


# ---------------- P26: stato senza il risultato doppio, solo gli eventi nuovi ----------------
def test_p26_stato_senza_risultato_doppio_e_solo_eventi_nuovi(progetti_mcp, monkeypatch):
    import asyncio
    s = server_mcp()
    a = s.Analisi(progetti_mcp / "Salame_prova" / "config.yaml")
    a.eventi += [{"tipo": "inizio", "corsa": "2026-10-22T10-00-00"}] + \
        [{"tipo": "avanzamento", "percentuale": p, "messaggio": "m", "eta_s": 1} for p in (10, 50, 90)] + \
        [{"tipo": "fine", "esito": "ok", "messaggio": "ok", "risultato": {"x": 1}}]
    a.esito = {"esito": "ok", "messaggio": "ok", "risultato": {"x": 1}, "eventi": a.eventi}
    monkeypatch.setattr(s.Stato, "analisi", a)
    st = asyncio.run(s.stato())
    assert st["fine"]["risultato"] == {"x": 1} and st["eventi"][-1]["tipo"] == "fine"
    assert "risultato" not in st["eventi"][-1] and st["prossimo"] == 5 and len(st["eventi"]) == 5
    assert asyncio.run(s.stato(dal=st["prossimo"]))["eventi"] == []
    assert [e["tipo"] for e in asyncio.run(s.stato(dal=4))["eventi"]] == ["fine"]
    assert "risultato" in a.eventi[-1]                           # gli eventi dell'analisi restano interi


# ---------------- P38: conferma di esegui con i numeri all'italiana ----------------
def test_p38_riassunto_con_la_virgola_dei_decimali():
    """La frase è sempre in italiano: virgola per i decimali, singolare con 1 campione e 1 minuto."""
    s = server_mcp()
    t = s.riassunto({"esito": "ok", "risultato": {"campioni": 2, "tempo_totale_s": 2280, "spazio_gb": 3.2,
                                                  "spazio_libero_gb": 412.5}})
    assert t == "2 campioni, circa 38 minuti, 3,2 GB di spazio (liberi 412,5 GB)."
    assert s.riassunto({"esito": "ok", "risultato": {"campioni": 1, "tempo_totale_s": 60, "spazio_gb": 12,
                                                     "spazio_libero_gb": 643}}) == \
        "1 campione, circa 1 minuto, 12 GB di spazio (liberi 643 GB)."
