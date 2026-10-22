# -*- coding: utf-8 -*-
"""Fixes of the 22/10 review, group GC-motore (P02, P03, P15, P41): each test reproduces one confirmed problem.
The tests of the real engine need process groups and signals: Linux/WSL only, like tests/test_pmn_motore.py."""
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from contratto import controlla
from test_pmn_motore import MOTORE, ROOT, ambiente, lancia  # noqa: F401  (ambiente: fixture of the engine tests)

sys.path.insert(0, os.path.join(ROOT, "motore"))

linux = pytest.mark.skipif(os.name == "nt", reason="process groups and signals: Linux/WSL only")


# ---------------- P02: annulla before run.sh starts ----------------
@linux
def test_p02_annulla_prima_di_run_sh(ambiente, tmp_path):
    """annulla while esegui still asks ENA/NCBI for the sizes (lock with pgid None): run.sh must never start."""
    env, progetto = ambiente
    (tmp_path / "srr.txt").write_text("SRR0000001\n", encoding="utf-8")   # a real code: campioni() goes to the network
    libera = threading.Event()

    class Lento(BaseHTTPRequestHandler):
        def rispondi(self):
            libera.wait(30)            # ENA and NCBI slow until annulla has answered
            self.send_response(400)    # then "no such run": camp None, as with a network outage
            self.end_headers()
        do_GET = do_POST = rispondi

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Lento)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    rete = {"PMN_ENA_SEARCH": url, "PMN_ENA_API": url, "PMN_NCBI_API": url, "no_proxy": "127.0.0.1"}
    blocco = progetto.parent.parent / "pmn" / "stato" / "esegui.lock"
    try:
        p = subprocess.Popen([sys.executable, MOTORE, "esegui", "--progetto", str(progetto)], stdout=subprocess.PIPE,
                             text=True, encoding="utf-8", env={**env, **rete})
        for _ in range(100):
            if blocco.exists():
                break
            time.sleep(0.1)
        dati = json.loads(blocco.read_text(encoding="utf-8"))
        assert dati["pgid"] is None                     # still in campioni(): run.sh not started
        ev, codice = lancia(env, "annulla", "--corsa", dati["corsa"])
        assert codice == 0 and ev[-1]["risultato"] == {"annullata": True}
        libera.set()
        out, _ = p.communicate(timeout=60)
    finally:
        libera.set()
        srv.shutdown()
        srv.server_close()
    ev = controlla(out, p.returncode, "esegui")
    assert p.returncode == 3 and ev[-1]["esito"] == "annullata"
    assert [e["passo"] for e in ev if e["tipo"] == "avanzamento"] == []
    assert not (tmp_path / "lavoro" / "metaphlan" / "S1_profile.txt").exists()
    assert not blocco.exists()


# ---------------- P03: Simpson of a sample without species ----------------
def test_p03_campione_senza_specie_non_ha_simpson_massimo():
    """MetaPhlAn profile with only UNCLASSIFIED: 0 taxa, so Simpson 0 (not 1 = the highest diversity)."""
    import diversita
    assert diversita.indici([]) == {"ricchezza": 0, "shannon": 0, "simpson": 0.0}
    t = {r["campione"]: r for r in diversita.tabella_metaphlan(
        {"vuoto": ([], 1000), "pieno": ([("X", 50.0), ("Y", 30.0)], 1000)}, {})}
    assert t["vuoto"]["ricchezza"] == 0 and t["vuoto"]["simpson"] == 0.0
    assert t["pieno"]["simpson"] == pytest.approx(0.46875)       # with taxa: same value as before
