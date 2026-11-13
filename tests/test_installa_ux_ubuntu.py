# -*- coding: utf-8 -*-
"""Test of the installation on a physical PC with Ubuntu in Italian (12/11/2026, LANG=it_IT.UTF-8): defects P1, P2, P3,
P4, P7, P8, P10 and P11 of installer/installa_motore.sh, installer/verifica_motore.sh and installer/linux/installa_pmn.sh.
Nothing real is installed: a fake micromamba, a fake final test, a fake engine installer and the local mirror
(tests/specchio_server.py), in a copy of installer/. Linux/WSL only, like the installer:
  /home/pmn/.pmn/mamba/envs/pmn_reports_py/bin/python -m pytest tests/test_installa_ux_ubuntu.py -q -p no:cacheprovider"""
import hashlib
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from contratto import controlla
from specchio_server import Specchio
from test_installa_eventi import meminfo
from test_scarico_pezzi import archivio, cartella, catalogo, estratto_come_la_1_0, md5, servi  # noqa: F401 (cartella: fixture)

pytestmark = pytest.mark.skipif(sys.platform != "linux" or not shutil.which("bash"),
                                reason="the installer runs on Linux/WSL only")
ROOT = Path(__file__).resolve().parent.parent
ENVS = re.search(r"^ENVS=\((.*)\)$", (ROOT / "installer" / "installa_motore.sh").read_text(encoding="utf-8"), re.M).group(1).split()


def lingua_del_sistema():
    """A locale of this system that is not C (Italian first: its decimal separator is a comma), or None."""
    try:
        presenti = set(subprocess.run(["locale", "-a"], capture_output=True, text=True).stdout.split())
    except OSError:
        return None
    return next((x for x in ("it_IT.utf8", "nl_NL.utf8", "de_DE.utf8", "en_US.utf8") if x in presenti), None)


LINGUA = lingua_del_sistema() if sys.platform == "linux" else None
con_lingua = pytest.mark.skipif(not LINGUA, reason="no locale other than C on this system (locale -a): generate one "
                                                   "with 'sudo locale-gen it_IT.UTF-8'")

# The sort of the PC of the test (Ubuntu 26.04) with a language other than C: "-" and "_" count the same, and two lines
# that count the same keep the order in which they arrive (GNU sort of Ubuntu 24.04 does not do it). With C: the real sort.
SORT = r'''#!/usr/bin/env bash
case "${LC_ALL:-${LC_COLLATE:-${LANG:-C}}}" in C | POSIX) exec VERO "$@" ;; esac
awk '{k = $0; gsub(/[-_]/, "", k); print k "\t" $0}' | LC_ALL=C VERO -s -t "$(printf '\t')" -k1,1 | cut -f2-
'''
# "create -n ENV -f LOCK" writes conda-meta/<package>.json for every package of the lock file; PMN_FINTO_ROTTO=ENV
# leaves the first package out of that environment. Every call is recorded in PMN_HOME/micromamba.chiamate.
MICROMAMBA = '''#!PYTHON
import os
import sys
from pathlib import Path
a = sys.argv[1:]
with open(Path(os.environ["PMN_HOME"]) / "micromamba.chiamate", "a") as f:
    f.write(" ".join(a) + "\\n")
if a[0] == "create":
    env, lock = a[a.index("-n") + 1], a[a.index("-f") + 1]
    meta = Path(os.environ["MAMBA_ROOT_PREFIX"]) / "envs" / env / "conda-meta"
    meta.mkdir(parents=True)
    nomi = [r.strip().rsplit("/", 1)[1].split("#")[0].replace(".conda", "").replace(".tar.bz2", "")
            for r in open(lock) if r.startswith("https://")]
    for n in nomi[os.environ.get("PMN_FINTO_ROTTO") == env:]:
        (meta / (n + ".json")).write_text("{}")
'''


def nomi_blocco(env):
    """The packages of a lock file, as installa_motore.sh reads them (name-version-build)."""
    righe = (ROOT / "installer" / "lock" / f"{env}.txt").read_text(encoding="utf-8").splitlines()
    return [r.strip().rsplit("/", 1)[1].split("#")[0].replace(".conda", "").replace(".tar.bz2", "")
            for r in righe if r.startswith("https://")]


