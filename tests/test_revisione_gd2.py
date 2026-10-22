# -*- coding: utf-8 -*-
"""Revisione del 22/10, gruppo GD2-pipeline: passi del motore che dopo un'interruzione restano a metà, e sprechi.

Ogni test riproduce un problema della revisione (P05, P06, ...) con programmi finti in testa al PATH.
Gira con la suite del motore nella WSL di sviluppo (non nella pmn):
  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_revisione_gd2.py"""
import gzip
import os
import shutil
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="steps/*.sh: Linux/WSL only")


def finti(cartella, **programmi):
    """Programmi finti (testo bash) in <cartella>/bin, da mettere in testa al PATH."""
    b = cartella / "bin"
    b.mkdir(exist_ok=True)
    for nome, testo in programmi.items():
        (b / nome).write_text(testo, encoding="utf-8", newline="\n")
        (b / nome).chmod(0o755)
    return b


def lancia(script, args, bin_dir, cwd=None, **env):
    return subprocess.run(["bash", str(RADICE / script), *map(str, args)], capture_output=True, text=True, cwd=cwd,
                          env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "NO_COLOR": "1",
                               "PMN_LANG": "en", **env})


def gz_fastq(f, n=200, mate=1):
    """Un FASTQ gz valido di n read."""
    f.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(f, "wt") as h:
        for k in range(n):
            h.write(f"@r{k}/{mate}\n{'ACGT'[k % 4] * 50}\n+\n{'I' * 50}\n")
    return f


def righe_gz(f):
    """Numero di righe di un gz; solleva un errore se il gz è troncato."""
    with gzip.open(f, "rt") as h:
        return sum(1 for _ in h)


# ---------------- P05: download e rifilatura scritti a metà presi per finiti ----------------
PREFETCH = "#!/usr/bin/env bash\nexit 0\n"
# fasterq-dump finto: argomenti nel registro, temporanei in -t (altrimenti nella cartella corrente, come il vero),
# poi <acc>_1.fastq e <acc>_2.fastq in -O
FASTERQ = r"""#!/usr/bin/env bash
echo "$@" >> "$REGISTRO_FQD"
O=.; T=""; acc=""
while [ $# -gt 0 ]; do
  case "$1" in -O) O="$2"; shift 2;; -t) T="$2"; shift 2;; --threads) shift 2;; --split-files) shift;; *) acc="$1"; shift;; esac
done
mkdir -p "${T:-.}/fasterq.tmp.x"
n="$(basename "$acc" .sra)"
for i in 1 2; do
  for k in $(seq 1 100); do printf '@r%s/%s\nACGTACGTAC\n+\nIIIIIIIIII\n' "$k" "$i"; done > "$O/${n}_$i.fastq"
done
"""
# pigz finto: la prima volta sul mate 2 scrive solo l'inizio dell'uscita e muore come con SIGTERM (Annulla)
PIGZ = r"""#!/usr/bin/env bash
f="${@: -1}"
if [ "${f%_2.fastq}" != "$f" ] && [ ! -e "$PIGZ_UCCISO" ]; then
  : > "$PIGZ_UCCISO"; gzip -c "$f" | head -c 100; exit 143
fi
exec gzip -c "$f"
"""


