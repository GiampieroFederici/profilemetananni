# -*- coding: utf-8 -*-
"""Command "sicurezza" (contract v0.2): FSSP predictions inside pmn-motore and the fake engine.
Criteria F1-F5 of sessioni/2026-10-16_motore_seconda_parte.md."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from contratto import controlla

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MOTORE = os.path.join(ROOT, "motore", "pmn_motore.py")
FINTO = os.path.join(ROOT, "installer", "finto_motore.py")
STEP45 = os.path.join(ROOT, "steps", "45_previsione_fssp.py")
DATI = os.path.join(ROOT, "installer", "finto")
ENGINES = {"vero": [sys.executable, MOTORE], "finto": [sys.executable, FINTO, "--velocita", "0"]}

COTTO = {"prodotto": {"sale_fase_acquosa": 3.0, "ph": 6.2, "nitrito": 60, "acidi": {"lattico": 7000}},
         "profilo_temperatura": [[5, 240], [10, 120]]}


def lancia(motore, tmp_path, richiesta, *extra, grezza=None):
    f = tmp_path / "richiesta.json"
    f.write_text(grezza if grezza is not None else json.dumps(richiesta), encoding="utf-8")
    env = {**os.environ, "PMN_HOME": str(tmp_path / "pmn_vuota")}
    r = subprocess.run([*ENGINES[motore], "sicurezza", "--ingresso", str(f), *extra], capture_output=True,
                       text=True, encoding="utf-8", timeout=120, env=env)
    return controlla(r.stdout, r.returncode, "sicurezza"), r.returncode


def step45(tmp_path, richiesta):
    f, u = tmp_path / "r45.json", tmp_path / "u45.json"
    f.write_text(json.dumps(richiesta), encoding="utf-8")
    subprocess.run([sys.executable, STEP45, "--ingresso", str(f), "--uscita", str(u)], check=True,
                   capture_output=True, timeout=120)
    return json.loads(u.read_text(encoding="utf-8"))


@pytest.fixture
def progetto(tmp_path):
    """A project folder whose risultati/ holds the real SF3RAt7 run (profile of the fake engine data)."""
    p = tmp_path / "progetto"
    (p / "risultati" / "metaphlan").mkdir(parents=True)
    shutil.copy(os.path.join(DATI, "SRR4875279_profile.txt"), p / "risultati" / "metaphlan")
    shutil.copy(os.path.join(DATI, "risultati.json"), p / "risultati")
    (p / "config.yaml").write_text("project_name: prova\n", encoding="utf-8")
    return p / "config.yaml"


@pytest.mark.parametrize("motore", ENGINES)
@pytest.mark.parametrize("modalita", [None, "migliorata", "fssp"])
def test_f1_stesse_previsioni_di_step45(motore, modalita, tmp_path):
    richiesta = dict(COTTO, **({"modalita": modalita} if modalita else {}))
    ev, rc = lancia(motore, tmp_path, richiesta)
    assert rc == 0 and ev[-1]["esito"] == "ok"
    atteso = step45(tmp_path, richiesta)
    r = ev[-1]["risultato"]
    assert r["modalita"] == (modalita or "migliorata")
    assert r["previsioni"] == atteso["previsioni"]
    assert [p["n0_listeria_ufc_g"] for p in r["previsioni"]] == [1.0, 100.0]   # D019: sempre 1 e 100
    assert {e["passo"] for e in ev if e["tipo"] == "avanzamento"} == {"sicurezza"}


@pytest.mark.parametrize("motore", ENGINES)
def test_f2_fuori_campo_un_avviso_per_fattore(motore, tmp_path):
    dentro, _ = lancia(motore, tmp_path, COTTO)
    assert not [e for e in dentro if e["tipo"] == "avviso"]
    fuori = dict(COTTO, prodotto=dict(COTTO["prodotto"], ph=5.2, nitrito=200))
    ev, rc = lancia(motore, tmp_path, fuori)
    avvisi = [e for e in ev if e["tipo"] == "avviso"]
    assert rc == 0 and {e["codice"] for e in avvisi} == {"FUORI_CAMPO"}
    assert len(avvisi) == len(ev[-1]["risultato"]["avvisi"]) == 2          # pH e nitrito
    assert all(e["messaggio"].startswith("Per il modello della Listeria") for e in avvisi)
    assert {(e["modello"], e["fattore"]) for e in avvisi} == {("listeria", "ph"), ("listeria", "nitrito")}


@pytest.mark.parametrize("motore", ENGINES)
@pytest.mark.parametrize("grezza,richiesta", [(None, dict(COTTO, prodotto={"ph": 15})),
                                              (None, dict(COTTO, prodotto={"colore": "rosso"})),
                                              ("{non e' json", None),
                                              (None, dict(COTTO, campione="../../fuori"))])
def test_f3_ingresso_non_valido(motore, grezza, richiesta, tmp_path):
    ev, rc = lancia(motore, tmp_path, richiesta, grezza=grezza)
    assert rc == 1 and ev[-2]["codice"] == "INGRESSO_NON_VALIDO" and ev[-1]["esito"] == "errore"


@pytest.mark.parametrize("motore", ENGINES)
def test_f4_ponte_dal_profilo_vero_di_SF3RAt7(motore, tmp_path, progetto):
    ev, rc = lancia(motore, tmp_path, COTTO, "--progetto", str(progetto))
    assert rc == 0
    r = ev[-1]["risultato"]
    assert r["campione"] == "SRR4875279" and r["profilo_usato"].startswith("MetaPhlAn, campione SRR4875279")
    assert "53,7 %" in r["profilo_usato"]                             # UNCLASSIFIED del profilo
    assert r["ponte"]["lab_trovati"] == ["latilactobacillus curvatus", "latilactobacillus sakei"]
    assert any("Leuconostoc" in n for n in r["note"])                # postilla: modello non adatto
    assert {p["modello"] for p in r["previsioni"]} == {"listeria"}   # senza conte: caso peggiore
    salvato = progetto.parent / "risultati" / "sicurezza" / "SRR4875279.json"
    assert json.loads(salvato.read_text(encoding="utf-8"))["previsioni"] == r["previsioni"]
    ev, rc = lancia(motore, tmp_path, dict(COTTO, conte={"lab_ufc_g": 1e4}), "--progetto", str(progetto))
    assert rc == 0 and {p["modello"] for p in ev[-1]["risultato"]["previsioni"]} == {"listeria_lab"}


def test_f5_finto_e_vero_danno_gli_stessi_numeri(tmp_path, progetto):
    a, _ = lancia("vero", tmp_path, COTTO, "--progetto", str(progetto))
    b, _ = lancia("finto", tmp_path, COTTO, "--progetto", str(progetto))
    assert a[-1]["risultato"]["previsioni"] == b[-1]["risultato"]["previsioni"]
    assert [e["tipo"] for e in a] == [e["tipo"] for e in b]