def prepara(cartella, verifica="echo VERDE", ogni_s=None):
    """The copy of installer/ becomes a whole fake root: fake final test and fake micromamba (its SHA-256 goes in the
    copy of the script, so nothing is downloaded); ogni_s: seconds between two progress events (15 in the real one)."""
    radice, home = cartella / "radice", cartella / "home"
    (radice / "motore").mkdir()
    (radice / "motore" / "pmn-motore").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    shutil.copy(ROOT / "motore" / "pmn_casuale.c", radice / "motore")
    (radice / "installer" / "verifica_motore.sh").write_text(f"#!/usr/bin/env bash\n{verifica}\n", encoding="utf-8")
    (home / "bin").mkdir(parents=True, exist_ok=True)
    mm = home / "bin" / "micromamba"
    mm.write_text(MICROMAMBA.replace("PYTHON", sys.executable), encoding="utf-8")
    mm.chmod(0o755)
    script = radice / "installer" / "installa_motore.sh"
    testo = script.read_text(encoding="utf-8")
    vero = re.search(r"^MICROMAMBA_SHA256=(\w+)$", testo, re.M).group(1)
    testo = testo.replace(vero, hashlib.sha256(mm.read_bytes()).hexdigest())
    if ogni_s:
        assert "\nOGNI_S=15 " in testo
        testo = testo.replace("\nOGNI_S=15 ", f"\nOGNI_S={ogni_s} ")
    script.write_text(testo, encoding="utf-8")
    return radice, home


def finti(cartella, sort=True, awk=False):
    """A folder to put first in PATH: the sort of the PC of the test and, as awk, mawk (the awk of Ubuntu)."""
    d = cartella / "finti"
    d.mkdir(exist_ok=True)
    if sort:
        (d / "sort").write_text(SORT.replace("VERO", shutil.which("sort")), encoding="utf-8")
        (d / "sort").chmod(0o755)
    if awk:
        (d / "awk").symlink_to(shutil.which("mawk"))
    return str(d)


def ambiente(home, lingua=None, percorso=None, **altro):
    e = {k: v for k, v in os.environ.items()
         if k not in ("PMN_URL_PACCHETTI", "PMN_CONNESSIONI", "PMN_LINGUA", "LANGUAGE", "LANG") and not k.startswith("LC_")}
    e.update(PMN_HOME=str(home), TERM="xterm", **altro)
    if lingua:
        e.update(LANG=lingua, LC_ALL=lingua)
    if percorso:
        e["PATH"] = f"{percorso}:{e['PATH']}"
    return e


def comando(cartella, *arg, json=True):
    cmd = ["bash", str(cartella / "radice" / "installer" / "installa_motore.sh"), *(["--json"] if json else []), "--si",
           "--catalogo", str(cartella / "catalogo.tsv"), *arg]
    return cmd if "--specchio" in arg else cmd + ["--specchio", "http://127.0.0.1:9"]   # never contacted


def installa(cartella, *arg, json=True, **amb):
    return subprocess.run(comando(cartella, *arg, json=json), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                          encoding="utf-8", env=ambiente(cartella / "home", **amb), timeout=600)


def tutto_scaricato(cartella):
    """A one-row catalogue with its database already on the disk: nothing to download."""
    home = cartella / "home"
    catalogo(cartella, [("prova", "file", "pmn", "prova/x", 10, 10, "0" * 32, "prova/x")])
    (home / "db" / "prova").mkdir(parents=True, exist_ok=True)
    (home / "db" / "prova" / "x").write_text("x", encoding="utf-8")
    (home / "stato").mkdir(exist_ok=True)
    (home / "stato" / "prova__x.ok").write_text("0" * 32 + "\n", encoding="utf-8")


def creati(cartella):
    """The environments the fake micromamba was asked to create, in order."""
    f = cartella / "home" / "micromamba.chiamate"
    righe = f.read_text().splitlines() if f.exists() else []
    return [r.split()[r.split().index("-n") + 1] for r in righe if r.startswith("create")]


