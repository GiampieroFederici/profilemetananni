# -*- coding: utf-8 -*-
"""installer/installa_motore.sh --json speaks the engine-GUI contract (docs/contratto_motore.md section 4)
in the cases that need no download. Linux only (the installer refuses anything else): on Windows run it
inside WSL, e.g. with the pmn_reports_py environment."""
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from contratto import controlla

pytestmark = pytest.mark.skipif(sys.platform != "linux" or not shutil.which("bash"),
                                reason="installa_motore.sh runs on Linux/WSL only")

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
INSTALLA = os.path.join(ROOT, "installer", "installa_motore.sh")
TESTA = "gruppo\ttipo\tsorgente\tpercorso\tbyte\tbyte_finale\tmd5\tdestinazione\n"
MD5 = "0" * 32
SPECCHIO = ["--specchio", "http://127.0.0.1:9"]   # never contacted: nothing left to download


@pytest.fixture
def tmp_path():
    """On disk, not in /tmp: WSL keeps /tmp in RAM (~6 GB), less than the 16 GB the installer keeps for the programs."""
    d = Path(tempfile.mkdtemp(prefix="pmn_test_", dir=Path.home()))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def catalogo(tmp_path, byte=10, installato=True):
    """One-row catalogue; installato=True also leaves the file and its marker, as after a finished install."""
    home = tmp_path / "home"
    c = tmp_path / "catalogo.tsv"
    c.write_text(TESTA + f"prova\tfile\tpmn\tprova/x\t{byte}\t{byte}\t{MD5}\tprova/x\n", encoding="utf-8")
    if installato:
        (home / "db" / "prova").mkdir(parents=True)
        (home / "db" / "prova" / "x").write_text("x", encoding="utf-8")
        (home / "stato").mkdir()
        (home / "stato" / "prova__x.ok").write_text(MD5 + "\n", encoding="utf-8")
    return home, c


def lancia(home, *arg, stdin=""):
    env = {**os.environ, "PMN_HOME": str(home)}
    env.pop("PMN_URL_PACCHETTI", None)
    r = subprocess.run(["bash", INSTALLA, "--json", *arg], input=stdin, capture_output=True, text=True,
                       encoding="utf-8", env=env, timeout=120)
    return r.stdout, r.returncode


def test_stima_reports_the_numbers(tmp_path):
    home, c = catalogo(tmp_path)
    out, rc = lancia(home, "--stima", "--catalogo", str(c), *SPECCHIO)
    ev = controlla(out, rc, "installa")
    assert rc == 0
    r = ev[-1]["risultato"]
    assert r["da_scaricare_gb"] == 0 and r["tempo_stimato_s"] == 0 and r["spazio_libero_gb"] > 0
    # Italian by default, as before (since B2 the Windows part reads the number from the result, not this text)
    assert any(e["messaggio"].startswith("Da scaricare: circa 0 GB") for e in ev)


def errore(home, *arg):
    out, rc = lancia(home, *arg)
    ev = controlla(out, rc, "installa")
    assert rc == 2 and ev[-1]["esito"] == "errore"
    return ev[-2]["codice"]


def test_missing_catalogue(tmp_path):
    assert errore(tmp_path / "home", "--stima", "--catalogo", str(tmp_path / "manca.tsv")) == "CONFIG_NON_VALIDA"


def test_not_enough_space_stops_before_downloading(tmp_path):
    home, c = catalogo(tmp_path, byte=10**18, installato=False)
    assert errore(home, "--si", "--catalogo", str(c), *SPECCHIO) == "SPAZIO_INSUFFICIENTE"
    assert not (home / "db" / "prova").exists()


def test_unpublished_packages(tmp_path):
    home, c = catalogo(tmp_path, installato=False)
    assert errore(home, "--si", "--catalogo", str(c)) == "DOWNLOAD_FALLITO"


def test_answer_no_is_annullata(tmp_path):
    home, c = catalogo(tmp_path)
    out, rc = lancia(home, "--catalogo", str(c), *SPECCHIO, stdin="n\n")
    ev = controlla(out, rc, "installa")
    assert rc == 3 and ev[-1]["esito"] == "annullata"


def test_interruption_is_annullata(tmp_path):
    home, c = catalogo(tmp_path)
    env = {**os.environ, "PMN_HOME": str(home)}
    p = subprocess.Popen(["bash", INSTALLA, "--json", "--catalogo", str(c), *SPECCHIO], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", env=env)
    righe = [p.stdout.readline(), p.stdout.readline()]   # inizio, then the space check: now it asks s/n
    time.sleep(1)
    p.send_signal(signal.SIGTERM)
    resto, _ = p.communicate(timeout=30)
    ev = controlla("".join(righe) + resto, p.returncode, "installa")
    assert p.returncode == 3 and ev[-1]["esito"] == "annullata"


def test_messages_with_real_accents_and_decimal_comma():
    """B2 (P5): the messages shown by the Windows installer had apostrophes for accents ("e'") and "57.2 MB/s"."""
    import re
    testo = open(INSTALLA, encoding="utf-8").read()
    messaggi = [r for r in testo.splitlines() if re.search(r"\b(evento|fallisci)\b", r) and not r.lstrip().startswith("#")]
    assert not [r for r in messaggi if re.search(r"\b(e|piu|gia|puo|velocita|cosi)'(?=[\s.,:;)!?])", r)]
    righe = "\n".join(r for r in testo.splitlines() if r.startswith(("num()", "mb_s()")))
    for lingua, atteso in (("it", "57,2"), ("en", "57.2")):
        out = subprocess.run(["bash", "-c", f"LINGUA={lingua}\n{righe}\nmb_s 57234567"],
                             capture_output=True, text=True).stdout
        assert out.strip() == atteso


def test_stima_in_english(tmp_path):
    """B2 (P12): with --lingua en (or PMN_LINGUA=en, set by pmn-motore) the messages for the person are in English;
    without, Italian as before."""
    home, c = catalogo(tmp_path)
    out, rc = lancia(home, "--stima", "--catalogo", str(c), *SPECCHIO, "--lingua", "en")
    ev = controlla(out, rc, "installa")
    assert rc == 0 and any(e["messaggio"].startswith("To download: about 0 GB") for e in ev)
    assert ev[-1]["messaggio"] == "Estimate ready: I have not downloaded anything."
