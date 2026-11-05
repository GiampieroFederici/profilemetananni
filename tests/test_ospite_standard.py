# -*- coding: utf-8 -*-
"""F1 (5/11/2026): pulizia e rimozione dell'ospite come lo standard KneadData 0.12.5.

- Bowtie2 --very-sensitive-local, regola strict: una coppia resta solo se nessuna delle due read si allinea
  (KneadData --decontaminate-pairs strict, "remove both R1+R2 if either align"), per ogni ospite e per l'uomo.
- fastp: finestra di 4 basi a qualità media 20 (--cut_right, l'equivalente di SLIDINGWINDOW:4:20 di Trimmomatic
  secondo il manuale di fastp) e lunghezza minima 70 bp (MetaPhlAn --read_min_len 70).
- Il timbro dell'ospite cambia: i progetti già analizzati rifanno ospite, MetaPhlAn e Kraken (D154).

Bowtie2, samtools e fastp sono quelli veri (ambienti pmn_hostfilter e pmn_trim), su genomi minuscoli casuali.
Gira con la suite del motore nella WSL di sviluppo:
  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_ospite_standard.py"""
import gzip
import os
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_ospiti import corsa, installazione_finta

RADICE = Path(__file__).resolve().parent.parent
linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="steps/*.sh: Linux/WSL only")
AMBIENTI = [Path.home() / "miniforge3" / "envs", Path("/home/pmn/.pmn/mamba/envs")]


def ambiente(nome, *programmi):
    """La cartella bin dell'ambiente conda <nome> che ha tutti i programmi, o None."""
    for a in AMBIENTI:
        b = a / nome / "bin"
        if all((b / p).exists() for p in programmi):
            return b
    return None


HF = ambiente("pmn_hostfilter", "bowtie2", "bowtie2-build", "samtools")
TRIM = ambiente("pmn_trim", "fastp")
con_bowtie2 = pytest.mark.skipif(HF is None, reason="ambiente pmn_hostfilter (bowtie2, samtools) assente")
con_fastp = pytest.mark.skipif(TRIM is None, reason="ambiente pmn_trim (fastp) assente")

CASO = random.Random(20261105)
L = 100   # lunghezza delle read


def dna(n):
    return "".join(CASO.choice("ACGT") for _ in range(n))


def rc(s):
    return s[::-1].translate(str.maketrans("ACGT", "TGCA"))


def scrivi_gz(f, read):
    with gzip.open(f, "wt") as h:
        for nome, seq, qual in read:
            h.write(f"@{nome}\n{seq}\n+\n{qual}\n")


def leggi_gz(f):
    with gzip.open(f, "rt") as h:
        righe = h.read().splitlines()
    return [(righe[i][1:].split()[0], righe[i + 1], righe[i + 3]) for i in range(0, len(righe), 4)]


def indice(cartella, nome, seq):
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / f"{nome}.fa").write_text(f">{nome}\n{seq}\n")
    subprocess.run([str(HF / "bowtie2-build"), "-q", "--seed", "1", str(cartella / f"{nome}.fa"),
                    str(cartella / nome)], check=True, capture_output=True)
    return cartella / nome


def lancia_hf(tmp_path, r1, r2, indici, *extra):
    out, log = tmp_path / "nonhost", tmp_path / "log"
    a = ["--sample", "S", "--in1", r1]
    if r2:
        a += ["--in2", r2]
    for i in indici:
        a += ["--index", i]
    a += ["--out", out, "--log-dir", log, "--threads", "2", *extra]
    (tmp_path / "t").mkdir(exist_ok=True)
    p = subprocess.run(["bash", str(RADICE / "steps" / "21_hostfilter.sh"), *map(str, a)], capture_output=True,
                       text=True, env={**os.environ, "PATH": f"{HF}:{os.environ['PATH']}", "NO_COLOR": "1",
                                       "PMN_LANG": "en", "TMPDIR": str(tmp_path / "t")})
    assert p.returncode == 0, p.stdout + p.stderr
    return out, log


@pytest.fixture(scope="module")
def genomi():
    """Due ospiti casuali da 5000 basi (maiale e uomo finti) e un pezzo di DNA che non c'è in nessuno dei due."""
    return {"maiale": dna(5000), "uomo": dna(5000), "taxon": dna(5000)}


def coppie_di_prova(g):
    """Coppie con origine nota. Frammenti di 350 basi, R2 sul filamento opposto (come Illumina)."""
    m, u, t = g["maiale"], g["uomo"], g["taxon"]
    q = "I" * L
    return {
        "entrambe_maiale": (m[500:600], rc(m[750:850])),
        "solo_R1_maiale": (m[1000:1100], t[0:100]),          # una sola read sull'ospite
        "solo_R2_maiale": (t[200:300], rc(m[2000:2100])),
        "discordante": (m[200:300], rc(m[4000:4100])),        # tutte e due sull'ospite, a 3900 basi (oltre -X 500)
        "solo_R1_uomo": (u[1500:1600], rc(t[600:700])),      # una sola read sull'uomo: la toglie il secondo passo
        "taxon_1": (t[1000:1100], rc(t[1250:1350])),
        "taxon_2": (t[2000:2100], rc(t[2250:2350])),
    }, q


