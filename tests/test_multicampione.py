# -*- coding: utf-8 -*-
"""Analisi multicampione (R11, PMN 1.1): metadati, scelta dei test dal disegno, PERMANOVA sempre con PERMDISP,
permutazioni ristrette per le misure ripetute, MetaPhlAn e Kraken separati, sezione nel referto.

Dati finti a disegno noto (seme fisso). Le prove con R girano con la suite del motore (pmn_reports_py nella WSL, R
dell'ambiente accanto pmn_stats_r); senza R si saltano. I numeri di vegan si ricontrollano con un calcolo
indipendente in Python (distanze e pseudo-F) e, se c'è scipy, con Mann-Whitney e Kruskal-Wallis di scipy."""
import csv
import json
import math
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "motore"))
import diversita  # noqa: E402
import multicampione as mc  # noqa: E402

R = mc.rscript()
con_r = pytest.mark.skipif(R is None, reason="R (pmn_stats_r) non c'è qui")


# ---------------- metadati ----------------
def test_modello_creato_una_volta_sola(tmp_path):
    assert not mc.crea_modello(tmp_path, ["A"])                       # un campione: niente modello
    assert mc.crea_modello(tmp_path, ["B", "A"])
    assert (tmp_path / "metadati.tsv").read_text(encoding="utf-8") == ("sample_id\tgroup\tsubject\ttimepoint\t"
                                                                       "covariate\nA\t\t\t\t\nB\t\t\t\t\n")
    (tmp_path / "metadati.tsv").write_text("sample_id\tgroup\nA\tx\n", encoding="utf-8")
    assert not mc.crea_modello(tmp_path, ["A", "B"])                  # mai sopra il file dell'utente
    assert "x" in (tmp_path / "metadati.tsv").read_text(encoding="utf-8")


def test_metadati_da_excel_e_controlli(tmp_path):
    f = tmp_path / "metadati.tsv"
    f.write_bytes("﻿sample_id\tgroup\tsubject\ttimepoint\tlotto\r\n# commento\r\nA\tx\ts1\t0\tL1\r\n"
                  "A\ty\t\t\t\r\nB\tx\t\t\t\r\nZ\tx\t\t\t\r\n".encode("utf-8"))
    meta, problemi, cov = mc.leggi_metadati(f, ["A", "B", "C"])
    assert meta["A"] == {"group": "x", "subject": "s1", "timepoint": "0", "lotto": "L1"}   # prima riga di A
    assert cov == ["lotto"]
    testo = " | ".join(problemi)
    assert "più righe: A" in testo and "una riga per campione" in testo
    assert "Mancano i dati di questi campioni" in testo and ": C." in testo   # campione del progetto senza riga
    assert "non corrispondono" in testo and ": Z." in testo                     # riga in più
    assert "Tutti i campioni hanno lo stesso gruppo (x)" in testo
    assert "non hanno il tempo e restano fuori dal confronto per tempo: B." in testo   # B senza timepoint
    m = {f"S{i}": {"group": "AB"[i < 2]} for i in range(5)}                              # A: 3 campioni, B: 2
    assert mc.controlla_fattori(m, sorted(m)) == [
        "Per un test servono almeno 3 campioni per ogni gruppo; ne hanno meno: B (2). Aggiungi campioni oppure unisci "
        "questi valori a un altro gruppo: intanto si mostrano solo grafici e valori."]


def test_valori_vuoti_dicono_che_cosa_fare(tmp_path):
    f = tmp_path / "metadati.tsv"
    f.write_text("sample_id\tgroup\n" + "".join(f"S{i}\t{'AB'[i % 2] if i else ''}\n" for i in range(7)),
                 encoding="utf-8")
    problemi = mc.leggi_metadati(f, [f"S{i}" for i in range(7)])[1]
    assert problemi == ["Questi campioni non hanno il gruppo e restano fuori dal confronto per gruppo: S0. Scrivi il "
                        "loro gruppo, oppure lascialo vuoto per tutti."]


