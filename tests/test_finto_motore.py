# -*- coding: utf-8 -*-
"""The fake engine speaks the engine-GUI contract (docs/contratto_motore.md section 4), for every
command and scenario, so the GUI built against it (S4-S6) works with the real engine."""
import json
import os
import subprocess
import sys

import pytest

from contratto import controlla

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FINTO = os.path.join(ROOT, "installer", "finto_motore.py")
DATI = os.path.join(ROOT, "installer", "finto")


def lancia(*arg, velocita="0"):
    r = subprocess.run([sys.executable, FINTO, *arg, "--velocita", velocita],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    return r.stdout, r.returncode


@pytest.fixture
def progetto(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("project_name: prova\n", encoding="utf-8")
    return p


CASI = [("info", "ok", 0), ("installa", "ok", 0), ("installa", "annullata", 3), ("verifica", "ok", 0),
        ("verifica", "DB_MANCANTE", 2), ("stima", "ok", 0), ("stima", "TEMPO_LUNGO", 0), ("esegui", "ok", 0),
        ("esegui", "DB_MANCANTE", 2), ("esegui", "GIA_IN_CORSO", 1), ("esegui", "annullata", 3),
        ("esegui", "READ_NON_TROVATE", 1), ("esegui", "TEMPO_LUNGO", 0)]


@pytest.mark.parametrize("comando,scenario,uscita", CASI)
def test_every_command_and_scenario_follows_the_contract(comando, scenario, uscita, progetto):
    out, rc = lancia(comando, "--progetto", str(progetto), "--scenario", scenario)
    assert rc == uscita
    controlla(out, rc, comando)


def test_error_says_which_step_stopped(progetto):     # v0.2, request 1 of S4
    out, rc = lancia("esegui", "--progetto", str(progetto), "--scenario", "DB_MANCANTE")
    ev = controlla(out, rc, "esegui")
    assert ev[-2]["passo"] == "kraken" and "pagina Motore" in ev[-2]["cosa_fare"]
    out, rc = lancia("esegui", "--progetto", str(progetto), "--scenario", "READ_NON_TROVATE")
    assert controlla(out, rc, "esegui")[-2]["passo"] == "download"


def test_missing_project_is_config_non_valida():
    out, rc = lancia("esegui", "--progetto", "non_esiste.yaml")
    ev = controlla(out, rc, "esegui")
    assert rc == 1 and ev[-2]["codice"] == "CONFIG_NON_VALIDA"


def test_tempo_lungo_warns_before_the_end(progetto):
    out, rc = lancia("stima", "--progetto", str(progetto), "--scenario", "TEMPO_LUNGO")
    ev = controlla(out, rc, "stima")
    assert any(e["tipo"] == "avviso" and e["codice"] == "TEMPO_LUNGO" for e in ev)
    assert sum(ev[-1]["risultato"]["tempo_s"].values()) > 4 * 3600


def test_esegui_writes_the_results_of_a_real_run(progetto):
    out, rc = lancia("esegui", "--progetto", str(progetto))
    ev = controlla(out, rc, "esegui")
    r = progetto.parent / "risultati"
    indice = json.loads((r / "risultati.json").read_text(encoding="utf-8"))
    assert ev[-1]["risultato"]["campioni"] == indice["campioni"]
    for c in indice["campioni"]:
        for f in c["file"].values():
            assert (r / f).is_file()
    # the profile is the one of the real SF3RAt7 (SRR4875279) run, unchanged
    assert (r / "metaphlan" / "SRR4875279_profile.txt").read_bytes() == \
        open(os.path.join(DATI, "SRR4875279_profile.txt"), "rb").read()
    passi = [e["passo"] for e in ev if e["tipo"] == "avanzamento"]
    assert passi[0] == "download" and passi[-2:] == ["riepilogo", "referto"]   # P15: referto ultimo, come il vero
    pct = [e["percentuale"] for e in ev if e["tipo"] == "avanzamento"]
    assert pct == sorted(pct)


def test_annulla_stops_a_running_esegui(progetto):
    corsa = subprocess.Popen([sys.executable, FINTO, "esegui", "--progetto", str(progetto), "--velocita", "200"],
                             stdout=subprocess.PIPE, text=True, encoding="utf-8")
    inizio = json.loads(corsa.stdout.readline())
    corsa.stdout.readline()                                   # first avanzamento: it is running
    out2, rc2 = lancia("esegui", "--progetto", str(progetto))  # one esegui at a time
    assert rc2 == 1 and json.loads(out2.splitlines()[-2])["codice"] == "GIA_IN_CORSO"
    out, rc = lancia("annulla", "--corsa", inizio["corsa"])
    assert rc == 0 and json.loads(out.splitlines()[-1])["risultato"] == {"annullata": True}
    resto, _ = corsa.communicate(timeout=30)
    assert corsa.returncode == 3
    assert json.loads(resto.splitlines()[-1])["esito"] == "annullata"
    out, rc = lancia("annulla", "--corsa", inizio["corsa"])    # nothing left to stop
    assert json.loads(out.splitlines()[-1])["risultato"] == {"annullata": False}
