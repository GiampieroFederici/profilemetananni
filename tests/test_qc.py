# -*- coding: utf-8 -*-
"""Controllo qualità delle read nel referto (v0.4, 22/10/2026, Giampiero: "è vitale").

FastQC non aveva mai fatto un report: steps/20_trim.sh passava "-o", che FastQC 0.13.0 (pmn_trim) non conosce, e
l'errore restava un avviso nel log. Qui: lo script con un fastqc finto che si comporta come lo 0.13.0, lo script con
il fastqc vero se c'è (WSL), i numeri del QC letti dai JSON di fastp e dai log di Bowtie 2, la sezione del referto.
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_qc.py"""
import glob
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "motore"))
import pmn_motore  # noqa: E402
import referto  # noqa: E402

TRIM = RADICE / "steps" / "20_trim.sh"
linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="steps/*.sh: Linux/WSL only")

# fastp e fastqc finti: fastp scrive le sue uscite; fastqc come lo 0.13.0 (argparse: "-o" non esiste, --outdir sì)
FASTP = """#!/usr/bin/env bash
while [ $# -gt 0 ]; do case "$1" in -o|-O) cp "$IN" "$2"; shift 2;; -i) IN="$2"; shift 2;; --json|--html) echo '{}' > "$2"; shift 2;; *) shift;; esac; done
"""
FASTQC = """#!/usr/bin/env python3
import argparse, os, sys
a = argparse.ArgumentParser(prog="fastqc")
a.add_argument("--outdir"); a.add_argument("-t", "--threads"); a.add_argument("-q", "--quiet", action="store_true")
a.add_argument("files", nargs="*")
o = a.parse_args()
if os.environ.get("FASTQC_MUTO"):
    sys.exit(0)                      # esce bene ma non scrive nulla
for f in o.files:
    b = os.path.basename(f).removesuffix(".gz").removesuffix(".fastq").removesuffix(".fq")
    open(os.path.join(o.outdir or os.path.dirname(f), b + "_fastqc.html"), "w").write("<html></html>")
    open(os.path.join(o.outdir or os.path.dirname(f), b + "_fastqc.zip"), "w").write("zip")
"""


def read_finte(cartella, n=200):
    """Due FASTQ gz a coppie di n read da 100 basi, qualità alta."""
    cartella.mkdir(parents=True, exist_ok=True)
    for i in (1, 2):
        with gzip.open(cartella / f"S1_{i}.fastq.gz", "wt") as f:
            for k in range(n):
                seq = "ACGT"[k % 4] * 10 + "".join("ACGT"[(k * 7 + j * (i + 3)) % 4] for j in range(90))
                f.write(f"@r{k}/{i}\n{seq}\n+\n{'I' * 100}\n")
    return cartella / "S1_1.fastq.gz", cartella / "S1_2.fastq.gz"


def trim(tmp_path, bin_dir, **env):
    r1, r2 = read_finte(tmp_path / "raw")
    return subprocess.run(["bash", str(TRIM), "--sample", "S1", "--in1", str(r1), "--in2", str(r2), "--out",
                           str(tmp_path / "trim"), "--threads", "2"], capture_output=True, text=True,
                          env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "NO_COLOR": "1", **env})


def strumenti_finti(tmp_path):
    b = tmp_path / "bin"
    b.mkdir()
    for nome, testo in (("fastp", FASTP), ("fastqc", FASTQC)):
        (b / nome).write_text(testo, encoding="utf-8")
        (b / nome).chmod(0o755)
    return b


ATTESI = ["S1_1_fastqc.html", "S1_2_fastqc.html", "S1_trim_1_fastqc.html", "S1_trim_2_fastqc.html"]


@linux
def test_fastqc_con_le_opzioni_dello_0_13(tmp_path):
    """Con "-o" il fastqc finto (come lo 0.13.0) esce con 2 e il report non c'è: qui deve esserci per tutte e 4 le read."""
    p = trim(tmp_path, strumenti_finti(tmp_path))
    assert p.returncode == 0, p.stdout + p.stderr
    assert sorted(f.name for f in (tmp_path / "trim").glob("*_fastqc.html")) == ATTESI


