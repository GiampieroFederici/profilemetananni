# -*- coding: utf-8 -*-
"""Kraken senza specie sopra la soglia di Bracken (PMN 1.1, 30/10/2026).

Suolo pubblico ERR2603036 (AMBIENTI, PlusPF-8): 677 coppie classificate, la specie piu' letta ha 5 read; Bracken con
-t 10 esce con "Error: no reads found" e steps/32_kraken_bracken.sh fermava tutta la corsa. Ora il campione ha un
.bracken e un report di specie vuoti ma validi, e un avviso; con almeno una specie Bracken gira come prima (al byte).
Dati: tests/dati/kraken_suolo_ERR2603036.k2report (report vero di quella corsa).
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_kraken_vuoto.py"""
import glob
import gzip
import os
import shutil
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
REPORT = RADICE / "tests" / "dati" / "kraken_suolo_ERR2603036.k2report"
TESTA = "name\ttaxonomy_id\ttaxonomy_lvl\tkraken_assigned_reads\tadded_reads\tnew_est_reads\tfraction_total_reads\n"
linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="steps/*.sh: Linux/WSL only")

# kraken2 finto: scrive come report il report vero del suolo
KRAKEN2 = """#!/usr/bin/env bash
while [ $# -gt 0 ]; do [ "$1" = --report ] && cp "$REPORT_FINTO" "$2"; shift; done
"""
# bracken finto: annota i suoi argomenti e scrive un'uscita riconoscibile
BRACKEN = """#!/usr/bin/env bash
printf "%s\\n" "$@" > "$TRACCIA/bracken.txt"
while [ $# -gt 0 ]; do [ "$1" = -o ] && echo "uscita di bracken" > "$2"; shift; done
"""


def strumenti(tmp_path, bracken=BRACKEN):
    b = tmp_path / "bin"
    b.mkdir()
    (b / "kraken2").write_text(KRAKEN2, encoding="utf-8")
    if bracken:
        (b / "bracken").write_text(bracken, encoding="utf-8")
    for f in b.iterdir():
        f.chmod(0o755)
    return b


def kraken(tmp_path, b, db, min_reads, out=None):
    (tmp_path / "traccia").mkdir(exist_ok=True)
    r1 = tmp_path / "r1.fq.gz"
    r1.write_bytes(gzip.compress(b"@r\nACGT\n+\nIIII\n"))
    return subprocess.run(["bash", str(RADICE / "steps" / "32_kraken_bracken.sh"), "--sample", "S1", "--in1", str(r1),
                           "--db", str(db), "--out", str(out or tmp_path / "out"), "--confidence", "0.1",
                           "--min-reads", str(min_reads), "--threads", "2"], capture_output=True, text=True,
                          env={**os.environ, "PATH": f"{b}:{os.environ['PATH']}", "NO_COLOR": "1", "PMN_LANG": "it",
                               "REPORT_FINTO": str(REPORT), "TRACCIA": str(tmp_path / "traccia")})


@linux
def test_nessuna_specie_con_10_read_profilo_vuoto_e_avviso(tmp_path):
    (tmp_path / "db").mkdir()
    p = kraken(tmp_path, strumenti(tmp_path), tmp_path / "db", 10)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "Kraken: nessuna specie con almeno 10 read in S1; il profilo di Kraken di questo campione è vuoto" \
        in p.stdout + p.stderr
    assert (tmp_path / "out" / "S1.bracken").read_text(encoding="utf-8") == TESTA          # vuoto ma valido
    assert (tmp_path / "out" / "S1_bracken_species.k2report").read_bytes() == b""
    assert not (tmp_path / "traccia" / "bracken.txt").exists()                               # Bracken non chiamato


@linux
def test_profilo_vuoto_non_si_rifa_alla_ripresa(tmp_path):
    (tmp_path / "db").mkdir()
    b = strumenti(tmp_path)
    assert kraken(tmp_path, b, tmp_path / "db", 10).returncode == 0
    (b / "kraken2").write_text("#!/usr/bin/env bash\nexit 9\n", encoding="utf-8")         # non deve ripartire
    p = kraken(tmp_path, b, tmp_path / "db", 10)
    assert p.returncode == 0 and "già profilato" in p.stdout + p.stderr, p.stdout + p.stderr


