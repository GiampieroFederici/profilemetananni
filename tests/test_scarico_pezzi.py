# -*- coding: utf-8 -*-
"""v1.1 (R1-R4, D165, D166, D170): download in pieces with Range, sources in parallel, archives extracted while they
arrive with the MD5 in the same pass, one space rule, estimate per source and an event at least every 30 s.
Against the "difficult" local mirror (tests/specchio_server.py). Linux/WSL only, like the installer:
  wsl -d Ubuntu  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_scarico_pezzi.py"""
import hashlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from contratto import controlla
from specchio_server import Specchio

pytestmark = pytest.mark.skipif(sys.platform != "linux" or not shutil.which("bash"),
                                reason="installa_motore.sh runs on Linux/WSL only")
ROOT = Path(__file__).resolve().parent.parent
TESTA = "gruppo\ttipo\tsorgente\tpercorso\tbyte\tbyte_finale\tmd5\tdestinazione\n"
MB = 1024 * 1024


@pytest.fixture
def cartella():
    """On disk, not in /tmp (RAM in WSL). A copy of installer/ so a test group can have its md5/<group>.md5."""
    d = Path(tempfile.mkdtemp(prefix="pmn_test_", dir=Path.home()))
    shutil.copytree(ROOT / "installer", d / "radice" / "installer", ignore=shutil.ignore_patterns("finto", "windows"))
    (d / "servito").mkdir()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def md5(dati):
    return hashlib.md5(dati).hexdigest()


def servi(cartella, sorgente, percorso, dati):
    f = cartella / "servito" / sorgente / percorso
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(dati)


def archivio(cartella, gruppo, nfile, mb):
    """A .tar.gz of random (incompressible) files; writes installer/md5/<gruppo>.md5. Returns (bytes, extracted bytes)."""
    buf = io.BytesIO()
    righe, estratto = [], 0
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=1) as t:
        for i in range(nfile):
            dati = os.urandom(mb * MB)
            info = tarfile.TarInfo(f"f{i}.k2d")
            info.size = len(dati)
            t.addfile(info, io.BytesIO(dati))
            righe.append(f"{md5(dati)}  f{i}.k2d\n")
            estratto += len(dati)
    (cartella / "radice" / "installer" / "md5" / f"{gruppo}.md5").write_text("".join(righe), encoding="utf-8")
    return buf.getvalue(), estratto


def catalogo(cartella, righe, nome="catalogo.tsv"):
    c = cartella / nome
    c.write_text(TESTA + "".join("\t".join(str(x) for x in r) + "\n" for r in righe), encoding="utf-8")
    return c


def avvia(cartella, url, *arg, stima=False):
    home = cartella / "home"
    env = {**os.environ, "PMN_HOME": str(home)}
    env.pop("PMN_URL_PACCHETTI", None)
    env.pop("PMN_CONNESSIONI", None)
    cmd = ["bash", str(cartella / "radice" / "installer" / "installa_motore.sh"), "--json", "--catalogo",
           str(cartella / "catalogo.tsv"), "--specchio", url, *arg]
    cmd += ["--stima"] if stima else ["--si", "--solo-database"]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                            text=True, encoding="utf-8", env=env)


def lancia(cartella, url, *arg, stima=False, timeout=600):
    p = avvia(cartella, url, *arg, stima=stima)
    out, _ = p.communicate(timeout=timeout)
    return controlla(out, p.returncode, "installa"), p.returncode


def ora(e):
    return datetime.fromisoformat(e["ora"]).timestamp()