# ---------------- P1: the language of the system ----------------
@con_lingua
def test_p1_ambienti_giusti_riconosciuti_con_la_lingua_del_sistema(cartella):
    """P1: with Ubuntu in Italian "sort" followed the language: in the lock files there are cached_property and
    cached-property (typing-extensions and typing_extensions), the two lists came out in a different order and a right
    environment was "different": deleted and installed again at every launch, for ever."""
    pacchetti = {re.sub(r"-[^-]+-[^-]+$", "", n) for e in ENVS for n in nomi_blocco(e)}
    assert {"cached_property", "cached-property", "typing-extensions", "typing_extensions"} <= pacchetti
    prepara(cartella)
    tutto_scaricato(cartella)
    amb = {"lingua": LINGUA, "percorso": finti(cartella)}
    r = installa(cartella, **amb)
    ev = controlla(r.stdout, r.returncode, "installa")
    assert r.returncode == 0 and ev[-1]["risultato"]["verifica"] == "verde", ev[-2:]
    assert creati(cartella) == ENVS
    r = installa(cartella, **amb)                            # again: nothing deleted, nothing installed again
    assert r.returncode == 0 and creati(cartella) == ENVS


@con_lingua
def test_p1_numeri_degli_eventi_con_la_virgola_decimale(cartella):
    """With a language whose decimal separator is a comma (it_IT, nl_NL) mawk, the awk of Ubuntu, writes "0,0": the
    events for the app were not JSON any more ("da_scaricare_gb":0,0)."""
    if not shutil.which("mawk"):
        pytest.skip("mawk is not installed")
    virgola = subprocess.run(["locale", "decimal_point"], capture_output=True, text=True,
                             env={**os.environ, "LC_ALL": LINGUA}).stdout.strip()
    if virgola != ",":
        pytest.skip(f"the decimal separator of {LINGUA} is not a comma")
    prepara(cartella)
    tutto_scaricato(cartella)
    amb = {"lingua": LINGUA, "percorso": finti(cartella, sort=False, awk=True)}
    r = installa(cartella, "--stima", **amb)
    ev = controlla(r.stdout, r.returncode, "installa")       # every line is JSON
    assert r.returncode == 0 and ev[-1]["risultato"]["spazio_libero_gb"] > 0
    testo = (ROOT / "installer" / "installa_motore.sh").read_text(encoding="utf-8")
    righe = "\n".join(x for x in testo.splitlines() if x.startswith(("num()", "mb_s()", "export LC_ALL")))
    out = subprocess.run(["bash", "-c", f"LINGUA=en\n{righe}\nmb_s 57234567"], capture_output=True, text=True,
                         env=ambiente(cartella / "home", **amb)).stdout
    assert out.strip() == "57.2"                             # English texts keep the decimal point


# ---------------- P2: the final test ----------------
@con_lingua
def test_p2_prova_del_motore_verde_con_la_lingua_del_sistema(cartella):
    """P2: verifica_motore.sh sorted mini.mapout with the language of the system, the reference MD5 is in C order: RED
    for an engine that works (and the app then proposed to install again)."""
    radice, home = cartella / "radice", cartella / "home"
    righe = [b"read_B-1\tM1\n", b"read_a_1\tM2\n", b"read_a-1\tM3\n", b"read_A_2\tM4\n", b"Read-c\tM5\n", b"read_b_1\tM6\n"]
    profilo = [b"#mpa_vJan25\n", b"#the command, different every time\n", b"k__Bacteria\t100.0\n"]
    (radice / "installer" / "riferimenti.tsv").write_text(
        f"chiave\tvalore\tfonte\nmini_mapout_ordinato\t{md5(b''.join(sorted(righe)))}\tprova\n"
        f"mini_profilo\t{md5(profilo[0] + profilo[2])}\tprova\n", encoding="utf-8")
    (radice / "motore").mkdir()
    (radice / "motore" / "mini.mapout").write_bytes(b"".join(righe))
    (radice / "motore" / "mini_profile.txt").write_bytes(b"".join(profilo))
    (radice / "motore" / "metaphlan_fette.sh").write_text(
        '#!/usr/bin/env bash\nmkdir -p "$4" && cp "$(dirname "$0")"/mini.mapout "$(dirname "$0")"/mini_profile.txt "$4"\n',
        encoding="utf-8")
    for c in ("pmn_metaphlan/metaphlan", "pmn_metaphlan/bowtie2", "pmn_kraken/kraken2", "pmn_trim/fastp",
              "pmn_hostfilter/samtools", "pmn_download/prefetch"):
        f = home / "envs" / c.split("/")[0] / "bin" / c.split("/")[1]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        f.chmod(0o755)
    (home / "tmp").mkdir()
    (home / "installazione.env").write_text(f"PMN_ROOT={radice}\nPMN_ENVS={home / 'envs'}\nPMN_TMP={home / 'tmp'}\n"
                                            f"PMN_PROVA={home / 'prova'}\n", encoding="utf-8")
    amb = ambiente(home, lingua=LINGUA, PMN_MEMINFO=meminfo(cartella, 8165008, 4194304))
    ordinate = subprocess.run(["sort"], input=b"".join(righe), capture_output=True, env=amb).stdout
    assert ordinate != b"".join(sorted(righe))               # the language really sorts in another way than C
    r = subprocess.run(["bash", str(radice / "installer" / "verifica_motore.sh")], capture_output=True, text=True,
                       encoding="utf-8", timeout=120, env=amb)
    assert "OK      mini: mapout (righe ordinate)" in r.stdout and "DIVERSO" not in r.stdout, r.stdout
    assert r.returncode == 0 and r.stdout.strip().endswith("VERDE")