@linux
@con_bowtie2
def test_strict_coppia_tolta_se_una_read_va_sull_ospite(tmp_path, genomi):
    """Restano solo le coppie con le due read lontane da tutti e due gli ospiti; le read restano identiche
    (sequenza e qualità), nello stesso ordine. Sul codice vecchio (--un-conc-gz) restavano anche le coppie con una
    sola read sull'ospite e le discordanti."""
    coppie, q = coppie_di_prova(genomi)
    r1, r2 = tmp_path / "R1.fastq.gz", tmp_path / "R2.fastq.gz"
    scrivi_gz(r1, [(n, a, q) for n, (a, _b) in coppie.items()])
    scrivi_gz(r2, [(n, b, q) for n, (_a, b) in coppie.items()])
    idx = [indice(tmp_path / "idx", "sus_scrofa", genomi["maiale"]), indice(tmp_path / "idx", "grch38", genomi["uomo"])]
    out, log = lancia_hf(tmp_path, r1, r2, idx, "--preset", "very-sensitive-local")
    n1, n2 = leggi_gz(out / "S_nonhost_1.fastq.gz"), leggi_gz(out / "S_nonhost_2.fastq.gz")
    assert [n for n, _s, _q in n1] == [n for n, _s, _q in n2] == ["taxon_1", "taxon_2"]
    assert [(s, qq) for _n, s, qq in n1] == [(coppie[n][0], q) for n in ("taxon_1", "taxon_2")]
    assert [(s, qq) for _n, s, qq in n2] == [(coppie[n][1], q) for n in ("taxon_1", "taxon_2")]
    # i log di Bowtie2 restano quelli di Bowtie2 (MultiQC); le coppie entrate e tenute per passo accanto
    assert (log / "S.sus_scrofa.bowtie2.log").read_text().startswith("7 reads; of these:")
    assert (log / "S.sus_scrofa.coppie.tsv").read_text() == "entrate\ttenute\n7\t3\n"
    assert (log / "S.grch38.coppie.tsv").read_text() == "entrate\ttenute\n3\t2\n"


@linux
@con_bowtie2
def test_strict_read_singole(tmp_path, genomi):
    """Read singole: si toglie la read che si allinea, le altre restano identiche."""
    m, t = genomi["maiale"], genomi["taxon"]
    q = "I" * L
    r = tmp_path / "R.fastq.gz"
    scrivi_gz(r, [("ospite", m[3000:3100], q), ("taxon", t[3000:3100], q), ("ospite_rc", rc(m[100:200]), q)])
    out, log = lancia_hf(tmp_path, r, None, [indice(tmp_path / "idx", "sus_scrofa", m)])
    assert leggi_gz(out / "S_nonhost.fastq.gz") == [("taxon", t[3000:3100], q)]
    assert (log / "S.sus_scrofa.coppie.tsv").read_text() == "entrate\ttenute\n3\t1\n"


@linux
@con_bowtie2
def test_strict_salva_le_coppie_tolte(tmp_path, genomi):
    """keep_host_reads: le coppie tolte vanno nella cartella dell'ospite, tutte e due le read (complemento esatto)."""
    coppie, q = coppie_di_prova(genomi)
    r1, r2 = tmp_path / "R1.fastq.gz", tmp_path / "R2.fastq.gz"
    scrivi_gz(r1, [(n, a, q) for n, (a, _b) in coppie.items()])
    scrivi_gz(r2, [(n, b, q) for n, (_a, b) in coppie.items()])
    idx = [indice(tmp_path / "idx", "sus_scrofa", genomi["maiale"])]
    out, _log = lancia_hf(tmp_path, r1, r2, idx, "--host-out", tmp_path / "ospite")
    tolte = sorted(n for n, _s, _q in leggi_gz(tmp_path / "ospite" / "S.sus_scrofa_1.fastq.gz"))
    assert tolte == sorted(n for n, _s, _q in leggi_gz(tmp_path / "ospite" / "S.sus_scrofa_2.fastq.gz"))
    assert tolte == ["discordante", "entrambe_maiale", "solo_R1_maiale", "solo_R2_maiale"]
    assert [n for n, _s, _q in leggi_gz(out / "S_nonhost_1.fastq.gz")] == ["solo_R1_uomo", "taxon_1", "taxon_2"]


@linux
@con_bowtie2
def test_strict_due_corse_identiche(tmp_path, genomi):
    """Riproducibilità: due corse uguali danno file identici al byte dopo la decompressione."""
    coppie, q = coppie_di_prova(genomi)
    r1, r2 = tmp_path / "R1.fastq.gz", tmp_path / "R2.fastq.gz"
    scrivi_gz(r1, [(n, a, q) for n, (a, _b) in coppie.items()] * 50)
    scrivi_gz(r2, [(n, b, q) for n, (_a, b) in coppie.items()] * 50)
    idx = [indice(tmp_path / "idx", "sus_scrofa", genomi["maiale"])]
    uscite = []
    for k in (1, 2):
        d = tmp_path / f"corsa{k}"
        d.mkdir()
        out, _log = lancia_hf(d, r1, r2, idx)
        uscite.append([gzip.decompress((out / f"S_nonhost_{m}.fastq.gz").read_bytes()) for m in (1, 2)])
    assert uscite[0] == uscite[1] and uscite[0][0]


