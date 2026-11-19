# -*- coding: utf-8 -*-
"""tempi() e piano() del motore (contratto 5.2) contro la corsa vera del 17/10 (L1a a riga di comando):
SF3RAt7, NVMe, 24 processori, 37 min 39 s dall'inizio al referto; Kraken 1.415 s su 1.507.887 coppie senza ospite."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "motore"))
import pmn_motore as pm  # noqa: E402

SF3RAT7 = [("SRR4875279", 3_240_847, 533_522_098)]
CFG = {"hosts": ["sus_scrofa"], "profiling": {"tool": "both"}, "motore": {"kraken_db": "completo", "processori": 24},
       "execution": {"threads": 24}}
VERO_S = 37 * 60 + 39
# 1.2: la corsa del 17/10 aveva il filtro end-to-end, che lasciava 1.507.887 coppie su 3.240.847 (53 % tolte); la quota
# di partenza ora è quella della regola strict (OSPITE_QUOTA 0,67), quindi il confronto usa la quota misurata allora
Q_17_10 = {"SRR4875279": 1 - 1_507_887 / 3_240_847}


def totale(camp=SF3RAT7, cfg=CFG, quote=None):
    return sum(pm.tempi(camp, cfg, quote).values())


def test_sf3rat7_entro_il_25_per_cento_del_vero():
    assert abs(totale(quote=Q_17_10) - VERO_S) <= 0.25 * VERO_S
    t = pm.tempi(SF3RAT7, CFG, Q_17_10)
    assert set(t) == {"download", "controllo_qualita", "pulizia", "ospite", "metaphlan", "kraken", "riepilogo", "referto"}
    assert abs(t["kraken"] - 1419) <= 0.25 * 1419          # Kraken + Bracken veri: 08:00:18 -> 08:23:57
    # 07:54:21 -> 08:00:18 col .pkl intero, meno i 50 s del profilo col database ridotto (F3, N1: 53 -> 3 s, 5/11)
    assert abs(t["metaphlan"] - (357 - 50)) <= 0.25 * (357 - 50)
    assert abs(t["download"] - 129) <= 0.25 * 129 and t["pulizia"] < 60


def test_kraken_conta_le_coppie_dopo_l_ospite():
    con = pm.tempi(SF3RAT7, CFG)["kraken"]
    senza = pm.tempi(SF3RAT7, {**CFG, "hosts": []})["kraken"]       # solo uomo: prudente, tutte le coppie
    f = pm.KRAKEN_FISSI_S["completo"]                               # 1.2: caricamento del database, fisso
    assert abs((senza - f) * (1 - pm.OSPITE_QUOTA) - (con - f)) <= 1
    # dal triage (host_pct per campione), se c'e': 80 % di ospite -> 20 % delle coppie
    assert abs(pm.tempi(SF3RAT7, CFG, {"SRR4875279": 0.8})["kraken"] - f - (senza - f) * 0.2) <= 1


def test_processori_dalla_corsa():
    assert pm.processori(CFG) == 24
    assert pm.processori({"motore": {"processori": 16}}) == 16      # senza execution.threads
    assert pm.processori({"execution": {"threads": "x"}}) == pm.KRAKEN_PROC_RIF
    otto = {**CFG, "execution": {"threads": 8}, "motore": {"kraken_db": "completo"}}
    assert pm.tempi(SF3RAT7, otto)["kraken"] > pm.tempi(SF3RAT7, CFG)["kraken"]
    # v1.1 (VELOCITA, 30/10, 8 processori, 8 GB): Kraken + Bracken 24 min 20 s a PC poco carico, 33 min a PC carico
    # (prima della v1.1, K2: 40 min 47 s); la stima resta prudente: fra il piu' veloce e il piu' lento + 10 %
    assert 1460 <= pm.tempi(SF3RAT7, otto)["kraken"] <= 1.1 * 1980


def test_read_locali_solo_metaphlan_e_rapido():
    locali = [("C1", 3_240_847, 0)]                                   # niente da scaricare
    assert pm.tempi(locali, CFG)["download"] == 0
    assert pm.tempi(SF3RAT7, {**CFG, "profiling": {"tool": "metaphlan"}})["kraken"] == 0
    assert pm.tempi(SF3RAT7, {**CFG, "motore": {"kraken_db": "rapido"}})["kraken"] < 60
    assert totale(SF3RAT7 * 3) > 2.5 * totale() - 60                  # 3 campioni: quasi il triplo


def test_piano_nell_ordine_di_run_sh():
    due = [("A", 1_000_000, 1), ("B", 2_000_000, 1)]
    etichette = [e for e, _, _, _ in pm.piano(due, {**CFG, "triage": {"enabled": True}})]
    assert etichette == ["size", "dl_A", "dl_B", "tq_A", "th_A", "tq_B", "th_B", "triage", "trim_A", "hf_A", "trim_B",
                         "hf_B", "multiqc", "mpa_A", "krk_A", "mpa_B", "krk_B", "riepilogo", "alfa_mpa_B", "referto"]
    gruppi = [g for _, _, g, _ in pm.piano(due, CFG)]
    assert gruppi == sorted(gruppi)


def test_gia_fatti_dalle_uscite_sul_disco(tmp_path):
    for f in ("nonhost/A_nonhost_1.fastq.gz", "metaphlan/A_profile.txt", "kraken/B.bracken", "raw/B_1.fastq.gz"):
        (tmp_path / f).parent.mkdir(exist_ok=True)
        (tmp_path / f).write_text("x", encoding="utf-8")
    (tmp_path / "kraken" / "A.bracken").write_text("", encoding="utf-8")   # vuoto: run.sh lo rifà
    etichette = [e for e, _, _, _ in pm.piano([("A", 1, 1), ("B", 1, 1)], CFG)]
    assert pm.gia_fatti(tmp_path, etichette) == {"trim_A", "hf_A", "mpa_A", "krk_B", "dl_B"}


def test_quote_dal_triage(tmp_path):
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "triage.tsv").write_text("sample\thost_pct\tscore\nA\t62.5\t0.9\nB\tNA\t0.1\n",
                                                     encoding="utf-8")
    assert pm.quote_triage(tmp_path) == {"A": 0.625}
    assert pm.quote_triage(tmp_path / "manca") == {}


def test_ospite_costa_secondo_la_quota():
    """18/11/2026, filtro in due fasi: a 8 processori una coppia tolta costa 70 microsecondi, una che resta 31
    (misure del 14/11 su SRR4875279). Prima: 155 s per milione a 24 processori, uguale per ogni quota."""
    otto = {"hosts": ["sus_scrofa"], "execution": {"threads": 8}}

    def ospite(coppie, cfg=otto, quote=None):
        return {e: sec for e, _passo, _gruppo, sec in pm.piano([("A", coppie, 0)], cfg, quote)}["hf_A"]

    assert abs(ospite(2_955_015, quote={"A": 1_970_140 / 2_955_015}) - 168.45) <= 0.5     # misurati 167,2 e 169,7 s
    assert abs(ospite(15_525_290, quote={"A": 0.99}) - 1081) <= 1          # 18 min; con la regola di prima 4.123 s
    # senza una quota misurata: 0,67
    assert abs(ospite(1_000_000) - (70 * pm.OSPITE_QUOTA + 31 * (1 - pm.OSPITE_QUOTA))) <= 1e-6
    # dove il filtro resta a un passaggio (solo l'uomo, very-sensitive) il metodo non cambia e la regola nemmeno:
    # 155 s per milione a 24 processori, con l'esponente di prima
    uno = 155 * (24 / 8) ** 0.49
    assert abs(ospite(1_000_000, {**otto, "hosts": []}) - uno) <= 1e-6
    assert abs(ospite(1_000_000, {**otto, "hosts": ["grch38"]}) - uno) <= 1e-6
    assert abs(ospite(1_000_000, {**otto, "host_sensitivity": "very-sensitive"}, {"A": 0.99}) - uno) <= 1e-6
    assert abs(ospite(1_000_000, {**otto, "hosts": [], "execution": {"threads": 24}}) - 155) <= 1e-6
    # processori (19/11): due esponenti misurati sulle due fasi, 0,73 sotto gli 8 processori e 0,42 sopra
    assert abs(ospite(1_000_000, {**otto, "execution": {"threads": 4}}) / ospite(1_000_000) - 2 ** 0.73) <= 1e-6
    assert abs(ospite(1_000_000, {**otto, "execution": {"threads": 24}}) / ospite(1_000_000) - 3 ** -0.42) <= 1e-6
    # contro le misure del 19/11 (SRR4875279, 66,7 % tolte): 4 processori 265,0 e 261,5 s, 24 processori 95,5 e 105,0 s
    misurata = {"A": 1_970_140 / 2_955_015}
    for processori, secondi in ((4, 263.25), (24, 100.25)):
        stimati = ospite(2_955_015, {**otto, "execution": {"threads": processori}}, misurata)
        assert abs(stimati - secondi) <= 0.10 * secondi, (processori, stimati)


def test_estremi_quando_la_quota_non_e_misurata():
    """19/11/2026: senza una quota di ospite misurata la stima dà due estremi, il totale alla quota di partenza (0,67)
    e quello al 99 %. Con più ospite il totale scende: MetaPhlAn e Kraken ricevono meno coppie."""
    otto = {"hosts": ["sus_scrofa"], "profiling": {"tool": "both"}, "motore": {"kraken_db": "completo"},
            "execution": {"threads": 8}}
    camp = [("A", 2_955_015, 0)]
    e = pm.estremi(camp, otto, {})
    assert e == {"tempo_minimo_s": totale(camp, otto, {"A": 0.99}), "tempo_massimo_s": totale(camp, otto)}
    assert (round(e["tempo_minimo_s"] / 60), round(e["tempo_massimo_s"] / 60)) == (7, 30)
    assert pm.estremi(camp, otto, {"A": 0.8}) == {}                 # quota misurata (triage, ospite già tolto)
    assert pm.estremi(camp, {**otto, "hosts": []}, {}) == {}        # solo l'uomo: la quota non conta
    # due campioni, uno misurato: per l'altro la quota di partenza (qui la media dei misurati) e il 99 %
    due = [("A", 1_000_000, 0), ("B", 1_000_000, 0)]
    assert pm.estremi(due, otto, {"A": 0.5}) == {"tempo_minimo_s": totale(due, otto, {"A": 0.5, "B": 0.99}),
                                                 "tempo_massimo_s": totale(due, otto, {"A": 0.5})}


def test_spazio_conta_le_coppie_della_fase_2():
    """19/11/2026: con il filtro in due fasi le coppie che passano la fase 1 aspettano la fase 2 non compresse
    (misurati 735 byte per coppia, 4,5 volte le read gz). La stima conta il caso peggiore, tutte le coppie, per un
    campione solo: la cartella temporanea si svuota a ogni campione. Dove il filtro resta a un passaggio: 6 volte."""
    maiale = {"hosts": ["sus_scrofa"]}
    assert pm.spazio_analisi(SF3RAT7, {"hosts": []}) == 3.2                     # 533,5 MB x 6, come prima
    assert pm.spazio_analisi(SF3RAT7, {"hosts": ["grch38"]}) == 3.2
    assert pm.spazio_analisi(SF3RAT7, {**maiale, "host_sensitivity": "very-sensitive"}) == 3.2
    assert pm.spazio_analisi(SF3RAT7, maiale) == 5.6                            # + 533,5 MB x 4,5 = 2,4 GB
    # due campioni (il secondo locale, 1 milione di coppie): 698,1 MB x 6 = 4,2 GB, più la fase 2 del più grande
    assert pm.spazio_analisi(SF3RAT7 + [("B", 1_000_000, 0)], maiale) == 6.6