def test_metadati_non_usabili(tmp_path):
    f = tmp_path / "metadati.tsv"
    assert mc.leggi_metadati(f, ["A"]) == (None, [], [])               # file assente: nessun problema, nessun test
    f.write_text("sample_id;group\nA;x\n", encoding="utf-8")
    meta, problemi, _ = mc.leggi_metadati(f, ["A"])
    assert meta is None and "tabulazioni" in problemi[0]
    f.write_text("campione\tgroup\nA\tx\n", encoding="utf-8")
    meta, problemi, _ = mc.leggi_metadati(f, ["A"])
    assert meta is None and "sample_id" in problemi[0]
    f.write_bytes("sample_id\tgroup\nA\tsalame à\n".encode("cp1252"))   # salvato da Excel come "Testo (Windows)"
    assert mc.leggi_metadati(f, ["A"])[0]["A"]["group"] == "salame à"


# ---------------- disegno e test scelti ----------------
def meta_di(righe):
    return {s: dict(zip(("group", "subject", "timepoint"), v)) for s, *v in righe}


def un(confronti, fattore="group"):
    return next(c for c in confronti if c["fattore"] == fattore)


def test_due_gruppi_indipendenti_mann_whitney():
    m = meta_di([(f"S{i}", "A" if i < 3 else "B", "", "") for i in range(6)])
    c = un(mc.piano(m, sorted(m)))
    assert (c["disegno"], c["test_alfa"], c["permutazioni"]) == ("independent", "mann_whitney", "free")
    assert "Mann-Whitney" in c["motivo"]


def test_tre_gruppi_kruskal_e_un_gruppo_piccolo():
    m = meta_di([(f"S{i}", "ABC"[i % 3], "", "") for i in range(9)])
    assert un(mc.piano(m, sorted(m)))["test_alfa"] == "kruskal_dunn"
    m["S9"] = {"group": "D"}                                         # gruppo D con un solo campione
    c = un(mc.piano(m, sorted(m)))
    assert c["test_alfa"] == "none" and c["permutazioni"] == "none" and c["solo_descrittive"]
    assert "almeno 3" in c["motivo"] and "D" in c["motivo"]


def test_appaiati_e_ripetuti_dentro_il_soggetto():
    m = meta_di([(f"{s}_{t}", "", s, t) for s in ("s1", "s2", "s3", "s4") for t in ("t0", "t1")])
    c = un(mc.piano(m, sorted(m)), "timepoint")
    assert (c["disegno"], c["test_alfa"], c["permutazioni"]) == ("paired", "wilcoxon_paired", "blocks")
    m = meta_di([(f"{s}_{t}", "", s, t) for s in ("s1", "s2", "s3", "s4") for t in ("t0", "t1", "t2")])
    del m["s4_t2"]                                                   # s4 incompleto: fuori da Friedman, dentro la beta
    c = un(mc.piano(m, sorted(m)), "timepoint")
    assert (c["disegno"], c["test_alfa"], c["permutazioni"]) == ("repeated", "friedman", "blocks")
    assert sum(r["alpha"] for r in c["righe"]) == 9 and sum(r["beta"] for r in c["righe"]) == 11
    assert "3 soggetti con dati completi" in c["motivo"]


def test_soggetti_dentro_i_gruppi_media_del_soggetto():
    m = meta_di([(f"{g}{s}_{k}", g, f"{g}{s}", "") for g in "AB" for s in range(3) for k in range(2)])
    c = un(mc.piano(m, sorted(m)))
    assert (c["disegno"], c["test_alfa"], c["permutazioni"]) == ("between_subjects", "mann_whitney", "subject_mean")
    assert "soggetto" in c["motivo"]


def test_senza_metadati_nessun_confronto():
    assert mc.piano(None, ["A", "B"]) == [] and mc.piano({"A": {"group": "x"}, "B": {"group": "x"}}, ["A", "B"]) == []


def test_matrici_separate_e_soglia_solo_kraken():
    camp = [{"nome": "A", "metaphlan": [("x", 0.001), ("y", 9.0)],
             "kraken": [{"nome": "x", "categoria": "batteri", "pct": 0.001, "letture": 1},
                        {"nome": "y", "categoria": "batteri", "pct": 90.0, "letture": 90},
                        {"nome": "Homo sapiens", "categoria": "altri eucarioti", "pct": 9.9, "letture": 9}]}]
    assert set(mc.matrice(camp, "metaphlan", 0.005)["A"]) == {"x", "y"}        # MetaPhlAn mai filtrato
    assert mc.matrice(camp, "kraken", 0.005)["A"] == {"y": 1.0}                # Kraken: soglia e solo taxa del prodotto