@linux
def test_con_una_specie_bracken_come_prima(tmp_path):
    """-t 5: Luteitalea pratensis ha 5 read, Bracken gira con gli stessi argomenti di prima e nessun avviso."""
    (tmp_path / "db").mkdir()
    p = kraken(tmp_path, strumenti(tmp_path), tmp_path / "db", 5)
    assert p.returncode == 0, p.stdout + p.stderr
    out = tmp_path / "out"
    assert (tmp_path / "traccia" / "bracken.txt").read_text().split("\n")[:-1] == \
        ["-d", str(tmp_path / "db"), "-i", str(out / "S1.k2report"), "-o", str(out / "S1.bracken"), "-r", "150",
         "-l", "S", "-t", "5"]
    assert (out / "S1.bracken").read_text() == "uscita di bracken\n"
    assert "nessuna specie" not in p.stdout + p.stderr


@linux
def test_un_errore_vero_di_bracken_ferma_ancora_il_passo(tmp_path):
    (tmp_path / "db").mkdir()
    rotto = "#!/usr/bin/env bash\necho 'Error: kmer distribution not found' >&2\nexit 1\n"
    p = kraken(tmp_path, strumenti(tmp_path, rotto), tmp_path / "db", 5)
    assert p.returncode != 0 and "bracken failed for S1" in p.stdout + p.stderr


def bracken_vero():
    """(cartella con bin/bracken, database con database150mers.kmer_distrib) di PlusPF-8 installato, se ci sono."""
    for env in [os.path.expanduser("~/.pmn/mamba/envs/pmn_kraken"), os.path.expanduser("~/miniforge3/envs/pmn_kraken")]:
        if os.path.isfile(os.path.join(env, "bin", "bracken")):
            for db in glob.glob(os.path.expanduser("~/.pmn/db/kraken*/")) + glob.glob(os.path.expanduser("~/pmn_kraken_db/k2_pluspf_08gb_*/")):
                if os.path.isfile(os.path.join(db, "database150mers.kmer_distrib")):
                    return Path(env) / "bin", Path(db)
    return None


@linux
def test_bracken_vero_identico_al_byte_e_suolo_che_prima_fermava(tmp_path):
    v = bracken_vero()
    if v is None:
        pytest.skip("Bracken e PlusPF-8 non installati qui")
    env_bin, db = v
    b = strumenti(tmp_path, bracken=None)
    path = f"{b}:{env_bin}:{os.environ['PATH']}"
    # Bracken da solo sul report del suolo: con -t 10 si ferma (il difetto), con -t 5 trova Luteitalea pratensis
    diretto = tmp_path / "diretto"
    diretto.mkdir()
    shutil.copy(REPORT, diretto / "S1.k2report")
    for t, atteso in ((10, 1), (5, 0)):
        d = subprocess.run(["bracken", "-d", str(db), "-i", str(diretto / "S1.k2report"), "-o",
                            str(diretto / f"S1_t{t}.bracken"), "-r", "150", "-l", "S", "-t", str(t)],
                           capture_output=True, text=True, env={**os.environ, "PATH": path})
        assert d.returncode == atteso, d.stdout + d.stderr
        assert ("no reads found" in d.stdout + d.stderr) == (t == 10)
    for t in (10, 5):
        out = tmp_path / f"passo_t{t}"
        p = subprocess.run(["bash", str(RADICE / "steps" / "32_kraken_bracken.sh"), "--sample", "S1", "--in1",
                            str(REPORT), "--db", str(db), "--out", str(out), "--confidence", "0.1", "--min-reads", str(t),
                            "--threads", "2"], capture_output=True, text=True,
                           env={**os.environ, "PATH": path, "NO_COLOR": "1", "PMN_LANG": "it", "REPORT_FINTO": str(REPORT)})
        assert p.returncode == 0, p.stdout + p.stderr
    assert (tmp_path / "passo_t10" / "S1.bracken").read_text() == TESTA
    assert (tmp_path / "passo_t5" / "S1.bracken").read_bytes() == (diretto / "S1_t5.bracken").read_bytes()
    assert (tmp_path / "passo_t5" / "S1_bracken_species.k2report").read_bytes() == \
        (diretto / "S1_bracken_species.k2report").read_bytes()
