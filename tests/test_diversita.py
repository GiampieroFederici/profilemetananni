# -*- coding: utf-8 -*-
"""Diversità alfa a profondità uguale (R1, 18/10/2026; criteri CD1-CD8 del diario della sessione R1).

MetaPhlAn e Kraken sempre separati. Kraken: valore atteso esatto della rarefazione delle letture di Bracken (taxa del
prodotto sopra la soglia D128). MetaPhlAn: nessuna soglia; profondità uguale con un sottocampione delle read del
mapout (seme 1992) e MetaPhlAn rifatto. Gira con la suite del motore (pmn_reports_py) e con l'ambiente dell'app."""
import math
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "motore"))
import diversita  # noqa: E402
import referto  # noqa: E402

PASSO = ROOT / "steps" / "42_alpha_equal_depth.py"


# ---------------- indici e rarefazione ----------------
def media_estrazioni(conteggi, n, volte=20000, seme=7):
    """Media dei 3 indici su molte estrazioni casuali senza reinserimento (il metodo "a forza bruta")."""
    rnd = random.Random(seme)
    urna = [i for i, c in enumerate(conteggi) for _ in range(c)]
    somma = {"ricchezza": 0.0, "shannon": 0.0, "simpson": 0.0}
    for _ in range(volte):
        conta = {}
        for i in rnd.sample(urna, n):
            conta[i] = conta.get(i, 0) + 1
        for k, v in diversita.indici(list(conta.values())).items():
            somma[k] += v
    return {k: v / volte for k, v in somma.items()}


def test_rarefazione_esatta_uguale_alla_media_di_molte_estrazioni():
    conteggi, n = [50, 30, 10, 5, 3, 1, 1], 20
    esatto = diversita.rarefazione_attesa(conteggi, n)
    forza_bruta = media_estrazioni(conteggi, n)
    for k in ("ricchezza", "shannon", "simpson"):
        assert esatto[k] == pytest.approx(forza_bruta[k], rel=0.01), k