# ---------------- dati finti a disegno noto, con R ----------------
TAXA = [f"Taxon_{i}" for i in range(10)]


def composizione(base, rnd, sd):
    v = [b * math.exp(rnd.gauss(0, sd)) for b in base]
    return [(t, 100 * x / sum(v)) for t, x in zip(TAXA, v)]


def progetto(tmp_path, campioni, metadati=None):
    """risultati/ di un progetto finto (solo MetaPhlAn) e d come lo prepara referto.raccogli."""
    (tmp_path / "risultati").mkdir(parents=True)
    if metadati is not None:
        (tmp_path / "metadati.tsv").write_text("sample_id\tgroup\tsubject\ttimepoint\n" + "".join(
            "\t".join(r) + "\n" for r in metadati), encoding="utf-8")
    alfa = [{"campione": n, "letture": 1000, "letture_usate": 1000, "stato": "intero",
             **diversita.indici([p for _, p in sp])} for n, sp in sorted(campioni.items())]
    d = {"campioni": [{"nome": n, "metaphlan": sp, "kraken": None} for n, sp in sorted(campioni.items())],
         "soglia": 0.005, "diversita": {"metaphlan": alfa, "kraken": []}}
    return tmp_path / "risultati", d


def tsv(f):
    with open(f, encoding="utf-8", newline="") as t:
        return list(csv.DictReader(t, delimiter="\t"))


def beta(cartella, distanza, test, confronto="group"):
    return next(r for r in tsv(cartella / "beta_tests.tsv")
                if r["distance"] == distanza and r["test"] == test and r["comparison"] == confronto)


def due_gruppi_diversi(tmp_path):
    rnd = random.Random(11)
    a, b = [40, 30, 15, 5, 4, 2, 1, 1, 1, 1], [1, 1, 1, 2, 4, 5, 15, 30, 40, 1]
    camp = {f"A{i}": composizione(a, rnd, 0.3) for i in range(6)} | {f"B{i}": composizione(b, rnd, 0.3) for i in range(6)}
    return progetto(tmp_path, camp, [(s, s[0], "", "") for s in camp])


@con_r
def test_due_gruppi_molto_diversi_permanova_si_permdisp_no(tmp_path):
    risultati, d = due_gruppi_diversi(tmp_path)
    rie = mc.esegui(risultati, d)
    cart = risultati / "multicampione" / "metaphlan"
    assert rie["profiler"]["metaphlan"]["errore"] is None, (cart / "R_log.txt").read_text(encoding="utf-8")
    assert not (risultati / "multicampione" / "kraken").exists()     # niente Kraken: niente cartella
    for dist in ("aitchison", "braycurtis"):
        pa, pd = beta(cart, dist, "PERMANOVA"), beta(cart, dist, "PERMDISP")
        # 6 + 6 campioni: 462 divisioni distinte (ognuna vale due volte), quindi p minimo vicino a 2/924
        assert float(pa["p"]) <= 0.01 and float(pa["R2"]) > 0.5 and pa["permutations"] == "999"
        assert float(pd["p"]) > 0.05 and pa["dispersion_differs"] == "no"
    mw = [r for r in tsv(cart / "alpha_tests.tsv") if r["metric"] == "shannon"][0]
    assert mw["test"] == "mann_whitney" and mw["n"] == "12" and mw["effect_size_name"] == "r"
    for f in ("alpha_group.png", "alpha_group.pdf", "pcoa_aitchison_group.png", "pcoa_braycurtis_group.pdf",
              "alpha_samples.png", "pcoa_aitchison.png"):
        assert (cart / f).stat().st_size > 1000
    par = {r["parameter"]: r["value"] for r in tsv(cart / "parametri.tsv")}
    assert par["seed"] == "1992" and par["permutations"] == "999" and par["abundance_threshold_pct"] == "none"
    assert re.match(r"\d", par["vegan"]) and par["R"].startswith("R version") and float(par["zero_replacement"]) > 0