@linux
def test_fastqc_senza_report_ferma_il_passo(tmp_path):
    """Niente più errore solo "in avviso": se FastQC non scrive il report, il passo fallisce."""
    p = trim(tmp_path, strumenti_finti(tmp_path), FASTQC_MUTO="1")
    assert p.returncode != 0 and "fastqc wrote no report" in p.stdout + p.stderr


@linux
def test_fastqc_rifatto_alla_ripresa(tmp_path):
    """Read già rifilate ma report di FastQC mancante (corsa fermata): si rifà solo FastQC, non fastp."""
    b = strumenti_finti(tmp_path)
    assert trim(tmp_path, b, FASTQC_MUTO="1").returncode != 0
    (b / "fastp").write_text("#!/usr/bin/env bash\nexit 9\n", encoding="utf-8")   # fastp non deve ripartire
    p = trim(tmp_path, b)
    assert p.returncode == 0, p.stdout + p.stderr
    assert sorted(f.name for f in (tmp_path / "trim").glob("*_fastqc.html")) == ATTESI


def ambiente_trim():
    for c in [os.path.expanduser("~/.pmn/mamba/envs/pmn_trim"), os.path.expanduser("~/miniforge3/envs/pmn_trim"),
              *glob.glob("/home/*/.pmn/mamba/envs/pmn_trim")]:
        if os.path.isfile(os.path.join(c, "bin", "fastqc")) and os.path.isfile(os.path.join(c, "bin", "fastp")):
            return Path(c) / "bin"
    return None


@linux
def test_fastqc_vero_scrive_il_report(tmp_path):
    """Con fastp e FastQC veri dell'ambiente pmn_trim (WSL): 4 report FastQC e il JSON di fastp."""
    b = ambiente_trim()
    if b is None:
        pytest.skip("ambiente pmn_trim non installato qui")
    p = trim(tmp_path, b)
    assert p.returncode == 0, p.stdout + p.stderr
    assert sorted(f.name for f in (tmp_path / "trim").glob("*_fastqc.html")) == ATTESI
    assert json.loads((tmp_path / "trim" / "S1_fastp.json").read_text())["summary"]["before_filtering"]["total_reads"] == 400


# ---------------- numeri del QC e cartella risultati/qc/ ----------------
FASTP_JSON = {"summary": {"before_filtering": {"total_reads": 4000000, "q30_rate": 0.912345, "read1_mean_length": 150,
                                               "read2_mean_length": 150},
                          "after_filtering": {"total_reads": 3800000, "q30_rate": 0.954321, "read1_mean_length": 146,
                                              "read2_mean_length": 144}},
              "duplication": {"rate": 0.0731}}
BOWTIE = ("{n} reads; of these:\n  {n} (100.00%) were paired; of these:\n    {zero} (50.00%) aligned concordantly 0 "
          "times\n")


def lavoro_finto(tmp_path):
    w = tmp_path / "pmn_work"
    (w / "trim").mkdir(parents=True)
    (w / "trim" / "S1_fastp.json").write_text(json.dumps(FASTP_JSON), encoding="utf-8")
    (w / "trim" / "S1_fastp.html").write_text("fastp", encoding="utf-8")
    (w / "trim" / "S1_1_fastqc.html").write_text("fqc", encoding="utf-8")
    (w / "hostfilter_logs").mkdir()   # due passaggi: maiale, poi uomo (entrate nel primo, rimaste dopo l'ultimo)
    (w / "hostfilter_logs" / "S1.sus_scrofa.bowtie2.log").write_text(BOWTIE.format(n=1900000, zero=600000))
    (w / "hostfilter_logs" / "S1.grch38.bowtie2.log").write_text(BOWTIE.format(n=600000, zero=570000))
    (w / "multiqc" / "prova_multiqc_report_data").mkdir(parents=True)
    (w / "multiqc" / "prova_multiqc_report.html").write_text("mqc", encoding="utf-8")
    (w / "multiqc" / "prova_multiqc_report_data" / "multiqc_fastqc.txt").write_text("x", encoding="utf-8")
    return w


