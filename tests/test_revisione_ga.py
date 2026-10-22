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