@con_r
def test_vegan_uguale_al_calcolo_indipendente(tmp_path):
    """Distanze di Aitchison e Bray-Curtis e pseudo-F/R² della PERMANOVA rifatti qui, a mano, dai file di ingresso."""
    risultati, d = due_gruppi_diversi(tmp_path)
    mc.esegui(risultati, d)
    cart = risultati / "multicampione" / "metaphlan"
    ab = tsv(cart / "abundance_relative.tsv")
    campioni = [c for c in ab[0] if c != "taxon"]
    P = {s: [float(r[s]) for r in ab] for s in campioni}
    P = {s: [x / sum(v) for x in v] for s, v in P.items()}
    delta = min(x for v in P.values() for x in v if x > 0) / 2
    par = {r["parameter"]: r["value"] for r in tsv(cart / "parametri.tsv")}
    assert float(par["zero_replacement"]) == pytest.approx(delta, rel=1e-3)

    def clr(v):
        k = sum(1 for x in v if x == 0)
        x = [delta if y == 0 else y * (1 - k * delta) for y in v]
        lg = [math.log(y) for y in x]
        return [y - sum(lg) / len(lg) for y in lg]
    C = {s: clr(v) for s, v in P.items()}
    ait = lambda a, b: math.dist(C[a], C[b])  # noqa: E731
    bray = lambda a, b: sum(abs(x - y) for x, y in zip(P[a], P[b])) / sum(x + y for x, y in zip(P[a], P[b]))  # noqa: E731
    for nome, fun in (("aitchison", ait), ("braycurtis", bray)):
        dr = {r["sample"]: r for r in tsv(cart / f"distance_{nome}.tsv")}
        for a in campioni:
            for b in campioni:
                assert float(dr[a][b]) == pytest.approx(fun(a, b), rel=1e-6, abs=1e-9)
        # PERMANOVA (Anderson 2001): SS totale e interna dalle distanze al quadrato
        gruppi = {s: s[0] for s in campioni}
        N = len(campioni)
        sst = sum(fun(a, b) ** 2 for i, a in enumerate(campioni) for b in campioni[i + 1:]) / N
        ssw = 0.0
        for g in set(gruppi.values()):
            m = [s for s in campioni if gruppi[s] == g]
            ssw += sum(fun(a, b) ** 2 for i, a in enumerate(m) for b in m[i + 1:]) / len(m)
        F = ((sst - ssw) / 1) / (ssw / (N - 2))
        pa = beta(cart, nome, "PERMANOVA")
        assert float(pa["F"]) == pytest.approx(F, rel=1e-3) and float(pa["R2"]) == pytest.approx((sst - ssw) / sst, abs=1e-3)


@con_r
def test_alfa_uguale_a_scipy(tmp_path):
    stats = pytest.importorskip("scipy.stats")
    risultati, d = due_gruppi_diversi(tmp_path)
    mc.esegui(risultati, d)
    cart = risultati / "multicampione" / "metaphlan"
    alfa = {r["sample"]: float(r["shannon"]) for r in tsv(cart / "alpha_diversity.tsv")}
    a = [v for s, v in sorted(alfa.items()) if s[0] == "A"]
    b = [v for s, v in sorted(alfa.items()) if s[0] == "B"]
    mw = [r for r in tsv(cart / "alpha_tests.tsv") if r["metric"] == "shannon"][0]
    assert float(mw["p"]) == pytest.approx(stats.mannwhitneyu(a, b, method="exact").pvalue, rel=1e-3)


@con_r
def test_stessa_media_dispersione_diversa_permdisp_lo_dice(tmp_path):
    rnd = random.Random(5)
    base = [10] * 10
    camp = {f"A{i}": composizione(base, rnd, 0.05) for i in range(8)} | \
           {f"B{i}": composizione(base, rnd, 1.2) for i in range(8)}
    risultati, d = progetto(tmp_path, camp, [(s, s[0], "", "") for s in camp])
    mc.esegui(risultati, d)
    cart = risultati / "multicampione" / "metaphlan"
    for dist in ("aitchison", "braycurtis"):
        assert float(beta(cart, dist, "PERMDISP")["p"]) < 0.05
        assert beta(cart, dist, "PERMANOVA")["dispersion_differs"] == "yes"