# ---------------- P3, P4: one message, a true one, and the error in the log ----------------
def test_p3_p4_ambiente_diverso_dal_blocco_non_si_rifa_a_ogni_rilancio(cartella):
    """P3: the check of an environment fails right after a successful "micromamba create": launching again does not
    help, so the message says to send the log (as R18 for a wrong MD5) and the environment is not deleted and
    installed again at the next launch. P4: the log has the error and what differs (diff without -q)."""
    radice, home = prepara(cartella)
    tutto_scaricato(cartella)
    manca = nomi_blocco("pmn_qc")[0]
    for giro in (1, 2):
        r = installa(cartella, PMN_FINTO_ROTTO="pmn_qc")
        ev = controlla(r.stdout, r.returncode, "installa")
        assert r.returncode == 2 and ev[-2]["codice"] == "DB_ROVINATO" and ev[-2]["passo"] == "programmi"
        assert ev[-2]["cosa_fare"] == f"Manda a noi il file {ev[0]['log']}.", giro
        log = Path(ev[0]["log"]).read_text(encoding="utf-8")
        assert f"< {manca}\n" in log, giro
        assert " errore DB_ROVINATO: L'ambiente pmn_qc non corrisponde" in log and " fine errore: " in log
        assert creati(cartella) == ["pmn_download", "pmn_qc"], giro          # the second time: not created again
        assert (home / "mamba" / "envs" / "pmn_qc" / "conda-meta").is_dir()
    lock = radice / "installer" / "lock" / "pmn_qc.txt"      # a new lock file (a correction): installed again
    lock.write_text(lock.read_text(encoding="utf-8") + "# nuovo\n", encoding="utf-8")
    r = installa(cartella)
    assert r.returncode == 0 and creati(cartella) == ["pmn_download", "pmn_qc", *ENVS[1:]]


def righe_pmn(r):
    return [x for x in r.stdout.splitlines() if x.startswith("[PMN]")]


