# -*- coding: utf-8 -*-
"""System One v0 (D031): rules that advise and do not compute. Criteria S1-S3 of
sessioni/2026-10-16_motore_seconda_parte.md: each rule at its boundary, each advice with its source."""
import json
import os
import subprocess
import sys

import pytest

from contratto import CODICI, controlla

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "motore"))
import system_one as so  # noqa: E402

FINTO = os.path.join(ROOT, "installer", "finto_motore.py")


def codici(consigli):
    return [c["codice"] for c in consigli if c["livello"] == "avviso"]


def test_s2_ram_e_modo_metaphlan():
    assert so.modo(39.9, True, True, True)[0]["metaphlan"] == "fette"
    assert so.modo(40.0, True, True, True)[0]["metaphlan"] == "standard"
    assert so.modo(64.0, False, True, True)[0]["metaphlan"] == "fette"     # senza indice intero niente standard
    assert codici(so.modo(7.4, False, True, True)[1]) == ["RAM_INSUFFICIENTE"]
    assert codici(so.modo(7.5, False, True, True)[1]) == []
    assert codici(so.modo(0.0, False, True, True)[1]) == []                 # RAM sconosciuta: niente avviso


def test_s2_database_kraken():
    assert so.modo(15.6, False, True, True)[0]["kraken"] == "completo"
    modo, c = so.modo(15.6, False, False, True)
    assert modo["kraken"] == "rapido" and codici(c) == ["DB_MANCANTE"]
    assert codici(so.modo(15.6, False, False, False)[1]) == ["DB_MANCANTE"]
    assert codici(so.database("completo", {"kraken_pluspf_20260626": False})) == ["DB_MANCANTE"]
    assert so.database("rapido", {"kraken_pluspf_08gb_20260626": True}) == []


def test_s2_tempo_e_spazio():
    assert so.tempo({"ospite": 3600, "kraken": 3 * 3600}) == []
    assert codici(so.tempo({"ospite": 3600, "kraken": 3 * 3600 + 1})) == ["TEMPO_LUNGO"]
    assert so.spazio(10, 11.5) == []                        # 10 x 1,15 = 11,5: basta
    assert codici(so.spazio(10, 11.4)) == ["SPAZIO_INSUFFICIENTE"]
    assert so.spazio(10, None) == []


def test_s2_triage(tmp_path):
    t = tmp_path / "triage.tsv"
    t.write_text("sample\ttotal_fragments\ttested_fragments\tpass_rate_pct\tq30_pct\tdup_pct\thost_pct\t"
                 "est_nonhost_fragments\tscore\tdecision\treasons\n"
                 "A\t3000000\t100000\t99\t92\t5\t50\t1500000\t1.0\tpass\t\n"
                 "B\t3000000\t100000\t99\t92\t5\t60\t950000\t0.45\treview\tx\n"
                 "C\t3000000\t100000\t99\t60\t5\t99\t30000\t0.0\texclude\tx\n", encoding="utf-8")
    esiti, consigli = so.triage(t)
    assert [e["esito"] for e in esiti] == ["buono", "da controllare", "da rifare"]
    assert esiti[0]["motivi"] == [] and len(esiti[1]["motivi"]) == 1 and len(esiti[2]["motivi"]) == 3
    assert codici(consigli) == ["CAMPIONE_DA_CONTROLLARE", "CAMPIONE_DA_RIFARE"]
    assert so.triage(tmp_path / "manca.tsv") == ([], [])
    # R1 (18/10): la virgola fra i due numeri resta una virgola ("circa 950.000, minimo"), non "950.000. minimo"
    assert esiti[1]["motivi"] == ["poche read senza l'ospite (circa 950.000, minimo 1.000.000)"]


def test_s1_ogni_consiglio_ha_fonte_e_codice_del_contratto(tmp_path):
    tutti = (so.modo(7.0, False, False, True)[1] + so.tempo({"k": 99999}) + so.spazio(100, 1)
             + so.database("completo", {}))
    for c in tutti:
        assert c["fonte"] and c["messaggio"]
        assert c["livello"] == "info" or c["codice"] in CODICI