@con_r
def test_misure_ripetute_permutazioni_ristrette(tmp_path):
    """6 soggetti molto diversi fra loro, misurati a t0 e t1; a t1 Taxon_0 cresce sempre di 4 volte. Con le
    permutazioni ristrette dentro il soggetto (2^6 = 64 possibili) l'effetto del tempo si vede; con permutazioni
    libere la differenza fra soggetti lo copre."""
    rnd = random.Random(3)
    camp, meta = {}, []
    for s in range(6):
        base = [math.exp(rnd.gauss(0, 1.5)) for _ in TAXA]
        dopo = [base[0] * 4] + base[1:]
        for t, b in (("t0", base), ("t1", dopo)):
            camp[f"s{s}_{t}"] = composizione(b, rnd, 0.05)
            meta.append((f"s{s}_{t}", "", f"s{s}", t))
    risultati, d = progetto(tmp_path, camp, meta)
    rie = mc.esegui(risultati, d)
    c = rie["profiler"]["metaphlan"]["confronti"][0]
    assert (c["fattore"], c["disegno"], c["test_alfa"], c["permutazioni"]) == ("timepoint", "paired",
                                                                                "wilcoxon_paired", "blocks")
    cart = risultati / "multicampione" / "metaphlan"
    ristretta = beta(cart, "aitchison", "PERMANOVA", "timepoint")
    assert ristretta["restriction"] == "blocks" and ristretta["permutations"] == "63"
    assert float(ristretta["p"]) <= 0.05
    assert [r["n"] for r in tsv(cart / "alpha_tests.tsv")] == ["6"] * 3
    # stessa analisi con permutazioni libere (solo per il confronto): p più alto
    righe = (cart / "comparisons.tsv").read_text(encoding="utf-8").replace("\tblocks", "\tfree")
    (cart / "comparisons.tsv").write_text(righe, encoding="utf-8")
    subprocess.run([R, str(ROOT / "motore" / "multicampione.R"), "--dir", str(cart)], check=True, capture_output=True)
    libera = beta(cart, "aitchison", "PERMANOVA", "timepoint")
    assert libera["permutations"] == "999" and float(libera["p"]) > float(ristretta["p"])


@con_r
def test_friedman_e_soggetti_annidati(tmp_path):
    rnd = random.Random(8)
    camp, meta = {}, []
    for s in range(4):
        base = [math.exp(rnd.gauss(0, 1)) for _ in TAXA]
        for k, t in enumerate(("t0", "t1", "t2")):
            camp[f"s{s}_{t}"] = composizione([base[0] * (1 + 2 * k)] + base[1:], rnd, 0.1)
            meta.append((f"s{s}_{t}", "AB"[s % 2], f"s{s}", t))
    risultati, d = progetto(tmp_path, camp, meta)
    rie = mc.esegui(risultati, d)
    cart = risultati / "multicampione" / "metaphlan"
    conf = {c["fattore"]: c for c in rie["profiler"]["metaphlan"]["confronti"]}
    assert conf["timepoint"]["test_alfa"] == "friedman"
    # group: 2 soggetti per gruppo, ognuno sempre nello stesso gruppo -> media del soggetto, ma meno di 3: niente test
    assert conf["group"]["disegno"] == "between_subjects" and conf["group"]["test_alfa"] == "none"
    fr = [r for r in tsv(cart / "alpha_tests.tsv") if r["comparison"] == "timepoint"]
    assert {r["test"] for r in fr} == {"friedman"} and {r["n"] for r in fr} == {"4"}
    per = {r["metric"]: r for r in fr}
    assert per["richness"]["p"] == "" and per["richness"]["note"].startswith("all values are equal")  # 10 taxa ovunque
    assert all(per[m]["effect_size_name"] == "kendall_w" and 0 <= float(per[m]["effect_size"]) <= 1
               for m in ("shannon", "simpson"))
    coppie = [r for r in tsv(cart / "alpha_posthoc.tsv") if r["comparison"] == "timepoint"]
    assert len(coppie) == 6 and {r["metric"] for r in coppie} == {"shannon", "simpson"}   # 3 coppie x 2 indici
    assert not [r for r in tsv(cart / "beta_tests.tsv") if r["comparison"] == "group"]


