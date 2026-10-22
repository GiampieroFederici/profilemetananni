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


# ---------------- P08: MetaPhlAn standard, il mapout di una corsa interrotta blocca la ripresa ----------------
# metaphlan finto con lo stesso controllo di check_params della 4.2.4: --mapout già presente senza --force = errore
METAPHLAN = r"""#!/usr/bin/env bash
: > "$MPA_CHIAMATO"
force=0
while [ $# -gt 0 ]; do
  case "$1" in --mapout) MAP="$2"; shift 2;; -o) PROF="$2"; shift 2;; --force) force=1; shift;; *) shift;; esac
done
if [ -e "$MAP" ] && [ "$force" -eq 0 ]; then echo "ERROR: Mapping output file detected: $MAP" >&2; exit 1; fi
echo mapout | bzip2 > "$MAP"
printf '#mpa_vJan25\nk__Bacteria\t2\t100.0\t\n' > "$PROF"
"""


def metaphlan_standard(tmp_path):
    b = finti(tmp_path, metaphlan=METAPHLAN)
    r1 = tmp_path / "r1.fq"
    r1.write_text("@r1\nACGT\n+\nIIII\n")
    out = tmp_path / "out"
    out.mkdir()
    p = lambda: lancia("steps/30_metaphlan.sh", ["--sample", "S1", "--in1", r1, "--out", out, "--threads", "1"], b,
                       MPA_CHIAMATO=str(tmp_path / "chiamato"))
    return p, out


@linux
def test_p08_mapout_parziale_non_blocca_la_ripresa(tmp_path):
    p, out = metaphlan_standard(tmp_path)
    (out / "S1.bowtie2.bz2").write_bytes(b"BZh91AY&SY parziale")       # corsa uccisa a metà, nessun profilo
    r = p()
    assert r.returncode == 0, r.stdout + r.stderr
    assert (out / "S1_profile.txt").stat().st_size > 0


@linux
def test_p08_profilo_fatto_si_salta(tmp_path):
    p, out = metaphlan_standard(tmp_path)
    (out / "S1_profile.txt").write_text("#fatto\n")
    (out / "S1.bowtie2.bz2").write_bytes(b"mapout intero")
    r = p()
    assert r.returncode == 0 and not (tmp_path / "chiamato").exists()
    assert (out / "S1.bowtie2.bz2").read_bytes() == b"mapout intero"


# ---------------- P22: rifilatura, gzip -t su R1 e R2 uno dopo l'altro e anche quando fastp si salta ----------------
# gzip finto: registra inizio e fine di ogni controllo e dorme 1 s; esce con 1 sul file di nome $GZ_ROTTO
GZIP_LENTO = r"""#!/usr/bin/env bash
f="$(basename "${@: -1}")"
echo "inizio $f $(date +%s.%N)" >> "$REGISTRO_GZ"
sleep 1
echo "fine $f $(date +%s.%N)" >> "$REGISTRO_GZ"
[ "$f" != "${GZ_ROTTO:-}" ]
"""
# fastp finto: copia gli ingressi nelle uscite
FASTP = r"""#!/usr/bin/env bash
I2=""
while [ $# -gt 0 ]; do
  case "$1" in -i) I1="$2"; shift 2;; -I) I2="$2"; shift 2;; -o) O1="$2"; shift 2;; -O) O2="$2"; shift 2;;
    --json|--html) echo '{}' > "$2"; shift 2;; *) shift;; esac
done
cp "$I1" "$O1"; [ -z "$I2" ] || cp "$I2" "$O2"
"""


def trim_gz(tmp_path, gia_rifilato=False, rotto=""):
    b = finti(tmp_path, gzip=GZIP_LENTO, fastp=FASTP, fastqc=FASTQC)
    r1, r2 = gz_fastq(tmp_path / "R1.fastq.gz", mate=1), gz_fastq(tmp_path / "R2.fastq.gz", mate=2)
    trim = tmp_path / "trim"
    if gia_rifilato:
        gz_fastq(trim / "C1_trim_1.fastq.gz", mate=1)
        gz_fastq(trim / "C1_trim_2.fastq.gz", mate=2)
    reg = tmp_path / "gz.log"
    p = lancia("steps/20_trim.sh", ["--sample", "C1", "--in1", r1, "--in2", r2, "--out", trim, "--threads", "1"], b,
               REGISTRO_GZ=str(reg), GZ_ROTTO=rotto)
    eventi = {(r.split()[0], r.split()[1]): float(r.split()[2]) for r in reg.read_text().splitlines()} \
        if reg.exists() else {}
    return p, eventi


