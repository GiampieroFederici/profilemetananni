# -*- coding: utf-8 -*-
"""Report in risultati/referto/ (HTML + Excel + PDF, contract v0.2). Criteria R1-R5, R7 of
sessioni/2026-10-16_motore_seconda_parte.md, on the real SF3RAt7 run of the fake engine data."""
import csv
import json
import os
import shutil
import subprocess
import sys
import unicodedata

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
    if len(v) > 1 and str(v[0][0]).startswith("Prototipo"):   # riga della scritta "prototipo" sopra le colonne
        v = v[1:]
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
    micro = {r["Specie"]: r for r in righe(wb["Kraken_taxa"])}
    with open(os.path.join(DATI, "SRR4875279.bracken"), encoding="utf-8") as f:
        letture = {r["name"]: int(r["new_est_reads"]) for r in csv.DictReader(f, delimiter="\t")}
    bracken = {n: 100 * v / sum(letture.values()) for n, v in letture.items()}   # read intere, non la frazione arrotondata (P29)
    assert micro["Latilactobacillus sakei"]["% sul totale assegnato"] == pytest.approx(bracken["Latilactobacillus sakei"])
    somma_microbi = sum(bracken[n] for n in micro)
    assert micro["Latilactobacillus sakei"]["% fra i taxa"] == pytest.approx(
        100 * bracken["Latilactobacillus sakei"] / somma_microbi)
    assert sum(r["% fra i taxa"] for r in micro.values()) == pytest.approx(100.0)
    assert micro["Debaryomyces hansenii"]["Gruppo"] == "funghi"


def test_r3_metaphlan_e_kraken_mai_insieme(referto):
    _, _, wb, html = referto
    assert {"MetaPhlAn_specie", "Kraken_taxa", "Kraken_a_parte"} <= set(wb.sheetnames)
    sez_mpa = html.split("2. Specie trovate con MetaPhlAn")[1].split("3. Taxa trovati con Kraken")[0]
    sez_krk = html.split("3. Taxa trovati con Kraken")[1].split("5. Virus")[0]
    assert "Proteus vulgaris" not in sez_mpa and "Proteus vulgaris" in sez_krk          # solo Kraken
    assert "Candida parapsilosis" in sez_mpa and "Candida parapsilosis" not in sez_krk  # solo MetaPhlAn
    assert not any(r["Specie"] == "Proteus vulgaris" for r in righe(wb["MetaPhlAn_specie"]))


def test_r4_homo_e_leishmania_a_parte(referto):
    _, _, wb, _ = referto
    micro = {r["Specie"] for r in righe(wb["Kraken_taxa"])}
    parte = {r["Nome"]: r for r in righe(wb["Kraken_a_parte"])}
    assert not micro & {"Homo sapiens", "Leishmania mexicana"}
    assert parte["Homo sapiens"]["% sul totale assegnato"] == pytest.approx(74 / 136004 * 100)   # read intere (P29)
    assert parte["Leishmania mexicana"]["Gruppo"] == "altri eucarioti"
    assert parte["Bottigliavirus pozzuoliense"]["Gruppo"] == "virus"