@con_r
def test_soggetti_annidati_nei_gruppi_unita_soggetto(tmp_path):
    """3 + 3 salami, 2 fette ciascuno: l'unità è il salame (6 unità, non 12 campioni), sia per l'alfa sia per la beta."""
    rnd = random.Random(9)
    camp, meta = {}, []
    for g, base in (("A", [40, 30, 15, 5, 4, 2, 1, 1, 1, 1]), ("B", [1, 1, 1, 2, 4, 5, 15, 30, 40, 1])):
        for s in range(3):
            for k in range(2):
                camp[f"{g}{s}_{k}"] = composizione(base, rnd, 0.3)
                meta.append((f"{g}{s}_{k}", g, f"{g}{s}", ""))
    risultati, d = progetto(tmp_path, camp, meta)
    rie = mc.esegui(risultati, d)
    assert rie["profiler"]["metaphlan"]["confronti"][0]["permutazioni"] == "subject_mean"
    cart = risultati / "multicampione" / "metaphlan"
    assert {r["n"] for r in tsv(cart / "alpha_tests.tsv")} == {"6"}
    pa = beta(cart, "aitchison", "PERMANOVA")
    assert pa["n"] == "6" and pa["restriction"] == "subject_mean" and pa["permutations"] == "719"   # 6! - 1
    assert float(pa["R2"]) > 0.5


@con_r
def test_un_campione_per_gruppo_niente_test(tmp_path):
    rnd = random.Random(1)
    camp = {s: composizione([10] * 10, rnd, 0.5) for s in ("A", "B", "C")}
    risultati, d = progetto(tmp_path, camp, [(s, s, "", "") for s in camp])
    rie = mc.esegui(risultati, d)
    cart = risultati / "multicampione" / "metaphlan"
    assert tsv(cart / "alpha_tests.tsv") == [] and tsv(cart / "beta_tests.tsv") == []
    assert "almeno 3" in rie["profiler"]["metaphlan"]["confronti"][0]["motivo"]
    assert (cart / "pcoa_aitchison_group.png").is_file() and (cart / "alpha_group.png").is_file()   # solo descrittive


@con_r
def test_senza_metadati_solo_descrittive_e_modello(tmp_path):
    rnd = random.Random(2)
    camp = {s: composizione([10] * 10, rnd, 0.5) for s in ("A", "B", "C")}
    risultati, d = progetto(tmp_path, camp)
    rie = mc.esegui(risultati, d)
    assert rie["metadati"]["creato_ora"] and not rie["metadati"]["usati"]
    assert (tmp_path / "metadati.tsv").is_file()
    cart = risultati / "multicampione" / "metaphlan"
    assert rie["profiler"]["metaphlan"]["confronti"] == [] and tsv(cart / "beta_tests.tsv") == []
    assert (cart / "pcoa_braycurtis.png").is_file() and (cart / "distance_aitchison.tsv").is_file()


def test_un_solo_campione_nulla(tmp_path):
    risultati, d = progetto(tmp_path, {"A": [("x", 100.0)]})
    assert mc.esegui(risultati, d) == {"attiva": False}
    assert not (risultati / "multicampione").exists() and not (tmp_path / "metadati.tsv").exists()


# ---------------- 30/10, VM B2-5a: p mai sotto il minimo del disegno; statistiche non definite ----------------
def p_minimo(dimensioni):
    """1 / numero di divisioni distinte dei campioni in gruppi di queste dimensioni (gruppi uguali scambiabili):
    con 3 + 3 campioni 720 / (3! 3! 2!) = 10 divisioni, quindi p >= 0,1."""
    n = math.factorial(sum(dimensioni))
    for k in dimensioni:
        n //= math.factorial(k)
    for k in set(dimensioni):
        n //= math.factorial(dimensioni.count(k))
    return 1 / n


def quasi_identici(tmp_path, stessi_dentro=False):
    """6 sottocampioni dello stesso campione (gruppi A e B da 3), come la prova VM B2-5."""
    rnd = random.Random(30)
    base = [50, 30, 10, 5, 3, 1, 0.5, 0.3, 0.1, 0.05]
    camp = {}
    for g in "AB":
        primo = composizione(base, rnd, 0.01)
        for i in range(3):
            camp[f"{g}{i}"] = primo if stessi_dentro else composizione(base, rnd, 0.01)
    return progetto(tmp_path, camp, [(s, s[0], "", "") for s in camp])