# ---------------- ambienti nuovi (v1.1, R9): voci dopo i 4 prodotti di carne ----------------
SALUMI = [  # info.prodotti di v1.0 (italiano): devono restare identici voce per voce
    {"prodotto": "maiale", "ospiti": ["sus_scrofa"], "genomi": ["Sscrofa11.1"],
     "frase": "Toglierò il DNA del maiale e quello umano.",
     "perche": "Sono la gran parte delle read di un salume e non dicono nulla dei taxa del prodotto. "
               "Il DNA umano si toglie sempre.", "livello": "info", "fonte": so.FONTE_OSPITE},
    {"prodotto": "bovino", "ospiti": ["bos_taurus"], "genomi": ["ARS-UCD1.2"],
     "frase": "Toglierò il DNA del bovino e quello umano.", "perche": so._CARNE, "livello": "info",
     "fonte": so.FONTE_OSPITE},
    {"prodotto": "pecora", "ospiti": ["ovis_aries"], "genomi": ["ARS-UI_Ramb_v2.0"],
     "frase": "Toglierò il DNA della pecora e quello umano.", "perche": so._CARNE, "livello": "info",
     "fonte": so.FONTE_OSPITE},
    {"prodotto": "altro", "ospiti": [], "genomi": [], "frase": "Toglierò solo il DNA umano.",
     "perche": "Se il prodotto contiene carne di maiale, bovino o pecora, sceglila qui sopra: senza, molte read della "
               "carne finiscono assegnate per errore a qualche taxon.", "livello": "avviso", "fonte": so.FONTE_OSPITE},
]


def test_ambienti_salumi_invariati():
    assert so.prodotti()[:4] == SALUMI


def test_ambienti_voci_e_ospiti():
    p = {x["prodotto"]: x for x in so.prodotti()[4:]}
    assert list(p) == ["feci_umane", "cute", "suolo", "vite_mosto", "vite_acino", "vite_foglia", "vite_radice"]
    assert p["feci_umane"]["ospiti"] == p["cute"]["ospiti"] == ["grch38"]           # l'uomo è l'ospite
    assert p["suolo"]["ospiti"] == []                                               # solo l'uomo (filter_human)
    assert all(p[k]["ospiti"] == ["vitis_vinifera"] for k in p if k.startswith("vite_"))
    assert p["vite_mosto"]["genomi"] == ["T2T-PN40024 (ASM3070453v1)"] and p["cute"]["genomi"] == ["GRCh38.p14"]
    for x in p.values():
        assert x["testo"] and x["frase"] and x["perche"] and x["fonte"]
        assert x["livello"] in ("info", "avviso") and isinstance(x["sperimentale"], bool)
        assert "—" not in x["perche"] + x["frase"] + x["testo"]                  # niente trattini lunghi
    assert p["vite_acino"]["sperimentale"] and p["vite_foglia"]["sperimentale"]     # nessuna prova con dati veri


def test_ambienti_ospiti_noti_al_motore():
    # nomi di refs/hosts.tsv; vitis_vinifera arriva con l'incarico OSPITE (D167): qui basta che sia un nome valido
    with open(os.path.join(ROOT, "refs", "hosts.tsv"), encoding="utf-8") as f:
        noti = {r.split("\t")[0] for r in f if r.strip() and not r.startswith("#")} | {"vitis_vinifera"}
    assert {o for x in so.prodotti() for o in x["ospiti"]} <= noti


def test_ambienti_testi_in_inglese():
    with open(os.path.join(ROOT, "motore", "lingua_en.json"), encoding="utf-8") as f:
        en = json.load(f)
    testi = {so.FONTE_AMBIENTI} | {t for _p, testo, _o, frase, perche, *_r in so.AMBIENTI for t in (testo, frase, perche)}
    assert not [t for t in testi if t not in en]


def lancia(*arg):
    r = subprocess.run([sys.executable, FINTO, *arg, "--velocita", "0"], capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    return controlla(r.stdout, r.returncode, arg[0]), r.returncode


@pytest.fixture
def progetto(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("project_name: prova\n", encoding="utf-8")
    return p


def test_s3_finto_info_stima_esegui(progetto):
    ev, _ = lancia("info")
    assert ev[-1]["risultato"]["modo_consigliato"]["metaphlan"] == "fette" and ev[-1]["risultato"]["consigli"]
    ev, _ = lancia("stima", "--progetto", str(progetto), "--scenario", "TEMPO_LUNGO")
    assert [c["codice"] for c in ev[-1]["risultato"]["consigli"]] == ["TEMPO_LUNGO"]
    ev, rc = lancia("esegui", "--progetto", str(progetto), "--scenario", "CAMPIONE_DA_CONTROLLARE")
    assert rc == 0 and [e["codice"] for e in ev if e["tipo"] == "avviso"] == ["CAMPIONE_DA_CONTROLLARE"]
    r = json.loads((progetto.parent / "risultati" / "risultati.json").read_text(encoding="utf-8"))
    assert r["triage"][0]["esito"] == "da controllare"