def misura(a, z, b, n):
    """The speed test before downloading: 8 MiB from the start of each of the n parts of the file."""
    return a in {b * k // n for k in range(n)} and z == min(a + 8 * MB - 1, b - 1)


def durata_database(ev):
    db = [e for e in ev if e.get("passo") == "database"]
    return ora(ev[-1]) - ora(db[0])


# ---------------- R1: pieces in parallel ----------------
def test_otto_connessioni_circa_otto_volte_piu_veloci(cartella):
    """200 MB, 1,5 MB/s per connection: one connection would take ~133 s; with 8 pieces at once ~17 s."""
    dati = os.urandom(200 * MB)
    servi(cartella, "kraken", "grande.bin", dati)
    catalogo(cartella, [("kraken_prova", "file", "kraken", "grande.bin", len(dati), len(dati), md5(dati), "kraken/grande.bin")])
    sp = Specchio(cartella / "servito", velocita={"/kraken/": int(1.5 * MB)})
    try:
        ev, rc = lancia(cartella, sp.url, "--connessioni", "8")
    finally:
        sp.chiudi()
    assert rc == 0 and ev[-1]["esito"] == "ok"
    assert md5((cartella / "home" / "db" / "kraken" / "grande.bin").read_bytes()) == md5(dati)
    velocita = len(dati) / durata_database(ev)
    print(f"\n8 connessioni: {velocita / MB:.1f} MB/s = {velocita / (1.5 * MB):.1f} volte una connessione")
    assert velocita > 6 * 1.5 * MB
    assert not list((cartella / "home" / "db" / "kraken").glob("grande.bin.*"))      # pieces gone


def test_kill_a_meta_e_ripresa_senza_riscaricare_i_pezzi_completi(cartella):
    dati = os.urandom(200 * MB)
    servi(cartella, "kraken", "grande.bin", dati)
    catalogo(cartella, [("kraken_prova", "file", "kraken", "grande.bin", len(dati), len(dati), md5(dati), "kraken/grande.bin")])
    sp = Specchio(cartella / "servito", velocita={"/kraken/": 2 * MB})
    base = cartella / "home" / "db" / "kraken" / "grande.bin"
    try:
        p = avvia(cartella, sp.url, "--connessioni", "8")
        time.sleep(8)                                        # about half
        os.killpg(p.pid, signal.SIGKILL)                     # as a PC switched off: no trap, nothing tidied up
        p.wait()
        pezzi = [tuple(map(int, r.split())) for r in Path(f"{base}.pezzi").read_text().splitlines()]
        completi = [(a, z) for i, (a, z) in enumerate(pezzi)
                    if Path(f"{base}.pezzo.{i}").exists() and Path(f"{base}.pezzo.{i}").stat().st_size == z - a + 1]
        assert 0 < len(completi) < len(pezzi)
        prima = len(sp.richieste)
        ev, rc = lancia(cartella, sp.url, "--connessioni", "8")
        dopo = [(a, z) for _, a, z, c in sp.richieste[prima:]                   # (0, 0): the Range probe
                if (a, z) != (0, 0) and not misura(a, z, len(dati), 8)]
    finally:
        sp.chiudi()
    assert rc == 0 and md5(base.read_bytes()) == md5(dati)
    assert not [r for r in dopo for (a, z) in completi if a <= r[0] <= z]           # no complete piece asked again
    scaricati = sum(z - a + 1 for a, z in dopo)
    print(f"\nripresa: {len(completi)} pezzi completi tenuti, riscaricati {scaricati / MB:.0f} MB su 200")
    assert scaricati <= len(dati) - sum(z - a + 1 for a, z in completi)


def test_il_parziale_della_v1_0_diventa_il_primo_pezzo(cartella):
    dati = os.urandom(40 * MB)
    servi(cartella, "kraken", "x.bin", dati)
    catalogo(cartella, [("kraken_prova", "file", "kraken", "x.bin", len(dati), len(dati), md5(dati), "kraken/x.bin")])
    f = cartella / "home" / "db" / "kraken" / "x.bin.parziale"
    f.parent.mkdir(parents=True)
    f.write_bytes(dati[:30 * MB])                          # v1.0: one sequential download, stopped at 30 MB
    sp = Specchio(cartella / "servito")
    try:
        ev, rc = lancia(cartella, sp.url, "--connessioni", "4")
    finally:
        sp.chiudi()
    assert rc == 0 and md5((cartella / "home" / "db" / "kraken" / "x.bin").read_bytes()) == md5(dati)
    scarico = [(a, z) for _, a, z, c in sp.richieste if (a, z) != (0, 0) and not misura(a, z, len(dati), 4)]
    assert scarico and all(a >= 30 * MB for a, z in scarico)


def test_server_senza_range_una_connessione_come_prima(cartella):
    dati = os.urandom(20 * MB)
    servi(cartella, "kraken", "x.bin", dati)
    catalogo(cartella, [("kraken_prova", "file", "kraken", "x.bin", len(dati), len(dati), md5(dati), "kraken/x.bin")])
    sp = Specchio(cartella / "servito", senza_range=("/kraken/",))
    try:
        ev, rc = lancia(cartella, sp.url, "--connessioni", "8")
    finally:
        sp.chiudi()
    assert rc == 0 and md5((cartella / "home" / "db" / "kraken" / "x.bin").read_bytes()) == md5(dati)
    assert {c for *_, c in sp.richieste} == {200}
    # two probes (speed test, then download) and the speed test (Range ignored: whole file) + one download
    assert sum(1 for _, a, z, c in sp.richieste if z - a + 1 == len(dati)) == 4


def test_connessione_che_cade_a_meta_riprende_da_sola(cartella):
    dati = os.urandom(20 * MB)
    servi(cartella, "kraken", "x.bin", dati)
    catalogo(cartella, [("kraken_prova", "file", "kraken", "x.bin", len(dati), len(dati), md5(dati), "kraken/x.bin")])
    sp = Specchio(cartella / "servito", cadute={"/kraken/": 12})   # probes and speed test take the first ones
    try:
        ev, rc = lancia(cartella, sp.url, "--connessioni", "4")
    finally:
        sp.chiudi()
    assert rc == 0 and md5((cartella / "home" / "db" / "kraken" / "x.bin").read_bytes()) == md5(dati)
    assert any(e["tipo"] == "avviso" and e["codice"] == "RETE_INTERROTTA" for e in ev)


def test_md5_sbagliato_si_riscarica_una_volta_poi_si_ferma(cartella):
    tgz, estratto = archivio(cartella, "kraken_prova", 2, 4)
    servi(cartella, "kraken", "a.tar.gz", tgz)
    catalogo(cartella, [("kraken_prova", "tar", "kraken", "a.tar.gz", len(tgz), estratto, "0" * 32, "kraken/a")])
    sp = Specchio(cartella / "servito")
    try:
        ev, rc = lancia(cartella, sp.url, "--connessioni", "4")
    finally:
        sp.chiudi()
    assert rc == 2 and ev[-2]["codice"] == "DB_ROVINATO" and "manda a noi" in ev[-2]["cosa_fare"]
    assert not (cartella / "home" / "db" / "kraken" / "a").exists()                  # extracted folder removed
    assert not list((cartella / "home" / "tmp").glob("a.tar.gz*"))                 # pieces removed: next time from scratch
    scaricati = sum(z - a + 1 for _, a, z, c in sp.richieste if (a, z) != (0, 0) and not misura(a, z, len(tgz), 4))
    assert scaricati == 2 * len(tgz)                                                 # downloaded twice


def test_url_alternativo_divide_i_pezzi_fra_le_sorgenti(cartella):
    """D166: optional column url_alternativo; the pieces go to both sources."""
    dati = os.urandom(16 * MB)
    servi(cartella, "kraken", "x.bin", dati)
    servi(cartella, "copia", "x.bin", dati)
    sp = Specchio(cartella / "servito")
    c = catalogo(cartella, [("kraken_prova", "file", "kraken", "x.bin", len(dati), len(dati), md5(dati), "kraken/x.bin",
                             f"{sp.url}/copia/x.bin")])
    assert c.read_text().splitlines()[1].count("\t") == 8
    try:
        ev, rc = lancia(cartella, sp.url, "--connessioni", "4")
    finally:
        sp.chiudi()
    assert rc == 0 and md5((cartella / "home" / "db" / "kraken" / "x.bin").read_bytes()) == md5(dati)
    assert {r[0].split("/")[1] for r in sp.richieste} == {"kraken", "copia"}


# ---------------- R3: extraction from the stream, peak on disk ----------------
def test_archivio_estratto_mentre_arriva_picco_senza_archivio_intero(cartella):
    """Little space: every piece is deleted as soon as tar has read it. Measured peak on disk (pieces + extracted)
    never holds the whole archive and the extracted files together."""
    tgz, estratto = archivio(cartella, "kraken_prova", 3, 40)
    servi(cartella, "kraken", "a.tar.gz", tgz)
    catalogo(cartella, [("kraken_prova", "tar", "kraken", "a.tar.gz", len(tgz), estratto, md5(tgz), "kraken/a")])
    sp = Specchio(cartella / "servito", velocita={"/kraken/": 3 * MB})
    home = cartella / "home"
    picco, fine = [0], threading.Event()

    def misura():
        while not fine.is_set():
            n = 0
            for d in (home / "tmp", home / "db"):
                for r, _, fs in os.walk(d):
                    for f in fs:
                        try:
                            n += os.path.getsize(os.path.join(r, f))
                        except OSError:
                            pass
            picco[0] = max(picco[0], n)
            time.sleep(0.05)

    t = threading.Thread(target=misura)
    t.start()
    try:   # enough for the extracted files and a few pieces, not for the whole archive too
        ev, rc = lancia(cartella, sp.url, "--connessioni", "4", "--spazio-libero", str(estratto + len(tgz) // 2))
    finally:
        fine.set()
        t.join()
        sp.chiudi()
    assert rc == 0 and ev[-1]["esito"] == "ok"
    assert any("cancello ogni pezzo appena letto" in e["messaggio"] for e in ev)
    print(f"\npicco {picco[0] / MB:.0f} MB; archivio {len(tgz) / MB:.0f} MB + estratto {estratto / MB:.0f} MB")
    assert picco[0] < estratto + 0.5 * len(tgz)
    assert sorted(p.name for p in (home / "db" / "kraken" / "a").iterdir()) == ["f0.k2d", "f1.k2d", "f2.k2d"]
    assert not list((home / "tmp").glob("a.tar.gz*"))


def test_archivio_con_spazio_i_pezzi_restano_fino_all_md5(cartella):
    """Enough space: the pieces stay until the MD5 is right (a stop during extraction does not download again)."""
    tgz, estratto = archivio(cartella, "kraken_prova", 2, 8)
    servi(cartella, "kraken", "a.tar.gz", tgz)
    catalogo(cartella, [("kraken_prova", "tar", "kraken", "a.tar.gz", len(tgz), estratto, md5(tgz), "kraken/a")])
    sp = Specchio(cartella / "servito")
    try:
        ev, rc = lancia(cartella, sp.url, "--connessioni", "4")
    finally:
        sp.chiudi()
    assert rc == 0 and not any("cancello ogni pezzo" in e["messaggio"] for e in ev)
    assert (cartella / "home" / "stato" / "kraken__a.ok").read_text().strip() == md5(tgz)


# ---------------- R2 + R4: two sources together, estimate per source, events every 30 s at most ----------------
def test_due_sorgenti_insieme_stima_entro_30_per_cento_ed_eventi_ogni_30_s(cartella):
    tgz, estratto = archivio(cartella, "kraken_prova", 1, 24)
    servi(cartella, "kraken", "a.tar.gz", tgz)
    righe = [("kraken_prova", "tar", "kraken", "a.tar.gz", len(tgz), estratto, md5(tgz), "kraken/a")]
    for i in range(2):
        d = os.urandom(12 * MB)
        servi(cartella, "pmn", f"p/f{i}.bin", d)
        righe.append(("pacchetti", "file", "pmn", f"p/f{i}.bin", len(d), len(d), md5(d), f"p/f{i}.bin"))
    catalogo(cartella, righe)
    sp = Specchio(cartella / "servito", velocita={"/kraken/": 150_000, "/pmn/": 300_000})
    try:
        ev, rc = lancia(cartella, sp.url, "--connessioni", "4", stima=True)
        assert rc == 0
        stima = ev[-1]["risultato"]
        ev, rc = lancia(cartella, sp.url, "--connessioni", "4")
    finally:
        sp.chiudi()
    assert rc == 0 and ev[-1]["esito"] == "ok"
    vero = durata_database(ev)
    print(f"\nstima {stima['tempo_stimato_s']} s, vero {vero:.0f} s; sorgenti {stima['sorgenti']}")
    assert abs(stima["tempo_stimato_s"] - vero) <= 0.3 * vero
    assert {s["sorgente"] for s in stima["sorgenti"]} == {"kraken", "pmn"}
    assert all(s["velocita_mb_s"] and s["tempo_stimato_s"] for s in stima["sorgenti"])
    db = [e for e in ev if e.get("passo") == "database" or e["tipo"] == "fine"]
    salti = [ora(b) - ora(a) for a, b in zip(db, db[1:])]
    assert max(salti) <= 30, salti
    periodici = [e for e in ev if e["tipo"] == "avanzamento" and "byte_fatti" in e]
    assert len(periodici) >= 3
    e = periodici[-1]
    assert e["byte_totali"] == len(tgz) + 24 * MB and 0 <= e["byte_fatti"] <= e["byte_totali"]
    assert {s["sorgente"] for s in e["sorgenti"]} == {"kraken", "pmn"}
    pct = [e["percentuale"] for e in ev if e["tipo"] == "avanzamento" and e["passo"] == "database"]
    assert pct == sorted(pct)
    # both sources really at the same time: the pmn files started before the archive was finished
    t = [(r[0], i) for i, r in enumerate(sp.richieste)]
    assert min(i for p, i in t if p.startswith("/pmn/")) < max(i for p, i in t if p.startswith("/kraken/"))


# ---------------- R6: nobody reads the events any more ----------------
def test_senza_nessuno_che_legge_il_motore_non_resta_a_scaricare(cartella):
    dati = os.urandom(40 * MB)
    servi(cartella, "kraken", "x.bin", dati)
    catalogo(cartella, [("kraken_prova", "file", "kraken", "x.bin", len(dati), len(dati), md5(dati), "kraken/x.bin")])
    sp = Specchio(cartella / "servito", velocita={"/kraken/": 200_000})
    try:
        p = avvia(cartella, sp.url, "--connessioni", "4")
        while "Scarico kraken_prova" not in p.stdout.readline():
            pass
        p.stdout.close()                                     # the Windows window was closed by force
        fine = time.monotonic() + 40
        while time.monotonic() < fine:
            try:
                os.killpg(p.pid, 0)
            except ProcessLookupError:
                break
            p.poll()
            time.sleep(0.5)
        else:
            os.killpg(p.pid, signal.SIGKILL)
            pytest.fail("processi rimasti dopo 40 s")
    finally:
        sp.chiudi()


# ---------------- R3: one space rule, about 80 GB less; D170 catalogue for the VM ----------------
def dim_pezzo(b, c):
    d = (b + 8 * c - 1) // (8 * c)
    return min(max(d, MB), 128 * MB)


def regola(righe, conn=16):
    """The rule of installa_motore.sh: final bytes + a few pieces of the biggest archive + 16 GB of programs."""
    fin = sum(int(r[5]) for r in righe)
    margine = max([min(int(r[4]), 2 * conn * dim_pezzo(int(r[4]), conn)) for r in righe if r[1] == "tar"] or [0])
    return fin + margine + 16 * 10**9


def stima_catalogo(cartella, righe):
    catalogo(cartella, righe)
    ev, rc = lancia(cartella, "http://127.0.0.1:9", stima=True)
    assert rc == 0
    return ev[-1]["risultato"]


def test_spazio_circa_80_gb_in_meno_con_il_catalogo_vero(cartella):
    righe = [r.split("\t") for r in (ROOT / "installer" / "catalogo.tsv").read_text().splitlines()[1:]]
    r = stima_catalogo(cartella, righe)
    vecchio = sum(int(x[5]) for x in righe) + max(int(x[4]) for x in righe if x[1] == "tar") + 16 * 10**9
    print(f"\nspazio: prima {vecchio / 2**30:.0f} GB, ora {r['spazio_necessario_byte'] / 2**30:.0f} GB")
    assert r["spazio_necessario_byte"] == regola(righe)
    assert 75 * 2**30 < vecchio - r["spazio_necessario_byte"] < 90 * 2**30
    assert r["spazio_necessario_gb"] == round(r["spazio_necessario_byte"] / 2**30, 1)


def test_d170_catalogo_della_vm_senza_kraken_completo(cartella):
    """D170: prova.conf with only "catalogo=installer/catalogo_vm.tsv": real sources, everything but kraken_completo.
    The space rule and the per-source estimate follow that catalogue."""
    righe = [r.split("\t") for r in (ROOT / "installer" / "catalogo.tsv").read_text().splitlines()[1:]]
    vm = [r for r in righe if r[0] != "kraken_completo"]
    r = stima_catalogo(cartella, vm)
    assert r["spazio_necessario_byte"] == regola(vm)
    kraken = next(s for s in r["sorgenti"] if s["sorgente"] == "kraken")
    assert kraken["da_scaricare_gb"] == round(int(next(x for x in vm if x[0] == "kraken_rapido")[4]) / 2**30, 1)


def test_opzioni_non_valide_si_fermano_subito(cartella):
    catalogo(cartella, [])
    for arg in (["--connessioni", "0"], ["--connessioni", "1;ls"], ["--spazio-libero", "tanto"]):
        p = avvia(cartella, "http://127.0.0.1:9", *arg, stima=True)
        out, _ = p.communicate(timeout=30)
        assert p.returncode == 1 and out == ""
