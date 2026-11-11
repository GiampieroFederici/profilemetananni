# -*- coding: utf-8 -*-
"""Bowtie2 su un PC con poca memoria (PMN 1.3, 10/11/2026).

Quando la memoria libera è meno dell'indice più 1 GB, Bowtie2 riceve --mm: legge l'indice dal disco man mano, e Linux
può scartarne dei pezzi e rileggerli invece di chiudere Bowtie2 (uscita 137). Con memoria abbondante il comando è quello
della 1.2. Regola in bin/lib/common.sh (pmn_bt2_mm), usata da steps/21_hostfilter.sh, steps/16_triage_host.sh e
motore/metaphlan_fette.sh. Le uscite sono identiche con e senza --mm (Bowtie2 vero su genomi minuscoli).
Gira con la suite del motore nella WSL di sviluppo:
  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_poca_memoria.py"""
import os
import subprocess
from pathlib import Path

import pytest

from test_ospite_standard import HF, con_bowtie2, coppie_di_prova, dna, indice, linux, scrivi_gz
from test_velocita import fette

RADICE = Path(__file__).resolve().parent.parent
GB = 1024 ** 3


def meminfo(tmp_path, libera_byte):
    f = tmp_path / "meminfo"
    f.write_text(f"MemTotal:       99999999 kB\nMemAvailable:   {libera_byte // 1024} kB\n", encoding="utf-8")
    return str(f)


def serve_mm(tmp_path, indice_byte, libera_byte, forza=None):
    """True se pmn_bt2_mm dice che serve --mm, con un indice finto (file sparsi) e una memoria libera finta."""
    for nome, parte in (("i.1.bt2", 0.5), ("i.rev.1.bt2", 0.5)):
        with open(tmp_path / nome, "wb") as f:
            f.truncate(int(indice_byte * parte))
    env = {**os.environ, "PMN_MEMINFO": meminfo(tmp_path, libera_byte)}
    if forza:
        env["PMN_BT2_MM"] = forza
    p = subprocess.run(["bash", "-c", '. "$1"; pmn_bt2_mm "$2"', "-", str(RADICE / "bin" / "lib" / "common.sh"),
                        str(tmp_path / "i")], capture_output=True, text=True, env=env)
    assert p.returncode in (0, 1), p.stdout + p.stderr
    return p.returncode == 0


@linux
def test_mm_solo_se_la_memoria_libera_e_meno_dell_indice_piu_un_gb(tmp_path):
    assert serve_mm(tmp_path, 4 * GB, 4 * GB + GB // 2)          # fetta da 4 GB, 4,5 GB liberi: --mm
    assert not serve_mm(tmp_path, 4 * GB, 6 * GB)                # 6 GB liberi: il comando della 1.2
    assert serve_mm(tmp_path, 4 * GB, 60 * GB, forza="si")       # forzato per le prove
    assert not serve_mm(tmp_path, 4 * GB, GB, forza="no")


# bowtie2 che annota i suoi argomenti e poi lancia quello vero
SPIA = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$TRACCIA"
exec "$VERO" "$@"
"""


def ospite(tmp_path, nome, r1, r2, idx, libera_byte):
    """21_hostfilter.sh con Bowtie2 vero dietro la spia; -> (R1 e R2 senza ospite in byte, argomenti di Bowtie2)."""
    d = tmp_path / nome
    (d / "bin").mkdir(parents=True)
    (d / "t").mkdir()
    spia = d / "bin" / "bowtie2"
    spia.write_text(SPIA, encoding="utf-8")
    spia.chmod(0o755)
    p = subprocess.run(["bash", str(RADICE / "steps" / "21_hostfilter.sh"), "--sample", "S", "--in1", str(r1), "--in2",
                        str(r2), "--index", str(idx), "--out", str(d / "nonhost"), "--log-dir", str(d / "log"),
                        "--threads", "2"], capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{d / 'bin'}:{HF}:{os.environ['PATH']}", "NO_COLOR": "1",
                            "PMN_LANG": "en", "TMPDIR": str(d / "t"), "TRACCIA": str(d / "argomenti.txt"),
                            "VERO": str(HF / "bowtie2"), "PMN_MEMINFO": meminfo(d, libera_byte)})
    assert p.returncode == 0, p.stdout + p.stderr
    import gzip
    return ([gzip.decompress((d / "nonhost" / f"S_nonhost_{i}.fastq.gz").read_bytes()) for i in (1, 2)],
            (d / "argomenti.txt").read_text())


@linux
@con_bowtie2
def test_ospite_con_poca_memoria_usa_mm_e_da_le_stesse_read(tmp_path):
    g = {"maiale": dna(5000), "uomo": dna(5000), "taxon": dna(5000)}
    coppie, q = coppie_di_prova(g)
    r1, r2 = tmp_path / "R1.fastq.gz", tmp_path / "R2.fastq.gz"
    scrivi_gz(r1, [(n, a, q) for n, (a, _b) in coppie.items()])
    scrivi_gz(r2, [(n, b, q) for n, (_a, b) in coppie.items()])
    idx = indice(tmp_path / "idx", "sus_scrofa", g["maiale"])
    larga, arg_larga = ospite(tmp_path, "larga", r1, r2, idx, 60 * GB)
    poca, arg_poca = ospite(tmp_path, "poca", r1, r2, idx, GB // 2)
    assert "--mm" not in arg_larga.split() and "--mm" in arg_poca.split()
    assert larga == poca and larga[0].count(b"\n") == 4 * 3      # stesse read senza ospite, al byte


@linux
def test_fette_con_poca_memoria_usano_mm(tmp_path, monkeypatch):
    """metaphlan_fette.sh (strumenti finti di test_velocita): con poca memoria libera ogni fetta riceve --mm."""
    import test_velocita
    monkeypatch.setattr(test_velocita, "BOWTIE2", test_velocita.BOWTIE2.replace(
        "\n", '\nprintf "%s\\n" "$*" >> "$TRACCIA/bowtie2_argomenti.txt"\n', 1))   # dopo la riga "#!": annota gli argomenti
    monkeypatch.setenv("PMN_MEMINFO", meminfo(tmp_path, GB // 2))
    p, _tmp, out, tr = fette(tmp_path, tmp_path / "nonhost")
    assert p.returncode == 0, p.stdout + p.stderr
    righe = (tr / "bowtie2_argomenti.txt").read_text().splitlines()
    assert len(righe) == 6 and all(r.split()[0] == "--mm" for r in righe), righe
    assert (out / "C1.mapout").read_text().startswith("r1__1\tGeneID:1\n")
