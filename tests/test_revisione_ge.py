# -*- coding: utf-8 -*-
"""Revisione del 22/10, gruppo "GE-scienza": P00 (verdetto Listeria sull'intero profilo di temperatura) e P29
(soglia di Kraken sulle read intere di Bracken, non sulla frazione arrotondata a 5 decimali).
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_revisione_ge.py"""
import importlib.util
import os
import subprocess
import sys

import pytest

RADICE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RADICE, "motore"))
sys.path.insert(0, os.path.join(RADICE, "steps"))

_spec = importlib.util.spec_from_file_location("previsione_fssp", os.path.join(RADICE, "steps", "45_previsione_fssp.py"))
step45 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(step45)

PRODOTTO = {"sale_fase_acquosa": 3.5, "ph": 6.0, "nitrito": 60, "acidi": {"lattico": 12000, "diacetato": 1000}}


# ---------------- P00: "La Listeria può crescere?" guarda tutte le temperature del profilo ----------------
def test_p00_verdetto_guarda_tutto_il_profilo():
    """Profilo freddo e poi caldo: psi alla prima temperatura > 1 (fedele a FSSP), ma la curva cresce di 100 volte."""
    r = step45.esegui({"prodotto": PRODOTTO, "profilo_temperatura": [[2, 120], [10, 480]]}, 1.0)
    for p in r["previsioni"]:
        assert p["psi_listeria"] > 1.0                          # psi iniziale, invariato
        assert p["cento_volte_listeria_giorni"] is not None     # la curva cresce di 100 volte
        assert p["listeria_puo_crescere"] is True


def test_p00_primo_tratto_oltre_il_limite():
    """Primo tratto sotto la Tmin (psi None), poi 12 °C: il verdetto è "sì"."""
    r = step45.esegui({"prodotto": {"sale_fase_acquosa": 5.0, "ph": 5.4, "nitrito": 100, "acidi": {"lattico": 3000}},
                       "profilo_temperatura": [[-5, 72], [12, 240]]}, 1.0)
    for p in r["previsioni"]:
        assert p["psi_listeria"] is None
        assert p["listeria_puo_crescere"] is True



def test_p00_verdetto_col_modello_listeria_lab():
    """Con i batteri lattici nel profilo e una conta totale lo step 45 usa il modello Listeria + LAB: anche lì il
    verdetto guarda tutto il profilo (2 °C poi 10 °C), non solo lo psi alla prima temperatura."""
    r = step45.esegui({"prodotto": PRODOTTO, "profilo_temperatura": [[2, 120], [10, 480]],
                       "profilo_specie": {"s__Latilactobacillus_sakei": 20.0}, "conte": {"totale_ufc_g": 1e6}}, 1.0)
    assert r["ponte"]["lab_trovati"] and r["previsioni"]
    for p in r["previsioni"]:
        assert p["modello"] == "listeria_lab" and p["n0_lab_ufc_g"] == pytest.approx(2e5)
        assert p["psi_listeria"] > 1.0                          # psi iniziale, invariato
        assert p["listeria_puo_crescere"] is True

@pytest.mark.parametrize("temperatura, atteso", [(10.0, True), (2.0, False)])
def test_p00_temperatura_costante_come_prima(temperatura, atteso):
    """A temperatura costante (l'app manda solo questa) il verdetto resta psi iniziale < 1."""
    r = step45.esegui({"prodotto": dict(PRODOTTO, temperatura=temperatura), "giorni": 30}, 1.0)
    for p in r["previsioni"]:
        assert p["listeria_puo_crescere"] is (p["psi_listeria"] is not None and p["psi_listeria"] < 1.0) is atteso


# ---------------- P29: soglia di Kraken sulle read intere di Bracken ----------------
INTESTAZIONE = "name\ttaxonomy_id\ttaxonomy_lvl\tkraken_assigned_reads\tadded_reads\tnew_est_reads\tfraction_total_reads\n"


def bracken(cartella, nome, righe):
    """righe: [(nome, taxid, read, frazione scritta da Bracken con 5 decimali)]."""
    testo = INTESTAZIONE + "".join(f"{n}\t{t}\tS\t{r}\t0\t{r}\t{f}\n" for n, t, r, f in righe)
    (cartella / f"{nome}.bracken").write_text(testo, encoding="utf-8")


def matrice(cartella, *extra):
    r = subprocess.run([sys.executable, os.path.join(RADICE, "steps", "33_kraken_matrix.py"), "--in", str(cartella),
                        "--out", str(cartella / "m.tsv"), *extra], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return cartella / "m.tsv"


def test_p29_matrice_usa_le_read_intere(tmp_path):
    """64 read su 1.405.930 sono lo 0,00455 %: Bracken scrive 0.00005 (0,005 %), che passava la soglia rapido."""
    pytest.importorskip("pandas")
    from _profiling_io import load_kraken_matrix
    bracken(tmp_path, "S1", [("Listeria welshimeri", 1643, 64, "0.00005"),
                             ("Latilactobacillus sakei", 1599, 1405866, "0.99995")])
    m = matrice(tmp_path)
    valori = dict(r.split("\t") for r in m.read_text(encoding="utf-8").splitlines()[1:])
    assert float(valori["Listeria welshimeri"]) == pytest.approx(64 / 1405930 * 100, rel=1e-9)
    assert float(valori["Listeria welshimeri"]) < 0.005
    assert "listeria welshimeri" not in load_kraken_matrix(str(m), 0.005)
    assert "latilactobacillus sakei" in load_kraken_matrix(str(m), 0.005)


def test_p29_matrice_non_arrotonda_alla_soglia(tmp_path):
    """1 read su 20.001 è lo 0,0049998 %: con 6 decimali diventava 0.005000 e passava la soglia."""
    pytest.importorskip("pandas")
    from _profiling_io import load_kraken_matrix
    bracken(tmp_path, "S1", [("Raro", 1, 1, "0.00005"), ("Latilactobacillus sakei", 1599, 20000, "0.99995")])
    m = matrice(tmp_path)
    assert "raro" not in load_kraken_matrix(str(m), 0.005)


def test_p29_taxa_del_prodotto_usano_le_read_intere(tmp_path):
    """--taxa-out (beta di Kraken) filtra con la stessa percentuale esatta."""
    pd = pytest.importorskip("pandas")
    bracken(tmp_path, "S1", [("Listeria welshimeri", 1643, 64, "0.00005"),
                             ("Latilactobacillus sakei", 1599, 1405866, "0.99995")])
    (tmp_path / "S1.k2report").write_text("100.00\t1405930\t0\tR\t1\troot\n"
                                          "100.00\t1405930\t0\tD\t2\t  Bacteria\n"
                                          "0.00\t64\t64\tS\t1643\t    Listeria welshimeri\n"
                                          "100.00\t1405866\t1405866\tS\t1599\t    Latilactobacillus sakei\n",
                                          encoding="utf-8")
    matrice(tmp_path, "--taxa-out", str(tmp_path / "t.tsv"), "--threshold-pct", "0.005")
    taxa = pd.read_csv(tmp_path / "t.tsv", sep="\t", index_col=0)["S1"]
    assert set(taxa[taxa > 0].index) == {"Latilactobacillus sakei"}
