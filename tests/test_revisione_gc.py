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


# ---------------- P41: annulla stops installa too ----------------
FINTO = os.path.join(ROOT, "installer", "finto_motore.py")


def test_p41_annulla_ferma_installa_finto():
    """'Ferma l'installazione' calls annulla with the run of installa: the fake engine must stop it (code 3)."""
    p = subprocess.Popen([sys.executable, FINTO, "installa", "--velocita", "50"], stdout=subprocess.PIPE, text=True,
                         encoding="utf-8")
    try:
        righe = [p.stdout.readline()]
        corsa = json.loads(righe[0])["corsa"]
        while json.loads(righe[-1]).get("passo") != "programmi":
            righe.append(p.stdout.readline())
        r = subprocess.run([sys.executable, FINTO, "annulla", "--corsa", corsa, "--velocita", "0"], capture_output=True,
                           text=True, encoding="utf-8", timeout=60)
        assert controlla(r.stdout, r.returncode, "annulla")[-1]["risultato"] == {"annullata": True}
        resto, _ = p.communicate(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()
    ev = controlla("".join(righe) + resto, p.returncode, "installa")
    assert p.returncode == 3 and ev[-1]["esito"] == "annullata"


@linux
def test_p41_annulla_motore_vero_ferma_installa():
    """Real chain: installa_motore.sh --json (as pmn-motore installa runs it) writes installa.lock with its run and
    its own process group; pmn_motore.py annulla --corsa stops it (fine annullata, code 3) and the lock goes away."""
    import shutil
    import tempfile
    from pathlib import Path
    from test_installa_eventi import INSTALLA, SPECCHIO, catalogo
    d = Path(tempfile.mkdtemp(prefix="pmn_test_", dir=Path.home()))   # on disk, as in test_installa_eventi
    try:
        home, c = catalogo(d)
        env = {**os.environ, "PMN_HOME": str(home)}
        p = subprocess.Popen(["bash", INSTALLA, "--json", "--catalogo", str(c), *SPECCHIO], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", env=env)
        try:
            righe = [p.stdout.readline(), p.stdout.readline()]   # inizio, then the space check: now it asks s/n
            corsa = json.loads(righe[0])["corsa"]
            blocco = home / "stato" / "installa.lock"
            assert json.loads(blocco.read_text(encoding="utf-8")) == {"corsa": corsa, "pid": p.pid, "pgid": p.pid}
            assert os.getpgid(p.pid) == p.pid != os.getpgid(0)    # its own group: annulla does not hit the caller
            attesa = threading.Thread(target=p.wait)              # reaped at once, as the WSL does
            attesa.start()
            ev, codice = lancia(env, "annulla", "--corsa", corsa)
            assert codice == 0 and ev[-1]["risultato"] == {"annullata": True}
            attesa.join(30)
            resto = p.stdout.read()
        finally:
            if p.poll() is None:
                p.kill()
            p.stdin.close()
        ev = controlla("".join(righe) + resto, p.returncode, "installa")
        assert p.returncode == 3 and ev[-1]["esito"] == "annullata"
        assert not blocco.exists()
    finally:
        shutil.rmtree(d, ignore_errors=True)


@linux
def test_p41_lock_di_installa_rimasto(ambiente):
    """installa.lock left by an installation that died (SIGKILL, power off): no signal to a pgid maybe reused."""
    env, progetto = ambiente
    stato = progetto.parent.parent / "pmn" / "stato"
    morto = subprocess.Popen(["true"])
    morto.wait()
    (stato / "installa.lock").write_text(json.dumps({"corsa": "X", "pid": morto.pid, "pgid": morto.pid}),
                                         encoding="utf-8")
    ev, codice = lancia(env, "annulla", "--corsa", "X")
    assert codice == 0 and ev[-1]["risultato"] == {"annullata": False}
    assert not (stato / "installa.lock").exists()
