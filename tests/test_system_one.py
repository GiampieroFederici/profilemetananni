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
