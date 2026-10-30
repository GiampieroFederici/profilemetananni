# -*- coding: utf-8 -*-
"""VELOCITA (R10, PMN 1.1, 30/10/2026): accelerazioni misurate dell'analisi, senza cambiare i risultati.

Le misure prima/dopo sono in implementazione/v1.1/velocita/ (privata). Qui il comportamento nuovo degli script:
- steps/20_trim.sh: FastQC 0.13.0 con più file in una sola chiamata li legge uno dopo l'altro su un solo core
  (misura del 30/10: 4 file di SF3RAt7 in 2 min 05 s, 0,77 core); un FastQC per file, insieme, fino a --threads; e
  legge a pezzi piccoli, lentissimo da /mnt/c (84 s contro 18 s per un file): i file su v9fs si copiano in TMPDIR.
- steps/32_kraken_bracken.sh: database piu' grande della RAM, 4 thread per processore (Kraken aspetta il disco).
- motore/metaphlan_fette.sh: read preparate e file delle fette in PMN_TMP, non nella cartella del progetto.
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_velocita.py"""
import gzip
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="steps/*.sh: Linux/WSL only")

FASTP = """#!/usr/bin/env bash
while [ $# -gt 0 ]; do case "$1" in -o|-O) cp "$IN" "$2"; shift 2;; -i) IN="$2"; shift 2;; --json|--html) echo '{}' > "$2"; shift 2;; *) shift;; esac; done
"""
# fastqc finto come lo 0.13.0 (--outdir, -t): annota quanti FastQC girano insieme e quanti file riceve ognuno
FASTQC = """#!/usr/bin/env python3
import argparse, glob, os, time
a = argparse.ArgumentParser(prog="fastqc")
a.add_argument("--outdir"); a.add_argument("-t", "--threads"); a.add_argument("-q", "--quiet", action="store_true")
a.add_argument("files", nargs="*")
o = a.parse_args()
d = os.environ["TRACCIA"]
mio = os.path.join(d, f"in_corso.{os.getpid()}")
open(mio, "w").close()
time.sleep(0.6)
with open(os.path.join(d, "chiamate.txt"), "a") as f:
    f.write(f"{len(o.files)} {len(glob.glob(os.path.join(d, 'in_corso.*')))}\\n")
with open(os.path.join(d, "file.txt"), "a") as f:
    f.write("".join(p + "\\n" for p in o.files))
for p in o.files:
    assert os.path.getsize(p) > 0
    b = os.path.basename(p).removesuffix(".gz").removesuffix(".fastq").removesuffix(".fq")
    open(os.path.join(o.outdir, b + "_fastqc.html"), "w").write("<html></html>")
os.remove(mio)
"""


def prepara(tmp_path, raw=None):
    b = tmp_path / "bin"
    b.mkdir()
    for nome, testo in (("fastp", FASTP), ("fastqc", FASTQC)):
        (b / nome).write_text(testo, encoding="utf-8")
        (b / nome).chmod(0o755)
    raw = raw or tmp_path / "raw"
    raw.mkdir(exist_ok=True)
    for i in (1, 2):
        with gzip.open(raw / f"S1_{i}.fastq.gz", "wt") as f:
            f.write(f"@r/{i}\n{'ACGT' * 25}\n+\n{'I' * 100}\n")
    (tmp_path / "traccia").mkdir()
    return b, raw


def trim(tmp_path, threads, raw=None, out=None):
    b, raw = prepara(tmp_path, raw)
    (tmp_path / "tmpdir").mkdir()
    p = subprocess.run(["bash", str(RADICE / "steps" / "20_trim.sh"), "--sample", "S1", "--in1", str(raw / "S1_1.fastq.gz"),
                        "--in2", str(raw / "S1_2.fastq.gz"), "--out", str(out or tmp_path / "trim"), "--threads", str(threads)],
                       capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{b}:{os.environ['PATH']}", "NO_COLOR": "1",
                            "TRACCIA": str(tmp_path / "traccia"), "TMPDIR": str(tmp_path / "tmpdir")})
    righe = (tmp_path / "traccia" / "chiamate.txt").read_text().split("\n")
    return p, [tuple(int(x) for x in r.split()) for r in righe if r]