def test_p3_un_solo_messaggio_e_vero(cartella):
    """P3: three sentences said "launch again / when you have solved", and "the engine is not installed yet" also
    with an engine installed and working. Now: the error with what to do, then one closing line, a true one."""
    radice, home = prepara(cartella)
    catalogo(cartella, [("prova", "file", "pmn", "prova/x", 10**18, 10**18, "0" * 32, "prova/x")])
    r = installa(cartella, json=False)
    assert r.returncode == 2 and "quando hai risolto" not in r.stdout.lower()
    assert [x for x in righe_pmn(r) if "rilanci" in x.lower()] == ["[PMN] Cosa fare: Libera spazio sul disco e rilancia."]
    assert righe_pmn(r)[-1] == "[PMN] Installazione non completata."
    # an engine installed before, and this launch has changed nothing: it is as it was
    (home / "installazione.env").write_text("PMN_ROOT=/x\n", encoding="utf-8")
    come_prima = ("[PMN] Installazione non completata. Non ho cambiato nulla: il motore già installato resta com'era "
                  "e, se funzionava, puoi continuare a usarlo.")
    r = installa(cartella, json=False)
    assert r.returncode == 2 and righe_pmn(r)[-1] == come_prima
    r = installa(cartella, "--lingua", "en", json=False)
    assert righe_pmn(r)[-1] == ("[PMN] Installation not completed. I have not changed anything: the engine already "
                                "installed is as it was and, if it worked, you can go on using it.")
    # installa_pmn.sh has just replaced the program of that engine with another version: not "nothing changed"
    r = installa(cartella, json=False, PMN_PROGRAMMA_SOSTITUITO="1")
    assert r.returncode == 2 and righe_pmn(r)[-1] == "[PMN] Installazione non completata."
    # this launch deletes an environment and installs it again: it does not say that nothing has changed
    tutto_scaricato(cartella)
    r = installa(cartella, json=False, PMN_FINTO_ROTTO="pmn_download")
    assert r.returncode == 2 and creati(cartella) == ["pmn_download"]
    assert righe_pmn(r)[-1] == "[PMN] Installazione non completata."
    assert not [x for x in righe_pmn(r) if "rilanci" in x.lower()]
    # again: the environment is not touched, but it differs from the lock file: nothing is said about the engine
    r = installa(cartella, json=False, PMN_FINTO_ROTTO="pmn_download")
    assert r.returncode == 2 and creati(cartella) == ["pmn_download"]
    assert righe_pmn(r)[-1] == "[PMN] Installazione non completata."


# ---------------- P4, P11: what the log says ----------------
def test_p4_p11_cadute_della_rete_nel_log_con_il_nuovo_tentativo(cartella):
    """P11: the log had "curl: (...)" for every drop of the network and nothing that said it was tried again.
    P4: the warnings (and the end) are in the log too."""
    dati = os.urandom(20 * 1024 * 1024)
    servi(cartella, "kraken", "x.bin", dati)
    catalogo(cartella, [("kraken_prova", "file", "kraken", "x.bin", len(dati), len(dati), md5(dati), "kraken/x.bin")])
    sp = Specchio(cartella / "servito", cadute={"/kraken/": 12})
    try:
        r = installa(cartella, "--solo-database", "--specchio", sp.url, "--connessioni", "4")
    finally:
        sp.chiudi()
    ev = controlla(r.stdout, r.returncode, "installa")
    avvisi = [e for e in ev if e["tipo"] == "avviso" and e["codice"] == "RETE_INTERROTTA"]
    assert r.returncode == 0 and avvisi
    log = Path(ev[0]["log"]).read_text(encoding="utf-8")
    assert log.count(" avviso RETE_INTERROTTA: La connessione si è interrotta: riprovo fra ") == len(avvisi)
    assert " fine ok: Database scaricati e controllati." in log


def test_p11_archivio_non_riconosciuto_una_riga_sola_nel_log(cartella):
    """P11: an archive extracted half way (or damaged) is not "already extracted by a 1.0": the log had the lines of
    md5sum ("No such file", "FAILED open or read", "WARNING"), which look like errors, at every launch."""
    estratto_come_la_1_0(cartella, "kraken_prova", per_file=False)
    (cartella / "home" / "db" / "kraken" / "a" / "f2.k2d").unlink()
    r = installa(cartella, "--stima")
    ev = controlla(r.stdout, r.returncode, "installa")
    assert r.returncode == 0
    log = Path(ev[0]["log"]).read_text(encoding="utf-8")
    assert not re.search(r"FAILED|WARNING|No such file", log), log
    assert log.count("non riconosciuto") == 1 and "kraken/a" in log


# ---------------- P7, P10: the terminal ----------------
def scarico_lento(cartella, mb=6):
    """A Kraken archive (2 files of mb MB) that arrives slowly: about 0,6 MB/s with 4 connections."""
    tgz, estratto = archivio(cartella, "kraken_prova", 2, mb)
    servi(cartella, "kraken", "a.tar.gz", tgz)
    catalogo(cartella, [("kraken_prova", "tar", "kraken", "a.tar.gz", len(tgz), estratto, md5(tgz), "kraken/a")])
    return Specchio(cartella / "servito", velocita={"/kraken/": 150_000})