def test_predefinito_very_sensitive_local(tmp_path):
    """Senza host_sensitivity nel config.yaml: --very-sensitive-local, come KneadData 0.12.5."""
    pytest.importorskip("yaml")
    cfg = tmp_path / "config.yaml"
    cfg.write_text("project_name: p\n")
    p = subprocess.run([sys.executable, str(RADICE / "bin" / "lib" / "parse_config.py"), str(cfg)],
                       capture_output=True, text=True, check=True)
    assert "PMN_HOST_PRESET=very-sensitive-local\n" in p.stdout
    esempio = (RADICE / "config.example.yaml").read_text(encoding="utf-8")
    assert "\nhost_sensitivity: very-sensitive-local\n" in esempio


@linux
@con_fastp
def test_fastp_finestra_4_a_20_e_minimo_70(tmp_path):
    """Una coppia con la coda di R1 a Q17 (sopra il Q15 del filtro predefinito di fastp, sotto la media 20 della
    finestra) dalla base 60: la finestra taglia R1 a meno di 70 basi e la coppia esce; la coppia buona resta intera.
    Col fastp predefinito restavano tutte e due, lunghe 150."""
    b = tmp_path / "bin"
    b.mkdir()
    (b / "fastp").symlink_to(TRIM / "fastp")    # solo fastp: niente FastQC in questo test
    t = dna(1000)
    buona, cattiva = "I" * 150, "I" * 60 + "2" * 90   # '2' = Q17
    r1, r2 = tmp_path / "R1.fastq.gz", tmp_path / "R2.fastq.gz"
    scrivi_gz(r1, [("buona", t[0:150], buona), ("coda_bassa", t[400:550], cattiva)])
    scrivi_gz(r2, [("buona", rc(t[200:350]), buona), ("coda_bassa", rc(t[600:750]), buona)])
    p = subprocess.run(["bash", str(RADICE / "steps" / "20_trim.sh"), "--sample", "S", "--in1", str(r1), "--in2",
                        str(r2), "--out", str(tmp_path / "trim"), "--threads", "1"], capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{b}:/usr/bin:/bin", "NO_COLOR": "1", "PMN_LANG": "en"})
    assert p.returncode == 0, p.stdout + p.stderr
    for m in (1, 2):
        assert [(n, len(s)) for n, s, _q in leggi_gz(tmp_path / "trim" / f"S_trim_{m}.fastq.gz")] == [("buona", 150)]


@linux
def test_timbro_ospite_vecchio_rifa_ospite_metaphlan_kraken(tmp_path):
    """Un progetto analizzato con il motore 1.1 (timbro senza la regola strict): la corsa nuova toglie le read senza
    ospite, i log di Bowtie2, i profili di MetaPhlAn e di Kraken e i file della pulizia fatti con la regola vecchia."""
    home = installazione_finta(tmp_path)
    testo, lavoro = corsa(tmp_path, home, "hosts: [sus_scrofa]\n")      # prima corsa: scrive il timbro nuovo
    assert "step failed: trim_C1" in testo, testo
    (lavoro / "nonhost" / ".parametri").write_text("hosts=sus_scrofa\nfilter_human=yes\nhost_sensitivity=very-sensitive\n")
    (lavoro / "metaphlan" / ".parametri").write_text("hosts=sus_scrofa\nfilter_human=yes\nhost_sensitivity=very-sensitive"
                                                     "\nmetaphlan_mode=auto\nmetaphlan_index=mpa_vJan25_CHOCOPhlAnSGB_202503\n")
    vecchi = [lavoro / "nonhost" / "C1_nonhost_1.fastq.gz", lavoro / "nonhost" / "C1_nonhost_2.fastq.gz",
              lavoro / "hostfilter_logs" / "C1.sus_scrofa.bowtie2.log", lavoro / "metaphlan" / "C1_profile.txt",
              lavoro / "trim" / "C1_trim_1_fastqc.html", lavoro / "trim" / "C1_fastp.json"]
    for f in vecchi:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("fatto con la regola vecchia")
    testo, lavoro = corsa(tmp_path, home, "hosts: [sus_scrofa]\n")
    assert [f for f in vecchi if f.exists()] == [], testo
    timbro = (lavoro / "nonhost" / ".parametri").read_text()
    assert "host_sensitivity=very-sensitive-local\n" in timbro and "host_pairs=strict\n" in timbro
    assert "trim=fastp cut_right 4:20 length_required 70" in timbro
    assert timbro in (lavoro / "metaphlan" / ".parametri").read_text()