@con_r
def test_nessun_p_sotto_il_minimo_del_disegno(tmp_path):
    risultati, d = quasi_identici(tmp_path)
    mc.esegui(risultati, d)
    righe = tsv(risultati / "multicampione" / "metaphlan" / "beta_tests.tsv")
    assert {(r["distance"], r["test"]) for r in righe} == {(x, y) for x in ("aitchison", "braycurtis")
                                                           for y in ("PERMANOVA", "PERMDISP")}
    for r in righe:   # entrambe le distanze; il minimo vale per la PERMANOVA (PERMDISP di vegan permuta i residui)
        if r["test"] == "PERMANOVA":
            assert r["p"] and float(r["p"]) >= p_minimo([3, 3]) - 1e-9, r


@con_r
def test_campioni_identici_nel_gruppo_niente_p_e_parole_semplici(tmp_path):
    """Dentro ogni gruppo i 3 campioni sono identici: dispersioni nulle (rumore di arrotondamento, 1e-17), che prima
    davano PERMDISP p = 0,001. Ora nessun p, e il referto lo dice in parole."""
    risultati, d = quasi_identici(tmp_path, stessi_dentro=True)
    rie = mc.esegui(risultati, d)
    for r in tsv(risultati / "multicampione" / "metaphlan" / "beta_tests.tsv"):
        assert r["p"] == "" and r["F"] == "" and "not defined" in r["note"], r
    sys.path.insert(0, str(ROOT / "motore"))
    import referto
    html = "\n".join(referto.html_multicampione({"multicampione": rie, "soglia": 0.005}))
    assert "il test non è definito, nessun valore p" in html and "non definita" in html
    assert "dispersione è zero in ogni gruppo" in html


@con_r
def test_permdisp_f_uguale_a_vegan(tmp_path):
    """F di PERMDISP uguale a quello di vegan::permutest."""
    risultati, d = due_gruppi_diversi(tmp_path)
    mc.esegui(risultati, d)
    cart = risultati / "multicampione" / "metaphlan"
    prova = cart / "prova_vegan.R"
    prova.write_text(
        'suppressPackageStartupMessages(library(vegan))\n'
        f'd <- as.dist(as.matrix(read.delim("{(cart / "distance_aitchison.tsv").as_posix()}", row.names = 1, '
        'check.names = FALSE)))\n'
        'g <- factor(substr(labels(d), 1, 1))\n'
        'cat(permutest(betadisper(d, g), permutations = 9)$tab$F[1])\n', encoding="utf-8")
    vegan = subprocess.run([R, str(prova)], capture_output=True, text=True, check=True).stdout
    assert float(beta(cart, "aitchison", "PERMDISP")["F"]) == pytest.approx(float(vegan), rel=1e-3)


# ---------------- nel referto: MetaPhlAn e Kraken separati ----------------
def scrivi_metaphlan(f, specie):
    righe = ["#mpa_vJan25_CHOCOPhlAnSGB_202503", "#1000 reads processed", "#clade_name\tNCBI_tax_id\trelative_abundance"]
    righe += [f"k__Bacteria|s__{n.replace(' ', '_')}\t1\t{p}\t" for n, p in specie]
    f.write_text("\n".join(righe) + "\n", encoding="utf-8")


def scrivi_kraken(cartella, nome, letture):
    rep = [f"100.00\t{sum(letture.values())}\t0\tR\t1\troot", f"100.00\t{sum(letture.values())}\t0\tD\t2\t  Bacteria"]
    rep += [f"1.00\t{v}\t{v}\tS\t{1000 + i}\t    {n}" for i, (n, v) in enumerate(letture.items())]
    (cartella / f"{nome}.k2report").write_text("\n".join(rep) + "\n", encoding="utf-8")
    b = ["name\ttaxonomy_id\ttaxonomy_lvl\tkraken_assigned_reads\tadded_reads\tnew_est_reads\tfraction_total_reads"]
    b += [f"{n}\t{1000 + i}\tS\t{v}\t0\t{v}\t0.1" for i, (n, v) in enumerate(letture.items())]
    (cartella / f"{nome}.bracken").write_text("\n".join(b) + "\n", encoding="utf-8")