def gruppo_vuoto(pgid, secondi=10):
    fine = time.monotonic() + secondi
    while time.monotonic() < fine:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.2)
    os.killpg(pgid, signal.SIGKILL)
    return False


def test_p7_ctrl_c_una_riga_sola_e_niente_resti(cartella):
    """P7: after Ctrl+C the terminal had the lines of bash "Terminated   curl ..." (one for each download stopped) and
    k2_....tar.gz.fifo stayed in ~/.pmn/tmp. Ctrl+C = SIGINT to the whole group of processes, as the terminal does."""
    prepara(cartella)
    sp = scarico_lento(cartella, mb=20)
    try:
        p = subprocess.Popen(comando(cartella, "--solo-database", "--specchio", sp.url, "--connessioni", "8", json=False),
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", env=ambiente(cartella / "home"), start_new_session=True)
        inizio = ""
        while "Scarico kraken_prova" not in inizio:
            riga = p.stdout.readline()
            assert riga, inizio
            inizio += riga
        time.sleep(4)                                        # the 8 downloads are going
        assert list((cartella / "home" / "tmp").rglob("*.fifo"))
        os.killpg(p.pid, signal.SIGINT)
        resto, _ = p.communicate(timeout=30)
        vuoto = gruppo_vuoto(p.pid)
    finally:
        sp.chiudi()
    uscita = inizio + resto
    assert p.returncode == 3 and vuoto
    assert "Terminated" not in uscita and "curl" not in uscita, uscita
    assert [x for x in uscita.splitlines() if "nterrott" in x] == \
        ["[PMN] Installazione interrotta. Rilancia lo stesso comando: riprende da dove era rimasta."]
    log = next((cartella / "home" / "log").glob("installazione_*.log")).read_text(encoding="utf-8")
    assert " fine annullata: Installazione interrotta." in log               # P4
    assert not list((cartella / "home").rglob("*.fifo"))
    assert [x.name for x in (cartella / "home" / "tmp").iterdir() if x.name.startswith("scarico_")] == []


def test_p10_senza_terminale_una_riga_di_avanzamento_ogni_5_minuti(cartella):
    """P10: 813 lines "Scarico i database: x di y" in 3,5 hours (one every 15 s) filled the terminal. Without --json
    and without a terminal (output to a file): the first one, then one every 5 minutes. With --json nothing changes
    (tests/test_scarico_pezzi.py: an event at least every 30 s)."""
    prepara(cartella, ogni_s=2)
    sp = scarico_lento(cartella)
    try:
        r = installa(cartella, "--solo-database", "--specchio", sp.url, "--connessioni", "4", json=False)
    finally:
        sp.chiudi()
    assert r.returncode == 0 and "[PMN] Database scaricati e controllati." in r.stdout
    assert len([x for x in r.stdout.splitlines() if x.startswith("[PMN] Scarico i database: ")]) == 1, r.stdout
    assert "\r" not in r.stdout and "\033" not in r.stdout


def con_terminale(cmd, env, secondi=240):
    """Runs cmd with a terminal as output (a pty); returns what it wrote and its exit code."""
    import pty
    padrone, schiavo = pty.openpty()
    p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=schiavo, stderr=subprocess.DEVNULL, env=env,
                         start_new_session=True)
    os.close(schiavo)
    scritto, fine = b"", time.monotonic() + secondi
    while time.monotonic() < fine:
        if select.select([padrone], [], [], 0.5)[0]:
            try:
                pezzo = os.read(padrone, 65536)
            except OSError:                                  # the other side is closed
                break
            if not pezzo:
                break
            scritto += pezzo
        elif p.poll() is not None:
            break
    os.close(padrone)
    return scritto.decode("utf-8"), p.wait(timeout=30)