def test_rarefazione_su_conteggi_grandi_resta_veloce_e_coerente():
    conteggi = [600_000, 250_000, 90_000, 40_000, 15_000, 4_000, 800, 120, 30, 11]
    tutto = diversita.indici(conteggi)
    meta = diversita.rarefazione_attesa(conteggi, sum(conteggi) // 2)
    assert meta["ricchezza"] <= tutto["ricchezza"]
    assert meta["simpson"] == pytest.approx(tutto["simpson"], abs=1e-4)       # Simpson quasi non dipende dalla profondità
    assert meta["shannon"] == pytest.approx(tutto["shannon"], abs=1e-3)


def test_a_profondita_piena_gli_indici_diretti():
    conteggi = [7, 3, 2, 1]
    assert diversita.rarefazione_attesa(conteggi, sum(conteggi)) == diversita.indici(conteggi)
    d = diversita.indici([1, 1, 2])
    assert d["ricchezza"] == 3
    assert d["shannon"] == pytest.approx(-(2 * 0.25 * math.log(0.25) + 0.5 * math.log(0.5)))
    assert d["simpson"] == pytest.approx(1 - (0.25 ** 2 * 2 + 0.25))


# ---------------- Kraken ----------------
def riga(nome, cat, letture, pct):
    return {"nome": nome, "categoria": cat, "letture": letture, "pct": pct, "taxid": "1", "pct_microbi": None}


def test_kraken_solo_taxa_del_prodotto_sopra_la_soglia():
    righe = [riga("Latilactobacillus sakei", "batteri", 9000, 60.0), riga("Debaryomyces hansenii", "funghi", 900, 6.0),
             riga("Homo sapiens", "altri eucarioti", 4000, 26.0), riga("Leishmania mexicana", "altri eucarioti", 900, 6.0),
             riga("Phage x", "virus", 100, 0.7), riga("Rarus rarus", "batteri", 1, 0.004)]
    t = diversita.tabella_kraken({"A": righe}, 0.005, referto.MICROBI)
    assert [r["campione"] for r in t] == ["A"]
    assert t[0]["letture"] == 9900 and t[0]["letture_usate"] == 9900 and t[0]["stato"] == "intero"
    assert t[0]["ricchezza"] == 2                       # Homo, Leishmania, virus e il taxon sotto soglia non contano
    s = referto.sintesi({"kraken": righe}, 0.005)       # CD7: stessa ricchezza della sintesi con un solo campione
    assert s["kraken"]["microbi"] == t[0]["ricchezza"]


def test_kraken_profondita_uguale_alla_piu_bassa():
    a = [riga("X", "batteri", 800, 80.0), riga("Y", "batteri", 150, 15.0), riga("Z", "batteri", 50, 5.0)]
    b = [riga("X", "batteri", 70, 70.0), riga("Y", "batteri", 30, 30.0)]
    t = {r["campione"]: r for r in diversita.tabella_kraken({"A": a, "B": b}, 0.005, referto.MICROBI)}
    assert t["A"]["letture_usate"] == t["B"]["letture_usate"] == 100
    assert t["A"]["stato"] == "pareggiato" and t["B"]["stato"] == "intero"
    assert t["A"]["ricchezza"] == pytest.approx(diversita.rarefazione_attesa([800, 150, 50], 100)["ricchezza"])
    assert 2 < t["A"]["ricchezza"] < 3


# ---------------- MetaPhlAn ----------------
def test_metaphlan_senza_soglia_e_un_solo_campione():
    specie = [("Latilactobacillus sakei", 40.0), ("Rara rarissima", 0.0001)]
    t = diversita.tabella_metaphlan({"A": (specie, 183241)}, {})
    assert t[0]["ricchezza"] == 2 and t[0]["stato"] == "intero" and t[0]["letture_usate"] == 183241
    assert t[0]["simpson"] == pytest.approx(diversita.indici([40.0, 0.0001])["simpson"])


def test_metaphlan_profondita_uguale_con_il_profilo_rifatto():
    a = ([("X", 50.0), ("Y", 30.0), ("Z", 0.01)], 2_000_000)
    b = ([("X", 60.0), ("Y", 20.0)], 1_000_000)
    pari = {"A": ([("X", 52.0), ("Y", 28.0)], 1_000_000)}
    t = {r["campione"]: r for r in diversita.tabella_metaphlan({"A": a, "B": b}, pari)}
    assert t["A"]["stato"] == "pareggiato" and t["A"]["ricchezza"] == 2 and t["A"]["letture_usate"] == 1_000_000
    assert t["B"]["stato"] == "intero"
    # senza il profilo rifatto (o rifatto a un'altra profondità) si dice, non si inventa (CD6)
    for p in ({}, {"A": ([("X", 1.0)], 999)}):
        t = {r["campione"]: r for r in diversita.tabella_metaphlan({"A": a, "B": b}, p)}
        assert t["A"]["stato"] == "non_pareggiato" and t["A"]["letture_usate"] == 2_000_000 and t["A"]["ricchezza"] == 3


def test_letture_dal_profilo_di_metaphlan():
    assert diversita.letture_profilo(ROOT / "installer" / "finto" / "SRR4875279_profile.txt") > 0


def fai_mapout(f, n_read, n_mappate, seme=3):
    rnd = random.Random(seme)
    righe = [f"read{i}__1\tmarker{rnd.randrange(40)}" for i in range(n_mappate)]
    rnd.shuffle(righe)                                   # Bowtie2 con più processori cambia l'ordine delle righe
    f.write_text("\n".join(righe) + f"\n#nreads\t{n_read}\n#avg_read_length\t148.5\n", encoding="utf-8")


def test_sottocampione_del_mapout(tmp_path):
    fai_mapout(tmp_path / "a.mapout", 10_000, 1_000, seme=3)
    fai_mapout(tmp_path / "b.mapout", 10_000, 1_000, seme=4)          # stesse righe, altro ordine
    na = diversita.sottocampiona_mapout(tmp_path / "a.mapout", tmp_path / "a_pari.mapout", 5_000)
    nb = diversita.sottocampiona_mapout(tmp_path / "b.mapout", tmp_path / "b_pari.mapout", 5_000)
    testo_a = (tmp_path / "a_pari.mapout").read_text(encoding="utf-8")
    assert re.search(r"^#nreads\t5000$", testo_a, re.M) and re.search(r"^#avg_read_length\t148.5$", testo_a, re.M)
    tenute = lambda t: sorted(r.split("\t")[0] for r in t.splitlines() if not r.startswith("#"))  # noqa: E731
    assert tenute(testo_a) == tenute((tmp_path / "b_pari.mapout").read_text(encoding="utf-8"))   # seme fisso, ordine no
    assert na == nb and abs(na - 500) < 75                           # attese 1.000 x 5.000 / 10.000 = 500
    with pytest.raises(ValueError):
        diversita.sottocampiona_mapout(tmp_path / "a.mapout", tmp_path / "x.mapout", 20_000)


# ---------------- passo della pipeline ----------------
def scrivi_profilo(f, letture, specie):
    righe = ["#mpa_vJan25_CHOCOPhlAnSGB_202503", "#metaphlan prova", f"#{letture} reads processed",
             f"#SampleID\t{f.stem[:-len('_profile')]}", "#clade_name\tNCBI_tax_id\trelative_abundance\tadditional_species",
             "UNCLASSIFIED\t-1\t10.0\t"]
    righe += [f"k__Bacteria|p__F|c__B|o__L|f__L|g__G|s__{n.replace(' ', '_')}\t1|2\t{v}\t" for n, v in specie]
    f.write_text("\n".join(righe) + "\n", encoding="utf-8")


def test_passo_42_sottocampiona_e_calcola(tmp_path):
    mpa, krk, res = tmp_path / "metaphlan", tmp_path / "kraken", tmp_path / "results"
    mpa.mkdir()
    krk.mkdir()
    scrivi_profilo(mpa / "A_profile.txt", 10_000, [("X", 60.0), ("Y", 30.0)])
    scrivi_profilo(mpa / "B_profile.txt", 4_000, [("X", 90.0)])
    fai_mapout(mpa / "A.mapout", 10_000, 1_000)
    fai_mapout(mpa / "B.mapout", 4_000, 400)
    for s in ("A", "B"):
        shutil.copy(ROOT / "installer" / "finto" / "SRR4875279.bracken", krk / f"{s}.bracken")
        shutil.copy(ROOT / "installer" / "finto" / "SRR4875279.k2report", krk / f"{s}.k2report")
    r = subprocess.run([sys.executable, str(PASSO), "sottocampiona", "--metaphlan-dir", str(mpa),
                        "--out", str(res / "alpha_metaphlan_pari")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in (res / "alpha_metaphlan_pari").iterdir()) == ["A.mapout"]   # B è già il più povero
    # MetaPhlAn rifatto (qui finto): profilo a 4.000 read
    scrivi_profilo(res / "alpha_metaphlan_pari" / "A_profile.txt", 4_000, [("X", 65.0)])
    r = subprocess.run([sys.executable, str(PASSO), "calcola", "--metaphlan-dir", str(mpa), "--pari-dir",
                        str(res / "alpha_metaphlan_pari"), "--kraken-dir", str(krk), "--threshold-pct", "0.005",
                        "--out", str(res)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    m = (res / "alpha_diversity_metaphlan.tsv").read_text(encoding="utf-8").splitlines()
    k = (res / "alpha_diversity_kraken.tsv").read_text(encoding="utf-8").splitlines()
    assert m[0].split("\t") == ["sample", "reads", "reads_used", "status", "richness", "shannon", "simpson"] == k[0].split("\t")
    assert m[1].split("\t")[:5] == ["A", "10000", "4000", "equalized", "1"]
    assert m[2].split("\t")[:5] == ["B", "4000", "4000", "full", "1"]
    assert len(k) == 3                                               # due campioni, un solo file per Kraken (CD1)


def test_run_sh_lancia_il_passo_42_prima_di_41_separato_per_strumento():
    testo = (ROOT / "bin" / "run.sh").read_text(encoding="utf-8")
    assert testo.index("42_alpha_equal_depth.py\" sottocampiona") < testo.index("42_alpha_equal_depth.py\" calcola") \
        < testo.index("steps/41_diversity.R\"")
    div = [r for r in testo.splitlines() if "41_diversity.R" in r and "do_step" in r]
    assert any("alpha_diversity_metaphlan.tsv" in r and "div_mpa" in r for r in div)
    assert any("alpha_diversity_kraken.tsv" in r and "div_krk" in r for r in div)


def rscript():
    for c in (shutil.which("Rscript"), Path(sys.executable).resolve().parent.parent.parent / "pmn_stats_r" / "bin" / "Rscript"):
        if c and Path(c).is_file():
            return str(c)
    return None


@pytest.mark.skipif(rscript() is None, reason="R (pmn_stats_r) non c'è qui")
def test_41_usa_l_alfa_a_profondita_uguale(tmp_path):
    """CD8: 41_diversity.R non calcola più un'alfa sua (era senza rarefazione): riporta quella del passo 42."""
    (tmp_path / "m.tsv").write_text("species\tA\tB\tC\nX\t50\t60\t70\nY\t30\t30\t20\nZ\t20\t10\t10\n", encoding="utf-8")
    (tmp_path / "a.tsv").write_text("sample\treads\treads_used\tstatus\trichness\tshannon\tsimpson\n"
                                    "A\t9\t5\tequalized\t2.5\t0.7\t0.4\nB\t5\t5\tfull\t2\t0.6\t0.3\n"
                                    "C\t7\t5\tequalized\t2.25\t0.5\t0.2\n", encoding="utf-8")
    r = subprocess.run([rscript(), str(ROOT / "steps" / "41_diversity.R"), "--matrix", str(tmp_path / "m.tsv"),
                        "--alpha", str(tmp_path / "a.tsv"), "--out", str(tmp_path / "out")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    righe = (tmp_path / "out" / "alpha_diversity.csv").read_text(encoding="utf-8").splitlines()
    assert righe[1].replace('"', "").split(",")[:4] == ["A", "2.5", "0.7", "0.4"]
    assert (tmp_path / "out" / "pca_aitchison.png").is_file()


# ---------------- referto ----------------
def test_referto_ha_la_sezione_diversita(tmp_path):
    """HTML, PDF ed Excel: sezione "Diversità" con l'avviso sulla profondità, MetaPhlAn e Kraken in due tabelle."""
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("PySide6.QtGui")
    sys.path.insert(0, str(ROOT / "tests"))
    from test_referto import fai_referto, prepara, righe
    p = prepara(tmp_path)
    esito = fai_referto(p)
    assert esito["problemi"] == []
    html = (p / "risultati" / "referto" / "referto.html").read_text(encoding="utf-8")
    sezione = html.split("<h2>4. Diversità")[1].split("<h2>5.")[0]
    assert "stessa profondità" in sezione and "un solo campione" in sezione
    assert sezione.count("<table border=\"1\"") == 2                 # MetaPhlAn e Kraken separati (CD1)
    assert sezione.index("MetaPhlAn") < sezione.index("Kraken")
    assert not re.search(r"\bmicrob[oi]\b", sezione, re.I)
    wb = openpyxl.load_workbook(p / "risultati" / "referto" / "referto.xlsx")
    mpa, krk = righe(wb["Diversità_MetaPhlAn"]), righe(wb["Diversità_Kraken"])
    assert len(mpa) == len(krk) == 1
    sintesi = referto.sintesi(referto.leggi_campione(p / "risultati", {"metaphlan": "metaphlan/SRR4875279_profile.txt",
                                                                          "kraken": "kraken/SRR4875279.bracken"}), 0.005)
    assert mpa[0]["Specie (ricchezza)"] == sintesi["metaphlan"]["specie"]          # CD7
    assert krk[0]["Taxa (ricchezza)"] == sintesi["kraken"]["microbi"]
    assert (p / "risultati" / "referto" / "referto.pdf").read_bytes()[:4] == b"%PDF"


def test_stima_conta_metaphlan_rifatto_per_i_campioni_in_piu():
    import pmn_motore as pm
    uno, due = [("A", 1_000_000, 0)], [("A", 1_000_000, 0), ("B", 2_000_000, 0)]
    assert pm.tempi(uno, {})["riepilogo"] == pm.ALTRI_S["riepilogo"]
    assert pm.tempi(due, {})["riepilogo"] == pm.ALTRI_S["riepilogo"] + pm.ALFA_MPA_S
    assert pm.tempi(due, {"profiling": {"tool": "kraken"}})["riepilogo"] == pm.ALTRI_S["riepilogo"]
    assert pm.tempi(due, {"analysis": {"diversity": False}})["riepilogo"] == pm.ALTRI_S["riepilogo"]