def progetto_referto(tmp_path, metadati=True):
    rnd = random.Random(4)
    p = tmp_path / "multi"
    r = p / "risultati"
    for sotto in ("metaphlan", "kraken", "tabelle"):
        (r / sotto).mkdir(parents=True)
    campioni = []
    for i in range(8):
        nome, base = f"S{i}", ([40, 30, 15, 5, 4, 2, 1, 1, 1, 1] if i < 4 else [1, 1, 1, 2, 4, 5, 15, 30, 40, 1])
        scrivi_metaphlan(r / "metaphlan" / f"{nome}_profile.txt", composizione(base, rnd, 0.3))
        scrivi_kraken(r / "kraken", nome, {f"Kraken taxon {j}": int(1000 * x / 100) + 10
                                           for j, (_, x) in enumerate(composizione(base[::-1], rnd, 0.3))})
        campioni.append({"nome": nome, "esito": "ok", "file": {"metaphlan": f"metaphlan/{nome}_profile.txt",
                                                              "kraken": f"kraken/{nome}.bracken"}})
    (r / "risultati.json").write_text(json.dumps({"motore": "prova", "corsa": "c1", "campioni": campioni,
                                                  "parametri": {"abundance_threshold_pct": "0.005"}}), encoding="utf-8")
    (p / "config.yaml").write_text("project_name: multi\n", encoding="utf-8")
    if metadati:
        (p / "metadati.tsv").write_text("sample_id\tgroup\n" + "".join(f"S{i}\t{'AB'[i >= 4]}\n" for i in range(8)),
                                        encoding="utf-8")
    return p


def fai_referto(p, lingua="it"):
    r = subprocess.run([sys.executable, str(ROOT / "motore" / "referto.py"), "--risultati", str(p / "risultati"),
                        "--progetto", str(p / "config.yaml")], capture_output=True, text=True, encoding="utf-8",
                       timeout=300, env={**os.environ, "PMN_LINGUA": lingua})
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@con_r
def test_referto_con_metadati_sezione_e_cartelle_separate(tmp_path):
    p = fai = progetto_referto(tmp_path)
    esito = fai_referto(fai)
    assert esito["problemi"] == []
    html = (p / "risultati" / "referto" / "referto.html").read_text(encoding="utf-8")
    sez = html.split("<h2>4. Diversità e confronto fra i campioni</h2>")[1].split("<h2>5.")[0]
    assert "Confronto fra i campioni (analisi multicampione)" in sez
    mpa, krk = sez.split("<h4>MetaPhlAn</h4>")[1].split("<h4>Kraken + Bracken</h4>")
    for parte in (mpa, krk):
        assert "Mann-Whitney" in parte and "R² " in parte and "PERMDISP, p" in parte and "999 permutazioni" in parte
        assert "Bray-Curtis" in parte and "dispersione" in parte
    assert "Prototipo, non per decisioni" in krk and "Prototipo" not in mpa
    assert "Limiti." in sez and not re.search(r"\bmicrob[oi]\b", sez, re.I) and "—" not in sez
    assert "Anderson MJ (2006)" in html                                            # fonti nel referto
    m = p / "risultati" / "multicampione"
    for profiler in ("metaphlan", "kraken"):
        taxa = [r["taxon"] for r in tsv(m / profiler / "abundance_relative.tsv")]
        assert all(t.startswith("Kraken") for t in taxa) == (profiler == "kraken")   # mai una matrice unica
        assert (m / profiler / "pcoa_aitchison_group.pdf").is_file()
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(p / "risultati" / "referto" / "referto.xlsx")
    assert "Multi_MetaPhlAn" in wb.sheetnames and "Multi_Kraken" in wb.sheetnames


@con_r
def test_referto_senza_metadati_e_in_inglese(tmp_path):
    p = progetto_referto(tmp_path, metadati=False)
    fai_referto(p)
    html = (p / "risultati" / "referto" / "referto.html").read_text(encoding="utf-8")
    assert "Nessun test, solo descrizione" in html and "è stato creato adesso" in html
    assert "Salva e aggiorna l'analisi" in html                                  # R18: si fa dall'app
    assert (p / "metadati.tsv").read_text(encoding="utf-8").startswith("sample_id\tgroup\tsubject\ttimepoint\tcovariate\n")
    fai_referto(p, "en")
    html = (p / "risultati" / "referto" / "referto.html").read_text(encoding="utf-8")
    assert "Diversity and comparison between samples" in html and "No test, description only" in html
