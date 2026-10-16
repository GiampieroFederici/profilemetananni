# -*- coding: utf-8 -*-
"""Report in risultati/referto/ (HTML + Excel + PDF, contract v0.2). Criteria R1-R5, R7 of
sessioni/2026-10-16_motore_seconda_parte.md, on the real SF3RAt7 run of the fake engine data."""
import csv
import json
import os
import shutil
import subprocess
import sys

import pytest

from contratto import controlla

openpyxl = pytest.importorskip("openpyxl")
pytest.importorskip("PySide6.QtGui")

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
REFERTO = os.path.join(ROOT, "motore", "referto.py")
FINTO = os.path.join(ROOT, "installer", "finto_motore.py")
DATI = os.path.join(ROOT, "installer", "finto")
NOME = "SF3RAt7 (salame Felino)"   # project name used to build installer/finto/referto/


def prepara(tmp_path):
    p = tmp_path / "SF3RAt7"
    for sotto in ("metaphlan", "kraken", "tabelle"):
        (p / "risultati" / sotto).mkdir(parents=True)
    shutil.copy(os.path.join(DATI, "SRR4875279_profile.txt"), p / "risultati" / "metaphlan")
    for est in ("bracken", "k2report"):
        shutil.copy(os.path.join(DATI, f"SRR4875279.{est}"), p / "risultati" / "kraken")
    for f in ("parameters.tsv", "kraken_matrix.tsv", "metaphlan_merged.tsv"):
        shutil.copy(os.path.join(DATI, f), p / "risultati" / "tabelle")
    shutil.copy(os.path.join(DATI, "risultati.json"), p / "risultati")
    (p / "config.yaml").write_text(f"project_name: {NOME}\n", encoding="utf-8")
    return p