@linux
def test_p05_download_interrotto_si_rifa(tmp_path):
    b = finti(tmp_path, prefetch=PREFETCH, **{"fasterq-dump": FASTERQ, "pigz": PIGZ})
    (tmp_path / "t").mkdir()
    env = {"TMPDIR": str(tmp_path / "t"), "REGISTRO_FQD": str(tmp_path / "fqd.log"),
           "PIGZ_UCCISO": str(tmp_path / "ucciso")}
    raw = tmp_path / "raw"
    args = ["--srr", "SRR000001", "--out", raw, "--threads", "1"]
    assert lancia("steps/10_download_sra.sh", args, b, cwd=tmp_path, **env).returncode != 0
    p = lancia("steps/10_download_sra.sh", args, b, cwd=tmp_path, **env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "already downloaded" not in p.stdout + p.stderr
    assert [righe_gz(raw / f"SRR000001_{i}.fastq.gz") for i in (1, 2)] == [400, 400]
    assert sorted(f.name for f in raw.iterdir()) == ["SRR000001_1.fastq.gz", "SRR000001_2.fastq.gz"]


# fastp finto: la prima volta scrive -o per intero e -O a metà, poi muore come con SIGTERM; dopo copia gli ingressi
FASTP_UCCISO = r"""#!/usr/bin/env bash
while [ $# -gt 0 ]; do
  case "$1" in -i) I1="$2"; shift 2;; -I) I2="$2"; shift 2;; -o) O1="$2"; shift 2;; -O) O2="$2"; shift 2;;
    --json|--html) echo '{}' > "$2"; shift 2;; *) shift;; esac
done
cp "$I1" "$O1"
if [ ! -e "$FASTP_UCCISO" ]; then : > "$FASTP_UCCISO"; head -c 100 "$I2" > "$O2"; exit 143; fi
cp "$I2" "$O2"
"""
# fastqc finto: un report per ogni file, nella cartella di --outdir
FASTQC = r"""#!/usr/bin/env bash
while [ $# -gt 0 ]; do
  case "$1" in --outdir) D="$2"; shift 2;; -t) shift 2;; -q) shift;;
    *) b="$(basename "$1")"; b="${b%.gz}"; b="${b%.fastq}"; b="${b%.fq}"; echo x > "$D/${b}_fastqc.html"; shift;; esac
done
"""


@linux
def test_p05_rifilatura_interrotta_si_rifa(tmp_path):
    b = finti(tmp_path, fastp=FASTP_UCCISO, fastqc=FASTQC)
    r1, r2 = gz_fastq(tmp_path / "R1.fastq.gz", mate=1), gz_fastq(tmp_path / "R2.fastq.gz", mate=2)
    trim = tmp_path / "trim"
    args = ["--sample", "C1", "--in1", r1, "--in2", r2, "--out", trim, "--threads", "1"]
    env = {"FASTP_UCCISO": str(tmp_path / "ucciso")}
    assert lancia("steps/20_trim.sh", args, b, **env).returncode != 0
    p = lancia("steps/20_trim.sh", args, b, **env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "already trimmed" not in p.stdout + p.stderr
    assert righe_gz(trim / "C1_trim_1.fastq.gz") == righe_gz(trim / "C1_trim_2.fastq.gz") == 800
    assert list(trim.glob(".*")) == []


# ---------------- P06: filtro dell'ospite, il mate 1 pubblicato prima del mate 2 ----------------
# bowtie2 finto: scrive le read "non host" (copia degli ingressi) dove dice --un-conc-gz
BOWTIE2 = r"""#!/usr/bin/env bash
while [ $# -gt 0 ]; do
  case "$1" in -1) I1="$2"; shift 2;; -2) I2="$2"; shift 2;; --un-conc-gz) U="$2"; shift 2;; *) shift;; esac
done
cp "$I1" "${U/\%/1}"; cp "$I2" "${U/\%/2}"
"""
# mv finto: alla chiamata numero $MV_UCCIDI ferma lo script (Annulla durante la pubblicazione), altrimenti il vero mv
MV = r"""#!/usr/bin/env bash
n=$(( $(cat "$MV_CONTA" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$MV_CONTA"
if [ "$n" -eq "$MV_UCCIDI" ]; then kill -TERM "$PPID"; exit 143; fi
exec /bin/mv "$@"
"""


def hostfilter_fermato(tmp_path, uccidi):
    b = finti(tmp_path, bowtie2=BOWTIE2, mv=MV)
    r1, r2 = gz_fastq(tmp_path / "R1.fastq.gz", mate=1), gz_fastq(tmp_path / "R2.fastq.gz", mate=2)
    (tmp_path / "idx.1.bt2").write_text("x")
    (tmp_path / "t").mkdir()
    out = tmp_path / "nonhost"
    p = lancia("steps/21_hostfilter.sh", ["--sample", "S", "--in1", r1, "--in2", r2, "--index", tmp_path / "idx",
                                          "--out", out, "--threads", "1"], b,
               TMPDIR=str(tmp_path / "t"), MV_CONTA=str(tmp_path / "conta"), MV_UCCIDI=str(uccidi))
    return p, out


@linux
@pytest.mark.parametrize("uccidi", [1, 2, 3, 4])
def test_p06_hostfilter_fermato_mai_mate1_senza_mate2(tmp_path, uccidi):
    """run.sh riprende guardando solo nonhost_1: se c'è il mate 1 deve esserci, intero, anche il mate 2."""
    p, out = hostfilter_fermato(tmp_path, uccidi)
    m1, m2 = out / "S_nonhost_1.fastq.gz", out / "S_nonhost_2.fastq.gz"
    if m1.exists():
        assert m2.exists() and righe_gz(m2) == 800
    assert [f.name for f in out.iterdir() if f.name.endswith(".part")] == []


@linux
def test_p06_hostfilter_intero(tmp_path):
    p, out = hostfilter_fermato(tmp_path, 99)
    assert p.returncode == 0, p.stdout + p.stderr
    assert sorted(f.name for f in out.glob("*.gz*")) == ["S_nonhost_1.fastq.gz", "S_nonhost_2.fastq.gz"]
    assert righe_gz(out / "S_nonhost_1.fastq.gz") == righe_gz(out / "S_nonhost_2.fastq.gz") == 800