def test_r5_parametri_fonti_citazioni_virus(referto):
    _, _, wb, html = referto
    par = {r["Parametro"]: r for r in righe(wb["Parametri"])}
    with open(os.path.join(ROOT, "refs", "kraken_profili.tsv"), encoding="utf-8") as f:
        fonte = next(r.split("\t")[4] for r in f.read().splitlines() if r.startswith("rapido\t"))
    for k in ("Confidenza di Kraken (--confidence)", "Letture minime di Bracken (-t)", "Soglia di abbondanza di Kraken (%)"):
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
    # v0.2 (richieste 6-7 di S4): sintesi pronta, MetaPhlAn e Kraken separati, non microbi a parte
    s = ev[-1]["risultato"]["campioni"][0]["sintesi"]
    assert s["metaphlan"]["specie"] == 27 and s["metaphlan"]["non_assegnata_pct"] == pytest.approx(53.651104)
    assert s["metaphlan"]["dominanti"][0]["nome"] == "Latilactobacillus sakei"
    assert s["kraken"]["microbi"] == 48 and s["kraken"]["dominanti"][0]["nome"] == "Latilactobacillus sakei"
    parte = {x["nome"]: x for x in s["kraken"]["non_microbi"]}
    assert parte["Homo sapiens"]["pct"] == pytest.approx(74 / 136004 * 100) and parte["Leishmania mexicana"]["gruppo"] == "altri eucarioti"
    assert "53,7 %" in s["metaphlan"]["frase"] and "Homo sapiens 0,054 %" in s["kraken"]["frase"]
    r = subprocess.run([sys.executable, FINTO, "referto", "--progetto", str(cfg), "--velocita", "0"],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    ev = controlla(r.stdout, r.returncode, "referto")
    assert r.returncode == 0 and not [e for e in ev if e["tipo"] == "avviso"]

# ---------------- 20/10: limiti dichiarati (D141, D142) e "prototipo" nell'Excel (D115) ----------------
def test_limite_di_kraken_e_di_metaphlan_dichiarati(referto):
    """Due frasi: la soglia di Kraken coi valori VERI della corsa (qui rapido: 0,1 e 0,005 %) e il limite di
    rilevamento di MetaPhlAn con molto ospite (numeri di L3). Nell'HTML (e quindi nel PDF) e nel foglio Leggimi."""
    _, _, wb, html = referto
    sez_mpa = html.split("2. Specie trovate con MetaPhlAn")[1].split("3. Taxa trovati con Kraken")[0]
    sez_krk = html.split("3. Taxa trovati con Kraken")[1].split("4. ")[0]
    assert ("Kraken mostra solo i taxa con almeno lo 0,005 % delle read assegnate da Bracken (non classificate "
            "escluse; confidence 0,1).") in sez_krk
    assert "da 196 a 64 su 12 campioni" in sez_krk and "da 10 a 0" in sez_krk
    assert "compresa <i>Listeria monocytogenes</i>, non compaiono nel profilo di Kraken" in sez_krk
    assert "MetaPhlAn non usa soglie" in sez_mpa and "circa 1.800 coppie" in sez_mpa and "fino allo 0,4 %" in sez_mpa
    assert "tarate su comunità simulate e su un campione di controllo (Zymo), non ancora su salumi veri" in sez_krk
    leggimi = " ".join(str(r[0]) for r in wb["Leggimi"].values if r and r[0])
    assert "Kraken mostra solo i taxa con almeno lo 0,005 %" in leggimi and "MetaPhlAn non usa soglie" in leggimi
    assert "<i>" not in leggimi                                                   # niente HTML nell'Excel


def test_limiti_nel_pdf(referto):
    pymupdf = pytest.importorskip("pymupdf")                                          # PyMuPDF legge il PDF vero
    _, esito, _, _ = referto
    def testo(pdf):                                                                # NFKC: legature come "ﬁ"
        return unicodedata.normalize("NFKC", " ".join(" ".join(pg.get_text().split()) for pg in pymupdf.open(pdf)))
    testo = testo(esito["pdf"]).strip() or testo(os.path.join(DATI, "referto", "referto.pdf"))   # Qt senza caratteri (Windows):
    # il PDF del finto motore, fatto col Python del motore (test_r7 tiene aggiornato il suo HTML)
    assert "Listeria monocytogenes, non compaiono nel profilo di Kraken" in testo and "MetaPhlAn non usa soglie" in testo


def test_prototipo_nei_fogli_kraken_e_sicurezza(tmp_path):
    p = prepara(tmp_path)
    richiesta = tmp_path / "r.json"
    richiesta.write_text(json.dumps({"prodotto": {"sale_fase_acquosa": 3.0, "ph": 5.4, "nitrito": 60}, "giorni": 30}),
                         encoding="utf-8")
    r = subprocess.run([sys.executable, FINTO, "sicurezza", "--ingresso", str(richiesta), "--progetto",
                        str(p / "config.yaml"), "--velocita", "0"], capture_output=True, text=True, encoding="utf-8")
    controlla(r.stdout, r.returncode, "sicurezza")
    fai_referto(p)
    wb = openpyxl.load_workbook(p / "risultati" / "referto" / "referto.xlsx")
    for nome in ("Kraken_taxa", "Kraken_a_parte", "Diversità_Kraken", "Sicurezza"):
        prima = wb[nome]["A1"].value
        assert prima.startswith("Prototipo, non per decisioni.") and "<b>" not in prima, nome
        if nome != "Sicurezza":                                                   # K4 fatta: testo nuovo
            assert "non ancora su salumi veri" in prima and "ancora in prova" not in prima, nome
        assert righe(wb[nome]) and "Campione" in righe(wb[nome])[0], nome     # le colonne restano sotto
    for nome in ("MetaPhlAn_specie", "Diversità_MetaPhlAn", "Parametri"):
        assert not str(wb[nome]["A1"].value).startswith("Prototipo"), nome