def fai_referto(p):
    r = subprocess.run([sys.executable, REFERTO, "--risultati", str(p / "risultati"), "--progetto", str(p / "config.yaml")],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def referto(tmp_path_factory):
    p = prepara(tmp_path_factory.mktemp("ref"))
    esito = fai_referto(p)
    wb = openpyxl.load_workbook(p / "risultati" / "referto" / "referto.xlsx")
    html = (p / "risultati" / "referto" / "referto.html").read_text(encoding="utf-8")
    return p, esito, wb, html


def righe(ws):
    v = list(ws.values)
    return [dict(zip(v[0], r)) for r in v[1:]]


def test_r1_tre_file(referto):
    p, esito, wb, html = referto
    assert esito["problemi"] == [] and esito["pagine_pdf"] >= 1
    assert (p / "risultati" / "referto" / "referto.pdf").read_bytes()[:4] == b"%PDF"
    assert html.startswith("<!DOCTYPE html>") and 'lang="it"' in html


def test_r2_numeri_fedeli(referto):
    _, _, wb, html = referto
    mpa = {r["Specie"]: r for r in righe(wb["MetaPhlAn_specie"])}
    with open(os.path.join(DATI, "SRR4875279_profile.txt"), encoding="utf-8") as f:   # riga s__ del profilo
        grezzo = next(float(r.split("\t")[2]) for r in f if r.split("\t")[0].endswith("|s__Latilactobacillus_sakei"))
    assert mpa["Latilactobacillus sakei"]["% sul totale delle read"] == grezzo == 21.617793
    assert "21,618" in html
    assert sum(r["% fra le specie trovate"] for r in mpa.values()) == pytest.approx(100.0)
    micro = {r["Specie"]: r for r in righe(wb["Kraken_microbi"])}
    with open(os.path.join(DATI, "SRR4875279.bracken"), encoding="utf-8") as f:
        bracken = {r["name"]: float(r["fraction_total_reads"]) * 100 for r in csv.DictReader(f, delimiter="\t")}
    assert micro["Latilactobacillus sakei"]["% sul totale assegnato"] == pytest.approx(bracken["Latilactobacillus sakei"])
    somma_microbi = sum(bracken[n] for n in micro)
    assert micro["Latilactobacillus sakei"]["% fra i soli microbi"] == pytest.approx(
        100 * bracken["Latilactobacillus sakei"] / somma_microbi)
    assert sum(r["% fra i soli microbi"] for r in micro.values()) == pytest.approx(100.0)
    assert micro["Debaryomyces hansenii"]["Gruppo"] == "funghi"


def test_r3_metaphlan_e_kraken_mai_insieme(referto):
    _, _, wb, html = referto
    assert {"MetaPhlAn_specie", "Kraken_microbi", "Kraken_a_parte"} <= set(wb.sheetnames)
    sez_mpa = html.split("2. Specie trovate con MetaPhlAn")[1].split("3. Microbi trovati con Kraken")[0]
    sez_krk = html.split("3. Microbi trovati con Kraken")[1].split("4. Virus")[0]
    assert "Proteus vulgaris" not in sez_mpa and "Proteus vulgaris" in sez_krk          # solo Kraken
    assert "Candida parapsilosis" in sez_mpa and "Candida parapsilosis" not in sez_krk  # solo MetaPhlAn
    assert not any(r["Specie"] == "Proteus vulgaris" for r in righe(wb["MetaPhlAn_specie"]))


def test_r4_homo_e_leishmania_a_parte(referto):
    _, _, wb, _ = referto
    micro = {r["Specie"] for r in righe(wb["Kraken_microbi"])}
    parte = {r["Nome"]: r for r in righe(wb["Kraken_a_parte"])}
    assert not micro & {"Homo sapiens", "Leishmania mexicana"}
    assert parte["Homo sapiens"]["% sul totale assegnato"] == pytest.approx(0.054)
    assert parte["Leishmania mexicana"]["Gruppo"] == "altri eucarioti"
    assert parte["Bottigliavirus pozzuoliense"]["Gruppo"] == "virus"


def test_r5_parametri_fonti_citazioni_virus(referto):
    _, _, wb, html = referto
    par = {r["Parametro"]: r for r in righe(wb["Parametri"])}
    with open(os.path.join(ROOT, "refs", "kraken_profili.tsv"), encoding="utf-8") as f:
        fonte = next(r.split("\t")[4] for r in f.read().splitlines() if r.startswith("rapido\t"))
    for k in ("Confidenza di Kraken (--confidence)", "Letture minime di Bracken (-t)", "Soglia di abbondanza (%)"):
        assert par[k]["Fonte"] == fonte
    assert all(r["Fonte"] for r in par.values())
    assert "Strumenti e database usati" in html and "Wright, Comeau &amp; Langille 2023" in html
    assert "4.2.4" in html and "2.17.2" in html
    assert "opzione sperimentale" in html                       # D017, D033
    assert "Sicurezza alimentare" not in html and "Sicurezza" not in wb.sheetnames


def test_r5_sicurezza_solo_se_calcolata(tmp_path):
    p = prepara(tmp_path)
    richiesta = tmp_path / "r.json"
    richiesta.write_text(json.dumps({"prodotto": {"sale_fase_acquosa": 3.0, "ph": 5.4, "nitrito": 60}, "giorni": 30}),
                         encoding="utf-8")
    r = subprocess.run([sys.executable, FINTO, "sicurezza", "--ingresso", str(richiesta), "--progetto",
                        str(p / "config.yaml"), "--velocita", "0"], capture_output=True, text=True, encoding="utf-8")
    controlla(r.stdout, r.returncode, "sicurezza")
    fai_referto(p)
    html = (p / "risultati" / "referto" / "referto.html").read_text(encoding="utf-8")
    assert "Sicurezza alimentare" in html and "Food Spoilage and Safety Predictor" in html
    assert "pH 5,4" in html and "Attenzione" in html             # dati del prodotto e fuori campo
    assert "Sicurezza" in openpyxl.load_workbook(p / "risultati" / "referto" / "referto.xlsx").sheetnames


def test_r7_il_finto_ha_il_referto_vero_e_aggiornato(tmp_path):
    p = prepara(tmp_path)
    fai_referto(p)
    nuovo = (p / "risultati" / "referto" / "referto.html").read_text(encoding="utf-8")
    with open(os.path.join(DATI, "referto", "referto.html"), encoding="utf-8") as f:
        assert f.read() == nuovo, "installer/finto/referto/ non e' aggiornato: rifallo con motore/referto.py"


def test_r7_finto_esegui_e_referto(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("project_name: prova\n", encoding="utf-8")
    r = subprocess.run([sys.executable, FINTO, "esegui", "--progetto", str(cfg), "--velocita", "0"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    ev = controlla(r.stdout, r.returncode, "esegui")
    assert ev[-1]["risultato"]["referto"] == {"html": "referto/referto.html", "pdf": "referto/referto.pdf",
                                             "xlsx": "referto/referto.xlsx"}
    for f in ev[-1]["risultato"]["referto"].values():
        assert (tmp_path / "risultati" / f).is_file()
    r = subprocess.run([sys.executable, FINTO, "referto", "--progetto", str(cfg), "--velocita", "0"],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    ev = controlla(r.stdout, r.returncode, "referto")
    assert r.returncode == 0 and not [e for e in ev if e["tipo"] == "avviso"]
