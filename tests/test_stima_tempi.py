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


def totale(camp=SF3RAT7, cfg=CFG, quote=None):
    return sum(pm.tempi(camp, cfg, quote).values())


def test_sf3rat7_entro_il_25_per_cento_del_vero():
    assert abs(totale() - VERO_S) <= 0.25 * VERO_S
    t = pm.tempi(SF3RAT7, CFG)
    assert set(t) == {"download", "controllo_qualita", "pulizia", "ospite", "metaphlan", "kraken", "riepilogo", "referto"}
    assert abs(t["kraken"] - 1419) <= 0.25 * 1419          # Kraken + Bracken veri: 08:00:18 -> 08:23:57
    assert abs(t["metaphlan"] - 357) <= 0.25 * 357         # 07:54:21 -> 08:00:18
    assert abs(t["download"] - 129) <= 0.25 * 129 and t["pulizia"] < 60


def test_kraken_conta_le_coppie_dopo_l_ospite():
    con = pm.tempi(SF3RAT7, CFG)["kraken"]
    senza = pm.tempi(SF3RAT7, {**CFG, "hosts": []})["kraken"]       # solo uomo: prudente, tutte le coppie
    assert abs(senza * (1 - pm.OSPITE_QUOTA) - con) <= 1
    # dal triage (host_pct per campione), se c'e': 80 % di ospite -> 20 % delle coppie
    assert abs(pm.tempi(SF3RAT7, CFG, {"SRR4875279": 0.8})["kraken"] - senza * 0.2) <= 1


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
