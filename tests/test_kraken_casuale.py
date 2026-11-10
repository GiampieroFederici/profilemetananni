# -*- coding: utf-8 -*-
"""Kraken con letture casuali dichiarate al kernel (PMN 1.3, 10/11/2026).

motore/pmn_casuale.c, compilata dall'installatore in $PMN_HOME/lib/pmn_casuale.so, si mette davanti a Kraken
(LD_PRELOAD) quando il database è più grande della memoria: il kernel legge solo la pagina chiesta, senza lettura
anticipata. Kraken non cambia (report identico al byte: implementazione/validazione/V13_8gb_linux).
Gira con la suite del motore nella WSL di sviluppo:
  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_kraken_casuale.py"""
import glob
import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_velocita import BRACKEN, linux, ram_byte

RADICE = Path(__file__).resolve().parent.parent
# kraken2 finto: annota la libreria che gli sta davanti e scrive un report vuoto
KRAKEN2 = """#!/usr/bin/env bash
printf '%s' "${LD_PRELOAD:-}" > "$TRACCIA/preload.txt"
while [ $# -gt 0 ]; do [ "$1" = --report ] && : > "$2"; shift; done
"""


def davanti_a_kraken(tmp_path, hash_byte, libreria=True, **env):
    """LD_PRELOAD con cui 32_kraken_bracken.sh lancia kraken2 (finto)."""
    b, db, tr, casa = tmp_path / "bin", tmp_path / "db", tmp_path / "traccia", tmp_path / "pmn"
    for d in (b, db, tr, casa / "lib"):
        d.mkdir(parents=True)
    for nome, testo in (("kraken2", KRAKEN2), ("bracken", BRACKEN)):
        (b / nome).write_text(testo, encoding="utf-8")
        (b / nome).chmod(0o755)
    with open(db / "hash.k2d", "wb") as f:   # file sparso: la dimensione conta, il disco no
        f.truncate(hash_byte)
    if libreria:
        (casa / "lib" / "pmn_casuale.so").write_bytes(b"finta")
    (tmp_path / "r1.fq.gz").write_bytes(gzip.compress(b"@r\nACGT\n+\nIIII\n"))
    p = subprocess.run(["bash", str(RADICE / "steps" / "32_kraken_bracken.sh"), "--sample", "S1", "--in1",
                        str(tmp_path / "r1.fq.gz"), "--db", str(db), "--out", str(tmp_path / "out"), "--confidence", "0.5",
                        "--threads", "8"], capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{b}:{os.environ['PATH']}", "NO_COLOR": "1", "PMN_LANG": "en",
                            "TRACCIA": str(tr), "PMN_HOME": str(casa), **env})
    assert p.returncode == 0, p.stdout + p.stderr
    return (tr / "preload.txt").read_text(), str(casa / "lib" / "pmn_casuale.so")


@linux
def test_database_piu_grande_della_ram_kraken_parte_con_la_libreria(tmp_path):
    visto, libreria = davanti_a_kraken(tmp_path, ram_byte() + 1024 ** 3)
    assert visto == libreria


@linux
@pytest.mark.parametrize("caso", ["sta_in_ram", "senza_libreria", "spenta"])
def test_negli_altri_casi_kraken_parte_come_nella_1_2(tmp_path, caso):
    grande = ram_byte() + 1024 ** 3
    if caso == "sta_in_ram":          # database che sta in memoria: la lettura anticipata aiuta a caricarlo
        visto, _ = davanti_a_kraken(tmp_path, 1024 ** 2)
    elif caso == "senza_libreria":    # installazione senza compilatore
        visto, _ = davanti_a_kraken(tmp_path, grande, libreria=False)
    else:                             # PMN_CASUALE=no: la via di prima, per i confronti
        visto, _ = davanti_a_kraken(tmp_path, grande, PMN_CASUALE="no")
    assert visto == ""


def compilatore():
    for c in glob.glob("/home/pmn/.pmn/mamba/envs/*/bin/x86_64-conda-linux-gnu-gcc") + [shutil.which("gcc"), shutil.which("cc")]:
        if c:
            return c
    return None


MAPPA = """import mmap, sys
with open(sys.argv[1], "rb") as f:
    m = mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ)
    dentro = False
    for riga in open("/proc/self/smaps"):
        if riga.rstrip().endswith(sys.argv[1]):
            dentro = True
        elif dentro and riga.startswith("VmFlags:"):
            print(riga.split(":", 1)[1].strip())
            break
"""


@linux
@pytest.mark.skipif(compilatore() is None, reason="nessun compilatore C (gcc di un ambiente del motore o del sistema)")
def test_la_libreria_vera_segna_come_casuali_solo_i_file_grandi(tmp_path):
    """Compilata come fa l'installatore: un file mappato di 2 GB prende il segno "rr" (MADV_RANDOM), uno piccolo no;
    senza la libreria nessuno dei due."""
    so = tmp_path / "pmn_casuale.so"
    subprocess.run([compilatore(), "-shared", "-fPIC", "-O2", "-o", str(so), str(RADICE / "motore" / "pmn_casuale.c")],
                   check=True, capture_output=True)
    (tmp_path / "mappa.py").write_text(MAPPA, encoding="utf-8")
    for nome, byte in (("grande.bin", 2 * 1024 ** 3), ("piccolo.bin", 1024 ** 2)):
        with open(tmp_path / nome, "wb") as f:
            f.truncate(byte)

    def segni(nome, con):
        env = {**os.environ, **({"LD_PRELOAD": str(so)} if con else {})}
        p = subprocess.run([sys.executable, str(tmp_path / "mappa.py"), str(tmp_path / nome)], capture_output=True,
                           text=True, env=env)
        assert p.returncode == 0 and p.stdout.strip(), p.stdout + p.stderr
        return p.stdout.split()

    assert "rr" in segni("grande.bin", True)
    assert "rr" not in segni("piccolo.bin", True)
    assert "rr" not in segni("grande.bin", False)
