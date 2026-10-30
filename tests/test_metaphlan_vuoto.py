# -*- coding: utf-8 -*-
"""MetaPhlAn senza specie (PMN 1.1, VM B3-3, 30/10/2026).

Campione di 20.000 coppie casuali, tipo "Suolo": MetaPhlAn non trova specie (profilo con la sola riga UNCLASSIFIED),
steps/34_metaphlan_matrix.py si fermava con "no species-level rows" e l'analisi finiva al 96 % con "Il progetto
contiene un valore non valido". Ora un profilo senza specie e' valido: la matrice non ha quel campione (vuota se
tutti sono vuoti), il motore da' l'avviso METAPHLAN_VUOTO, il referto scrive una frase al posto della tabella.
Con almeno una specie in ogni campione la matrice resta identica al byte.
Dati (tests/dati): profilo vero delle read casuali (MetaPhlAn 4.2.4 a fette, vJan25), profili veri di cute
(SRR1620994) e feci (ERR478976) della prova AMBIENTI, tabelle unite con merge_metaphlan_tables.py, matrice attesa
fatta dal codice di partenza (397d46a) sulle due tabelle piene.
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_metaphlan_vuoto.py"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
DATI = RADICE / "tests" / "dati"
MATRICE = RADICE / "steps" / "34_metaphlan_matrix.py"
FRASE = "MetaPhlAn: nessuna specie trovata; il profilo di MetaPhlAn di questo campione è vuoto."


def matrice(tmp_path, tabella):
    out = tmp_path / "metaphlan_matrix.tsv"
    p = subprocess.run([sys.executable, str(MATRICE), "--in", str(DATI / tabella), "--out", str(out)],
                       capture_output=True, text=True)
    return p, out


def test_con_le_specie_matrice_identica_al_byte(tmp_path):
    p, out = matrice(tmp_path, "metaphlan_unite_piene.tsv")
    assert p.returncode == 0, p.stdout + p.stderr
    assert out.read_bytes() == (DATI / "metaphlan_matrice_piene_attesa.tsv").read_bytes()


def test_campione_senza_specie_fuori_dalla_matrice(tmp_path):
    """Prima: colonna CASUALE tutta a 0 (la beta e il passo 41 la prendevano come campione). Ora: stessa matrice
    delle sole tabelle piene, al byte, e un avviso."""
    p, out = matrice(tmp_path, "metaphlan_unite_con_vuoto.tsv")
    assert p.returncode == 0, p.stdout + p.stderr
    assert out.read_bytes() == (DATI / "metaphlan_matrice_piene_attesa.tsv").read_bytes()
    assert "CASUALE" in p.stderr and "no species" in p.stderr


def test_tutti_senza_specie_matrice_vuota_e_l_analisi_continua(tmp_path):
    p, out = matrice(tmp_path, "metaphlan_unite_solo_vuoto.tsv")
    assert p.returncode == 0, p.stdout + p.stderr                     # prima: codice 1, analisi ferma al 96 %
    assert out.read_text() == "species\n"
    assert "CASUALE" in p.stderr


def test_tabella_rotta_ferma_ancora(tmp_path):
    (tmp_path / "rotta.tsv").write_text("niente di MetaPhlAn\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(MATRICE), "--in", str(tmp_path / "rotta.tsv"), "--out",
                        str(tmp_path / "m.tsv")], capture_output=True, text=True)
    assert p.returncode != 0


def risultati(tmp_path, campioni):
    """Cartella risultati/ come la scrive pmn-motore, con i profili MetaPhlAn di tests/dati."""
    r = tmp_path / "risultati"
    (r / "metaphlan").mkdir(parents=True)
    (r / "tabelle").mkdir()
    (r / "tabelle" / "parameters.tsv").write_text("parameter\tvalue\nmetaphlan_mode\tfette\n", encoding="utf-8")
    elenco = []
    for nome, dato in campioni.items():
        shutil.copy(DATI / dato, r / "metaphlan" / f"{nome}_profile.txt")
        elenco.append({"nome": nome, "esito": "ok", "file": {"metaphlan": f"metaphlan/{nome}_profile.txt"}})
    (r / "risultati.json").write_text(json.dumps({"campioni": elenco, "parametri": {}, "corsa": "prova"}),
                                      encoding="utf-8")
    return r


def test_referto_frase_al_posto_del_campione_vuoto(tmp_path):
    sys.path.insert(0, str(RADICE / "motore"))
    import referto
    r = risultati(tmp_path, {"CASUALE": "metaphlan_casuale_profile.txt", "ERR478976": "metaphlan_feci_ERR478976_profile.txt"})
    d = referto.raccogli(r, {})
    html = referto.html_referto(d)
    sezione = html.split("<h2>2.")[1].split("<h2>3.")[0]
    assert "Campione CASUALE" in sezione and FRASE in sezione
    assert "Campione ERR478976" in sezione and FRASE not in sezione.split("Campione ERR478976")[1]
    assert d["campioni"][0]["sintesi"]["metaphlan"]["specie"] == 0


# --- avviso del motore (evento METAPHLAN_VUOTO), con il run.sh finto di test_pmn_motore ---
linux = pytest.mark.skipif(os.name == "nt", reason="process groups and signals: Linux/WSL only")


@linux
@pytest.mark.parametrize("profilo, avviso", [("metaphlan_casuale_profile.txt", True),
                                             ("metaphlan_feci_ERR478976_profile.txt", False)])
def test_evento_metaphlan_vuoto(tmp_path, profilo, avviso):
    sys.path.insert(0, str(RADICE / "tests"))
    from test_pmn_motore import STUB, lancia   # lancia controlla gia' ogni riga col contratto (tests/contratto.py)
    finto = 'echo "#mpa" > "$work/metaphlan/S1_profile.txt"'
    assert finto in STUB
    stub = tmp_path / "run_stub.sh"
    stub.write_text(STUB.replace(finto, 'cp "$PROFILO" "$work/metaphlan/S1_profile.txt"'), encoding="utf-8")
    home = tmp_path / "pmn"
    for d in ("stato", "log"):
        (home / d).mkdir(parents=True)
    (home / "installazione.env").write_text(f"PMN_ENVS={tmp_path / 'envs'}\nPMN_TMP={tmp_path / 'tmp'}\n", encoding="utf-8")
    progetto = tmp_path / "progetto" / "config.yaml"
    progetto.parent.mkdir()
    (tmp_path / "srr.txt").write_text("S1\n", encoding="utf-8")
    progetto.write_text(f"project_name: prova\npaths:\n  work_dir: {tmp_path / 'lavoro'}\n  srr_list: {tmp_path / 'srr.txt'}\n"
                        "hosts: [sus_scrofa]\nmotore: {kraken_db: rapido}\n", encoding="utf-8")
    env = {**os.environ, "PMN_HOME": str(home), "PMN_RUN_SH": str(stub), "PMN_ATTESA_RETE": "0",
           "PROFILO": str(DATI / profilo)}
    ev, codice = lancia(env, "esegui", "--progetto", str(progetto))
    assert codice == 0
    vuoti = [e for e in ev if e["tipo"] == "avviso" and e.get("codice") == "METAPHLAN_VUOTO"]
    if avviso:
        assert len(vuoti) == 1 and "S1" in vuoti[0]["messaggio"], vuoti
    else:
        assert vuoti == []