def test_p10_nel_terminale_la_riga_di_avanzamento_si_aggiorna_sul_posto(cartella):
    """P10: in a terminal the progress line is written again on the same line (carriage return, line cleared, no
    wrapping); every other message clears it and takes its place, so no progress line is left on the screen."""
    prepara(cartella, ogni_s=2)
    sp = scarico_lento(cartella)
    try:
        scritto, rc = con_terminale(comando(cartella, "--solo-database", "--specchio", sp.url, "--connessioni", "4",
                                            json=False), ambiente(cartella / "home"))
    finally:
        sp.chiudi()
    assert rc == 0, scritto
    assert scritto.count("Scarico i database: ") >= 3, scritto
    # what stays on the screen: of every line, what follows the last "clear the line"
    schermo = [riga.split("\r\033[K")[-1] for riga in scritto.split("\r\n")]
    assert not [x for x in schermo if "Scarico i database: " in x], schermo
    assert "[PMN] Database scaricati e controllati." in schermo
    assert scritto.count("\033[?7l") == scritto.count("\033[?7h") == scritto.count("Scarico i database: ")


# ---------------- P3, P7, P8: installer/linux/installa_pmn.sh ----------------
# Fake engine installer: records the folder it runs from and its arguments, and leaves what a finished installation
# leaves (micromamba, installazione.env) and a fake Python of the app that accepts everything and records where it
# runs. PMN_FINTO_ESCE: it stops with that exit code.
MOTORE_FINTO = r'''#!/usr/bin/env bash
set -eu
radice=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$PMN_HOME/bin" "$PMN_HOME/log" "$PMN_HOME/mamba/envs/pmn_app/bin"
echo "$radice $*" >> "$PMN_HOME/motore.chiamate"
echo "${PMN_PROGRAMMA_SOSTITUITO:-0}" >> "$PMN_HOME/motore.sostituito"
[ -z "${PMN_FINTO_ESCE:-}" ] || exit "$PMN_FINTO_ESCE"
for a in "$@"; do [ "$a" != --stima ] || exit 0; done
printf '#!/usr/bin/env bash\nexit 0\n' > "$PMN_HOME/bin/micromamba"
printf '#!/usr/bin/env bash\npwd >> "$PMN_HOME/python.cartelle"\n' > "$PMN_HOME/mamba/envs/pmn_app/bin/python"
chmod +x "$PMN_HOME/bin/micromamba" "$PMN_HOME/mamba/envs/pmn_app/bin/python"
printf 'PMN_ROOT=%s\nPMN_ENVS=%s\n' "$radice" "$PMN_HOME/mamba/envs" > "$PMN_HOME/installazione.env"
'''


@pytest.fixture
def casa():
    d = Path(tempfile.mkdtemp(prefix="pmn_test_", dir=Path.home()))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def scaricata(casa, nome="profilemetananni-main"):
    """The folder as it is downloaded from GitHub and extracted (here on the Desktop), with the fake engine installer."""
    s = casa / "Scrivania" / nome
    (s / "installer" / "linux").mkdir(parents=True)
    shutil.copy(ROOT / "installer" / "linux" / "installa_pmn.sh", s / "installer" / "linux")
    (s / "installer" / "installa_motore.sh").write_text(MOTORE_FINTO, encoding="utf-8")
    for n in ("motore", "bin", "steps", "refs", "docs", "tests"):
        (s / n).mkdir()
        (s / n / "un_file").write_text(n, encoding="utf-8")
    (s / "app" / "risorse").mkdir(parents=True)
    shutil.copy(ROOT / "app" / "requirements.txt", s / "app")
    (s / "app" / "risorse" / "avatar_512.png").write_bytes(b"png")
    (s / "app" / "__pycache__").mkdir()
    (s / "app" / "__pycache__" / "main.pyc").write_bytes(b"x")
    return s


def installa_pmn(casa, cartella, *arg, **altro):
    env = {**ambiente(casa / ".pmn", **altro), "HOME": str(casa), "LANG": "it_IT.UTF-8"}
    return subprocess.run(["bash", str(cartella / "installer" / "linux" / "installa_pmn.sh"), *arg],
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)