@linux
def test_fastqc_un_file_per_chiamata_tutti_insieme(tmp_path):
    p, chiamate = trim(tmp_path, 8)
    assert p.returncode == 0, p.stdout + p.stderr
    assert len(chiamate) == 4 and all(n == 1 for n, _ in chiamate)    # un file per FastQC
    assert max(c for _, c in chiamate) == 4                            # i 4 FastQC girano insieme
    assert len(list((tmp_path / "trim").glob("*_fastqc.html"))) == 4


@linux
def test_fastqc_non_piu_dei_processori_chiesti(tmp_path):
    p, chiamate = trim(tmp_path, 1)
    assert p.returncode == 0, p.stdout + p.stderr
    assert len(chiamate) == 4 and max(c for _, c in chiamate) == 1    # --threads 1: uno alla volta


def tipo_fs(p):
    return subprocess.run(["stat", "-f", "-c", "%T", str(p)], capture_output=True, text=True).stdout.strip()


@linux
def test_fastqc_legge_dal_disco_della_wsl_non_da_windows(tmp_path):
    """Read e cartella di lavoro su /mnt/c (v9fs, come il progetto dell'app): FastQC riceve copie in TMPDIR, che alla
    fine non restano. Sul disco della WSL (ext4) nessuna copia."""
    if tipo_fs(RADICE) != "v9fs":
        pytest.skip("serve la cartella del codice su /mnt/c (WSL di sviluppo)")
    win = Path(tempfile.mkdtemp(dir=RADICE / "tests", prefix="_prova_v9fs_"))
    try:
        p, _ = trim(tmp_path, 8, raw=win / "raw", out=win / "trim")
        assert p.returncode == 0, p.stdout + p.stderr
        usati = (tmp_path / "traccia" / "file.txt").read_text().split()
        assert len(usati) == 4 and all(u.startswith(str(tmp_path / "tmpdir") + "/pmn_fqc_S1.") for u in usati), usati
        assert sorted(f.name for f in (win / "trim").glob("*_fastqc.html")) == \
            ["S1_1_fastqc.html", "S1_2_fastqc.html", "S1_trim_1_fastqc.html", "S1_trim_2_fastqc.html"]
        assert list((tmp_path / "tmpdir").iterdir()) == []
    finally:
        shutil.rmtree(win)


@linux
def test_fastqc_senza_copie_sul_disco_della_wsl(tmp_path):
    if tipo_fs(tmp_path) == "v9fs":
        pytest.skip("tmp su v9fs")
    p, _ = trim(tmp_path, 8)
    assert p.returncode == 0, p.stdout + p.stderr
    assert all(u.startswith(str(tmp_path / "raw")) or u.startswith(str(tmp_path / "trim"))
               for u in (tmp_path / "traccia" / "file.txt").read_text().split())


# --- steps/32_kraken_bracken.sh: database piu' grande della RAM = Kraken aspetta il disco, piu' thread ---
KRAKEN2 = """#!/usr/bin/env bash
printf "%s\\n" "$@" > "$TRACCIA/kraken2.txt"
while [ $# -gt 0 ]; do [ "$1" = --report ] && : > "$2"; shift; done
"""
BRACKEN = """#!/usr/bin/env bash
while [ $# -gt 0 ]; do [ "$1" = -o ] && echo fatto > "$2"; shift; done
"""


def thread_di_kraken(tmp_path, hash_byte):
    b, db, tr = tmp_path / "bin", tmp_path / "db", tmp_path / "traccia"
    for d in (b, db, tr):
        d.mkdir()
    for nome, testo in (("kraken2", KRAKEN2), ("bracken", BRACKEN)):
        (b / nome).write_text(testo, encoding="utf-8")
        (b / nome).chmod(0o755)
    with open(db / "hash.k2d", "wb") as f:   # file sparso: la dimensione conta, il disco no
        f.truncate(hash_byte)
    (tmp_path / "r1.fq.gz").write_bytes(gzip.compress(b"@r\nACGT\n+\nIIII\n"))
    p = subprocess.run(["bash", str(RADICE / "steps" / "32_kraken_bracken.sh"), "--sample", "S1", "--in1",
                        str(tmp_path / "r1.fq.gz"), "--db", str(db), "--out", str(tmp_path / "out"), "--confidence", "0.5",
                        "--threads", "8"], capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{b}:{os.environ['PATH']}", "NO_COLOR": "1", "PMN_LANG": "en",
                            "TRACCIA": str(tr)})
    assert p.returncode == 0, p.stdout + p.stderr
    a = (tr / "kraken2.txt").read_text().split("\n")
    return int(a[a.index("--threads") + 1])