@linux
def test_p22_gzip_non_lanciato_se_gia_rifilato(tmp_path):
    p, eventi = trim_gz(tmp_path, gia_rifilato=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert eventi == {}                                               # fastp si salta: niente da controllare


@linux
def test_p22_gzip_r1_r2_in_parallelo(tmp_path):
    p, eventi = trim_gz(tmp_path)
    assert p.returncode == 0, p.stdout + p.stderr
    assert eventi[("inizio", "R2.fastq.gz")] < eventi[("fine", "R1.fastq.gz")]


@linux
@pytest.mark.parametrize("rotto", ["R1.fastq.gz", "R2.fastq.gz"])
def test_p22_gzip_rotto_fallisce(tmp_path, rotto):
    p, _ = trim_gz(tmp_path, rotto=rotto)
    assert p.returncode != 0 and "corrupt gzip" in p.stdout + p.stderr and rotto in p.stdout + p.stderr
    assert not (tmp_path / "trim" / "C1_trim_1.fastq.gz").exists()


# ---------------- P28: il confronto MetaPhlAn/Kraken conta anche Homo, Leishmania e virus ----------------
def test_p28_run_sh_confronto_con_i_soli_taxa_del_referto():
    righe = (RADICE / "bin" / "run.sh").read_text(encoding="utf-8").splitlines()
    kraken = [r for r in righe if "a+=(--kraken" in r]
    assert len(kraken) == 1 and '--kraken "$RES_DIR/kraken_matrix_taxa.tsv"' in kraken[0]


def test_p28_confronto_solo_batteri_archei_funghi(tmp_path):
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    import sys
    krk = tmp_path / "kraken"
    krk.mkdir()
    # albero del report di Kraken (rientro di 2 spazi per livello) e Bracken: L. sakei 50 %, Homo e Leishmania
    # 0,17 %, un virus 0,2 %: tutti sopra la soglia di 0,1 %, ma solo L. sakei è un taxon del prodotto
    albero = [(0, "R", 1, "root"), (1, "R1", 131567, "cellular organisms"), (2, "D", 2, "Bacteria"),
              (3, "S", 1599, "Latilactobacillus sakei"), (2, "D", 2759, "Eukaryota"), (3, "S", 9606, "Homo sapiens"),
              (3, "S", 5664, "Leishmania major"), (1, "D", 10239, "Viruses"), (2, "S", 99999, "Virus finto")]
    (krk / "S1.k2report").write_text("".join(f"1.00\t10\t10\t{r}\t{t}\t{'  ' * l}{n}\n" for l, r, t, n in albero),
                                     encoding="utf-8")
    specie = [("Latilactobacillus sakei", 1599, 0.5), ("Homo sapiens", 9606, 0.0017),
              ("Leishmania major", 5664, 0.0017), ("Virus finto", 99999, 0.002)]
    (krk / "S1.bracken").write_text(
        "name\ttaxonomy_id\ttaxonomy_lvl\tkraken_assigned_reads\tadded_reads\tnew_est_reads\tfraction_total_reads\n"
        + "".join(f"{n}\t{t}\tS\t10\t0\t10\t{f}\n" for n, t, f in specie), encoding="utf-8")
    mpa = tmp_path / "metaphlan_merged.tsv"
    mpa.write_text("clade_name\tS1\nk__Bacteria|p__Bacillota|s__Latilactobacillus_sakei\t100.0\n", encoding="utf-8")
    subprocess.run([sys.executable, str(RADICE / "steps" / "33_kraken_matrix.py"), "--in", str(krk),
                    "--out", str(tmp_path / "kraken_matrix.tsv"), "--taxa-out", str(tmp_path / "kraken_matrix_taxa.tsv"),
                    "--threshold-pct", "0.1"], check=True, capture_output=True)

    def confronto(matrice):
        out = tmp_path / f"{matrice}.xlsx"
        subprocess.run([sys.executable, str(RADICE / "steps" / "40_compare_report.py"), "--metaphlan", str(mpa),
                        "--kraken", str(tmp_path / f"{matrice}.tsv"), "--out", str(out), "--threshold-pct", "0.1"],
                       check=True, capture_output=True)
        s = pd.read_excel(out, sheet_name="summary").set_index("metric")["value"]
        return s, pd.read_excel(out, sheet_name="all_taxa")

    s, taxa = confronto("kraken_matrix")                              # matrice intera: Homo, Leishmania, virus contati
    assert s["species_kraken"] == 4 and s["only_kraken"] == 3
    s, taxa = confronto("kraken_matrix_taxa")                         # la matrice che passa run.sh dopo P28
    assert (s["species_kraken"], s["only_kraken"], s["jaccard"], s["kraken_confirmed_by_metaphlan_pct"]) == (1, 0, 1, 100)
    assert list(taxa["species"]) == ["latilactobacillus sakei"]


# ---------------- P23: fasterq-dump mette i suoi temporanei nella cartella corrente (Documenti, su /mnt/c) ----------------
@linux
def test_p23_temporanei_di_fasterq_dump_nella_cartella_temporanea(tmp_path):
    b = finti(tmp_path, prefetch=PREFETCH, **{"fasterq-dump": FASTERQ, "pigz": '#!/usr/bin/env bash\nexec gzip -c "${@: -1}"\n'})
    (tmp_path / "t").mkdir()
    progetti = tmp_path / "progetti"                                  # la cartella corrente del motore
    progetti.mkdir()
    raw = tmp_path / "raw"
    p = lancia("steps/10_download_sra.sh", ["--srr", "SRR000001", "--out", raw, "--threads", "1"], b, cwd=progetti,
               TMPDIR=str(tmp_path / "t"), REGISTRO_FQD=str(tmp_path / "fqd.log"))
    assert p.returncode == 0, p.stdout + p.stderr
    args = (tmp_path / "fqd.log").read_text().split()
    assert "-t" in args and args[args.index("-t") + 1].startswith(str(tmp_path / "t"))
    assert list(progetti.iterdir()) == []
    assert [righe_gz(raw / f"SRR000001_{i}.fastq.gz") for i in (1, 2)] == [400, 400]