def test_p8_il_programma_sta_in_una_cartella_fissa(casa):
    """P8: the command and the menu entry pointed to the folder the installation was launched from (for example
    ~/Scrivania/profilemetananni-main): moved or deleted, the program did not start any more. Now the installer copies
    the program in ~/.pmn/programma, as the Windows one does, and everything runs from there."""
    s = scaricata(casa)
    fissa = casa / ".pmn" / "programma"
    r = installa_pmn(casa, s, "--si")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (casa / ".pmn" / "motore.chiamate").read_text() == f"{fissa} --si\n"          # the engine: from there
    assert (casa / ".pmn" / "python.cartelle").read_text().splitlines()[-1] == str(fissa)   # the app opens from there
    assert sorted(x.name for x in fissa.iterdir()) == ["app", "bin", "installer", "motore", "refs", "steps"]
    assert (fissa / "app" / "requirements.txt").is_file() and not (fissa / "app" / "__pycache__").exists()
    lanciatore = (casa / ".local" / "bin" / "profilemetananni").read_text(encoding="utf-8")
    voce = (casa / ".local" / "share" / "applications" / "profilemetananni.desktop").read_text(encoding="utf-8")
    assert f"cd {fissa} && exec " in lanciatore and str(s) not in lanciatore + voce
    assert f"Icon={fissa}/app/risorse/avatar_512.png\n" in voce
    si_cancella = (f"[PMN] Il programma è installato in {fissa}. La cartella da cui hai lanciato l'installazione "
                   f"({s}) non serve più: puoi cancellarla.")
    assert si_cancella in r.stdout
    # launched again from the same downloaded folder: the same program is not replaced (same folder, same files)
    (fissa / "app" / "__pycache__").mkdir()                  # what Python leaves when the app runs
    prima = (fissa / "motore").stat().st_ino
    r = installa_pmn(casa, s, "--si")
    assert r.returncode == 0 and si_cancella in r.stdout and (fissa / "motore").stat().st_ino == prima
    shutil.rmtree(s)                                         # the downloaded folder is deleted: everything is still there
    assert (fissa / "installer" / "linux" / "installa_pmn.sh").is_file()
    r = installa_pmn(casa, fissa, "--si")                    # launched again from the fixed folder: not copied on itself
    assert r.returncode == 0 and "cancellarla" not in r.stdout and (fissa / "app" / "requirements.txt").is_file()
    assert (casa / ".pmn" / "motore.chiamate").read_text() == f"{fissa} --si\n" * 3
    # an update: the new version, downloaded in another folder, takes the place of the old one, and the engine
    # installer knows it (it will not say "nothing changed" if it stops)
    nuova = scaricata(casa, "profilemetananni-nuova")
    (nuova / "motore" / "un_file").write_text("nuovo", encoding="utf-8")
    r = installa_pmn(casa, nuova, "--si")
    assert r.returncode == 0 and (fissa / "motore" / "un_file").read_text() == "nuovo"
    assert (casa / ".pmn" / "motore.sostituito").read_text().split() == ["0", "0", "0", "1"]
    assert not list((casa / ".pmn").glob("programma.*"))


def test_p8_la_stima_non_copia_nulla(casa):
    s = scaricata(casa)
    r = installa_pmn(casa, s, "--stima")
    assert r.returncode == 0 and not (casa / ".pmn" / "programma").exists()
    assert (casa / ".pmn" / "motore.chiamate").read_text() == f"{s} --stima\n"
    assert not (casa / ".local").exists()


def test_p3_p7_dopo_il_motore_nessuna_frase_in_piu(casa):
    """P3, P7: after an error (2) or an interruption (3) of the engine installer, which has already said what
    happened and what to do, installa_pmn.sh added "Il motore non è ancora installato (codice 3). Quando hai risolto,
    rilancia questo script": false with an engine installed, and without sense after a wanted Ctrl+C."""
    s = scaricata(casa)
    for codice in ("2", "3"):
        r = installa_pmn(casa, s, "--si", PMN_FINTO_ESCE=codice)
        assert r.returncode == int(codice)
        assert righe_pmn(r) == ["[PMN] Installo il motore: programmi e database. Può durare ore; se si interrompe, "
                                "rilancia questo script e riprende."], r.stdout
    r = installa_pmn(casa, s, "--si", PMN_FINTO_ESCE="7")    # stopped without saying why: one line, with the logs
    assert r.returncode == 7 and righe_pmn(r)[1:] == [
        f"[PMN] L'installazione del motore si è fermata (codice 7). Se il motivo non è scritto qui sopra, manda a noi "
        f"i file della cartella {casa / '.pmn' / 'log'}."]