def ram_byte():
    with open("/proc/meminfo") as f:
        return int(next(r for r in f if r.startswith("MemTotal:")).split()[1]) * 1024


@linux
def test_kraken_database_piu_grande_della_ram_quattro_thread_per_processore(tmp_path):
    assert thread_di_kraken(tmp_path, ram_byte() + 1024 ** 3) == 32


@linux
def test_kraken_database_che_sta_in_ram_thread_chiesti(tmp_path):
    assert thread_di_kraken(tmp_path, 1024 ** 2) == 8


# --- motore/metaphlan_fette.sh: file di passaggio in PMN_TMP (disco della WSL), non nella cartella del progetto ---
READ_FASTX = """#!/usr/bin/env bash
printf '@r1__1\\nACGT\\n+\\nIIII\\n'
echo "2 100.0 0" >&2
"""
# bowtie2 finto: annota il file delle read, controlla che esista, scrive un SAM con una read allineata
BOWTIE2 = """#!/usr/bin/env bash
while [ $# -gt 0 ]; do case "$1" in -U) U="$2"; shift 2;; -S) SAM="$2"; shift 2;; -x) X="$2"; shift 2;; *) shift;; esac; done
[ -s "$U" ] || exit 7
echo "$U" >> "$TRACCIA/read_usate.txt"
n="${X##*fetta}"
printf '@HD\\tVN:1.0\\nr1__1\\t0\\tGeneID:%s\\t1\\t42\\t4M\\t*\\t0\\t0\\tACGT\\tIIII\\tAS:i:0\\n' "$n" > "$SAM"
"""
# python di pmn_metaphlan finto (metaphlan_mapout.py): scrive il profilo dopo "-o"
MPA_PY = """#!/usr/bin/env bash
while [ $# -gt 0 ]; do [ "$1" = -o ] && echo profilo > "$2"; shift; done
"""


@linux
def test_fette_file_di_passaggio_fuori_dal_progetto(tmp_path):
    envs, tmp, out, tr = tmp_path / "envs", tmp_path / "pmn_tmp", tmp_path / "progetto" / "metaphlan", tmp_path / "traccia"
    for d in (envs / "pmn_metaphlan" / "bin", envs / "pmn_reports_py" / "bin", tmp, tr):
        d.mkdir(parents=True)
    for nome, testo in (("read_fastx.py", READ_FASTX), ("bowtie2", BOWTIE2), ("python", MPA_PY)):
        f = envs / "pmn_metaphlan" / "bin" / nome
        f.write_text(testo, encoding="utf-8")
        f.chmod(0o755)
    (envs / "pmn_reports_py" / "bin" / "python").symlink_to(shutil.which("python3"))   # l'arbitro vero
    (tmp_path / "home").mkdir()
    (tmp_path / "home" / "installazione.env").write_text(
        f"PMN_ENVS={envs}\nPMN_FETTE={tmp_path / 'fette'}\nPMN_MPA_DB={tmp_path / 'db'}\nPMN_TMP={tmp}\n", encoding="utf-8")
    p = subprocess.run(["bash", str(RADICE / "motore" / "metaphlan_fette.sh"), "C1", "r1.fq.gz", "", str(out), "2"],
                       capture_output=True, text=True,
                       env={**os.environ, "PMN_HOME": str(tmp_path / "home"), "TRACCIA": str(tr)})
    assert p.returncode == 0, p.stdout + p.stderr
    usate = (tr / "read_usate.txt").read_text().split()
    assert len(usate) == 6 and all(Path(u).parent.parent == tmp for u in usate), usate   # read preparate in PMN_TMP
    assert sorted(f.name for f in out.iterdir()) == ["C1.mapout", "C1_profile.txt"]      # nel progetto solo le uscite
    assert list(tmp.iterdir()) == []                                                      # passaggio tolto alla fine
    assert (out / "C1.mapout").read_text().startswith("r1__1\tGeneID:1\n")