def test_controllo_qualita_copia_e_numeri(tmp_path):
    w = lavoro_finto(tmp_path)
    r = tmp_path / "risultati"
    qc = pmn_motore.controllo_qualita(w, w / "trim", r)
    assert qc["multiqc"] == "qc/prova_multiqc_report.html" and (r / qc["multiqc"]).is_file()
    assert (r / "qc" / "prova_multiqc_report_data" / "multiqc_fastqc.txt").is_file()
    assert qc["fastp"] == ["qc/S1_fastp.html"] and qc["fastqc"] == ["qc/fastqc/S1_1_fastqc.html"]
    assert all((r / f).is_file() for f in qc["fastp"] + qc["fastqc"])
    c, = qc["campioni"]
    assert c["nome"] == "S1" and c["a_coppie"] is True
    assert (c["coppie_prima"], c["coppie_dopo"]) == (2000000, 1900000)          # read / 2: sono coppie
    assert c["q30_prima_pct"] == pytest.approx(91.2345) and c["q30_dopo_pct"] == pytest.approx(95.4321)
    assert c["duplicati_pct"] == pytest.approx(7.31) and c["lunghezza_media"] == pytest.approx(145)
    assert c["coppie_profili"] == 570000 and c["ospite_pct"] == pytest.approx(70.0)
    json.dumps(qc)                                                               # va in risultati.json


def test_controllo_qualita_senza_niente(tmp_path):
    """Analisi senza QC (per esempio di prima del 22/10): campi vuoti, nessun errore."""
    qc = pmn_motore.controllo_qualita(tmp_path / "pmn_work", tmp_path / "pmn_work" / "trim", tmp_path / "risultati")
    assert qc == {"multiqc": None, "fastp": [], "fastqc": [], "campioni": []}


def test_sezione_qc_del_referto(tmp_path):
    """Due tabelle da 5 colonne (il PDF di Qt rende male le tabelle larghe), numeri scritti all'italiana, frase su come
    leggerle e collegamento al report MultiQC."""
    w = lavoro_finto(tmp_path)
    qc = pmn_motore.controllo_qualita(w, w / "trim", tmp_path / "risultati")
    h = "\n".join(referto.html_qc({"qc": qc}, 7))
    assert h.startswith("<h2>7. Controllo qualità delle read</h2>")
    tabelle = h.split("<table")[1:]
    assert len(tabelle) == 2
    for t in tabelle:
        assert t.split("</tr>")[0].count("<th") == 5                            # al massimo 5 colonne
    assert "2.000.000" in tabelle[0] and "1.900.000" in tabelle[0] and "91,2" in tabelle[0] and "95,4" in tabelle[0]
    assert "7,3" in tabelle[1] and ">145,0<" in tabelle[1] and "70,0" in tabelle[1] and "570.000" in tabelle[1]
    assert "Come leggerle" in h and "1 errore ogni 1.000 basi" in h
    # 22/10: fastp misura i duplicati sulle read grezze; l'ospite tolto è maiale (o altro) più uomo
    assert "Duplicati, read grezze (%)" in tabelle[1] and "Ospite e uomo tolti (%)" in tabelle[1]
    assert "I duplicati sono misurati sulle read grezze." in h
    assert '<a href="../qc/prova_multiqc_report.html">' in h
    vuota = "\n".join(referto.html_qc({"qc": {}}, 7))
    assert "non disponibile" in vuota and "<table" not in vuota


def test_foglio_qc_dell_excel(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    w = lavoro_finto(tmp_path)
    qc = pmn_motore.controllo_qualita(w, w / "trim", tmp_path / "risultati")
    d = {"progetto": "prova", "corsa": "c", "motore": "0.1.0", "soglia": 0.1, "campioni": [], "triage": [],
         "sicurezza": [], "parametri": {"kraken_confidence": "0.5"}, "versioni": {}, "citazioni": [],
         "diversita": {"metaphlan": [], "kraken": []}, "qc": qc}
    referto.excel(d, tmp_path / "r.xlsx")
    ws = openpyxl.load_workbook(tmp_path / "r.xlsx")["QC"]
    intest, riga = list(ws.values)[:2]
    assert intest[0] == "Campione" and len(intest) == 9
    assert intest[5] == "% duplicati (read grezze)" and intest[7] == "% ospite e uomo tolti"
    assert riga[:3] == ("S1", 2000000, 1900000) and riga[-1] == 570000
    assert riga[3] == pytest.approx(91.2345) and riga[7] == pytest.approx(70.0)


# ---------------- 22/10: numeri lunghi interi su una riga nel PDF ----------------
def test_numeri_a_8_cifre_su_una_riga_nel_pdf(tmp_path):
    """Salame_esempio (b8ef83a): nel PDF "1.507.887" andava a capo ("1.507.88" e sotto "7"; letto con PyMuPDF sul PDF
    vero). Il referto intero, con coppie a 8 cifre come C03_1 (34 milioni), impaginato come fa referto.pdf():
    QTextDocument.print_() impagina in punti (72 per pollice: 510 di pagina utile su A4 con 15 mm di margine; a questa
    larghezza Qt spezza "1.507.887" come nel PDF vero), quindi qui si impagina così e si contano le righe di ogni numero."""
    QtGui = pytest.importorskip("PySide6.QtGui")
    from PySide6.QtCore import QMarginsF, QSizeF
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication(["test"])  # noqa: F841
    if not QtGui.QFontDatabase.families():
        pytest.skip("Qt senza caratteri qui (Windows col Python misto): gira con il Python del motore")
    r = tmp_path / "risultati"
    dati = RADICE / "installer" / "finto"
    for sotto, f in (("metaphlan", "SRR4875279_profile.txt"), ("kraken", "SRR4875279.bracken"),
                     ("kraken", "SRR4875279.k2report"), ("tabelle", "parameters.tsv")):
        (r / sotto).mkdir(parents=True, exist_ok=True)
        shutil.copy(dati / f, r / sotto)
    indice = json.loads((dati / "risultati.json").read_text(encoding="utf-8"))
    numeri = {"coppie_prima": 34_000_000, "coppie_dopo": 33_123_456, "coppie_profili": 12_345_678}
    indice["qc"] = {"multiqc": "qc/x_multiqc_report.html", "fastp": [], "fastqc": [], "campioni": [
        {"nome": "SRR4875279", "a_coppie": True, "q30_prima_pct": 94.95, "q30_dopo_pct": 95.46, "duplicati_pct": 3.25,
         "lunghezza_media": 140.0, "ospite_pct": 53.09, **numeri}]}
    (r / "risultati.json").write_text(json.dumps(indice), encoding="utf-8")
    html = referto.html_referto(referto.raccogli(r, {"project_name": "prova"}))
    doc = QtGui.QTextDocument()
    doc.setHtml(html)
    w = QtGui.QPdfWriter(str(tmp_path / "r.pdf"))                      # stessa pagina di referto.pdf()
    w.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4))
    w.setPageMargins(QMarginsF(15, 15, 15, 15), QtGui.QPageLayout.Unit.Millimeter)
    punti = w.pageLayout().paintRect(QtGui.QPageLayout.Unit.Point).width()   # 510: come nel PDF vero (PyMuPDF, 22/10)
    doc.setPageSize(QSizeF(punti, 100_000))
    doc.documentLayout().documentSize()
    righe, spezzate, qc, b = {}, [], False, doc.begin()
    while b.isValid():
        t = b.text()
        qc = (qc or t.startswith("Pulizia delle read")) and not t.startswith("Come leggerle")
        if t.strip() in {referto.lingua.migliaia(f"{n:,}") for n in numeri.values()}:
            righe[t.strip()] = b.layout().lineCount()
        for i in range(b.layout().lineCount() - 1 if qc else 0):   # intestazioni e celle: a capo solo fra parole
            fine = b.layout().lineAt(i).textStart() + b.layout().lineAt(i).textLength()
            if not (t[fine - 1].isspace() or t[fine].isspace()):
                spezzate.append(f"{t[:fine]}|{t[fine:]}")
        b = b.next()
    assert len(righe) == 3 and set(righe.values()) == {1}, (righe, round(punti))
    assert not spezzate, spezzate
