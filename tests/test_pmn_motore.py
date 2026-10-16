# -*- coding: utf-8 -*-
"""The real engine (motore/pmn_motore.py, D053) speaks the engine-GUI contract like the fake one.
run.sh is replaced by a stub that prints the same step labels, so the tests take seconds; the real
run on SF3RAt7 is criterion P3, done by hand in WSL."""
import gzip
import json
import os
import subprocess
import sys
import time

import pytest

from contratto import controlla

pytestmark = pytest.mark.skipif(os.name == "nt", reason="process groups and signals: Linux/WSL only")

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MOTORE = os.path.join(ROOT, "motore", "pmn_motore.py")
STUB = r"""#!/usr/bin/env bash
# stub of bin/run.sh: same "[locale] <label>" lines; outputs where run.sh puts them
cfg=$2; work=$(awk '/work_dir/ {print $2}' "$cfg")
for l in size dl_S1 tq_S1 th_S1 trim_S1 hf_S1 multiqc mpa_S1 krk_S1 merge kmatrix report; do
  echo "[INFO] [locale] $l"
  case "${STUB_MODO:-ok}" in
    lento) sleep 1 ;;
    spazio) [ "$l" = size ] && { echo "[FAIL] Not enough space: need ~9.0 GB, have 1.0 GB."; exit 1; } ;;
    rete) [ "$l" = size ] && { echo "[FAIL] ENA and NCBI could not be reached - nothing to download."; exit 1; } ;;
  esac
done
mkdir -p "$work/metaphlan" "$work/kraken" "$work/results"
echo "#mpa" > "$work/metaphlan/S1_profile.txt"
printf '1.0\t10\t10\tU\t0\tunclassified\n99.0\t990\t5\tR\t1\troot\n' > "$work/kraken/S1.k2report"
echo "name" > "$work/kraken/S1.bracken"
printf 'parameter\tvalue\nmetaphlan_index\tmpa_vJan25_CHOCOPhlAnSGB_202503\n' > "$work/results/parameters.tsv"
"""


@pytest.fixture
def ambiente(tmp_path):
    home = tmp_path / "pmn"
    for d in ("stato", "log"):
        (home / d).mkdir(parents=True)
    (home / "installazione.env").write_text(f"PMN_ENVS={tmp_path / 'envs'}\nPMN_TMP={tmp_path / 'tmp'}\n", encoding="utf-8")
    stub = tmp_path / "run_stub.sh"
    stub.write_text(STUB, encoding="utf-8")
    progetto = tmp_path / "progetto" / "config.yaml"
    progetto.parent.mkdir()
    (tmp_path / "srr.txt").write_text("S1\n", encoding="utf-8")
    progetto.write_text(f"project_name: prova\npaths:\n  work_dir: {tmp_path / 'lavoro'}\n  srr_list: {tmp_path / 'srr.txt'}\n"
                        "hosts: [sus_scrofa]\nmotore: {kraken_db: rapido}\n", encoding="utf-8")
    env = {**os.environ, "PMN_HOME": str(home), "PMN_RUN_SH": str(stub), "PMN_ATTESA_RETE": "0"}
    return env, progetto


def lancia(env, *arg, **extra):
    r = subprocess.run([sys.executable, MOTORE, *arg], capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env={**env, **extra})
    return controlla(r.stdout, r.returncode, arg[0]), r.returncode


def test_senza_installazione(tmp_path):
    env = {**os.environ, "PMN_HOME": str(tmp_path / "vuota")}
    ev, codice = lancia(env, "info")
    assert codice == 0 and not any(d["installato"] for d in ev[-1]["risultato"]["database"])
    ev, codice = lancia(env, "verifica")
    assert codice == 2 and ev[-2]["codice"] == "DB_MANCANTE"


def test_esegui_ok(ambiente):
    env, progetto = ambiente
    ev, codice = lancia(env, "esegui", "--progetto", str(progetto))
    assert codice == 0 and ev[-1]["esito"] == "ok"
    pct = [e["percentuale"] for e in ev if e["tipo"] == "avanzamento"]
    assert pct == sorted(pct) and {e["passo"] for e in ev if e["tipo"] == "avanzamento"} >= {"download", "ospite", "metaphlan", "kraken", "riepilogo"}
    r = json.loads((progetto.parent / "risultati" / "risultati.json").read_text(encoding="utf-8"))
    assert r["campioni"][0]["nome"] == "S1" and r["campioni"][0]["coppie_dopo_ospite"] == 1000
    assert any("Sscrofa11.1" in c for c in r["citazioni"])
    assert not (progetto.parent.parent / "pmn" / "stato" / "esegui.lock").exists()
    # v0.2: referto fatto alla fine dell'analisi, e rifatto a richiesta
    assert r["referto"]["html"] == "referto/referto.html"
    assert r["campioni"][0]["sintesi"]["metaphlan"]["specie"] == 0      # profilo finto vuoto: frase lo stesso
    assert (progetto.parent / "risultati" / "referto" / "referto.html").is_file()
    ev, codice = lancia(env, "referto", "--progetto", str(progetto))
    assert codice == 0 and ev[-1]["risultato"]["referto"]["html"] == "referto/referto.html"


def test_spazio_e_rete(ambiente):
    env, progetto = ambiente
    ev, codice = lancia(env, "esegui", "--progetto", str(progetto), STUB_MODO="spazio")
    assert codice == 1 and ev[-2]["codice"] == "SPAZIO_INSUFFICIENTE"
    assert ev[-2]["passo"] == "download"            # v0.2: passo in cui si e' fermato
    ev, codice = lancia(env, "esegui", "--progetto", str(progetto), STUB_MODO="rete")
    assert codice == 1 and ev[-2]["codice"] == "DOWNLOAD_FALLITO"
    assert [e["codice"] for e in ev if e["tipo"] == "avviso"] == ["RETE_INTERROTTA", "RETE_INTERROTTA"]   # 3 tentativi


def test_gia_in_corso_e_annulla(ambiente):
    env, progetto = ambiente
    primo = subprocess.Popen([sys.executable, MOTORE, "esegui", "--progetto", str(progetto)], stdout=subprocess.PIPE,
                             text=True, encoding="utf-8", env={**env, "STUB_MODO": "lento"})
    blocco = progetto.parent.parent / "pmn" / "stato" / "esegui.lock"
    for _ in range(100):
        if blocco.exists() and json.loads(blocco.read_text(encoding="utf-8")).get("pgid"):
            break
        time.sleep(0.1)
    dati = json.loads(blocco.read_text(encoding="utf-8"))
    ev, codice = lancia(env, "esegui", "--progetto", str(progetto))
    assert codice == 1 and ev[-2]["codice"] == "GIA_IN_CORSO"
    ev, codice = lancia(env, "annulla", "--corsa", dati["corsa"])
    assert codice == 0 and ev[-1]["risultato"] == {"annullata": True}
    out, _ = primo.communicate(timeout=30)
    ev = controlla(out, primo.returncode, "esegui")
    assert primo.returncode == 3 and ev[-1]["esito"] == "annullata"
    assert not blocco.exists()
    with pytest.raises(ProcessLookupError):
        os.killpg(dati["pgid"], 0)   # nessun processo rimasto


def test_stima_read_locali(ambiente, tmp_path):
    env, _ = ambiente
    read = tmp_path / "read"
    read.mkdir()
    for m in (1, 2):
        with gzip.open(read / f"C1_R{m}.fastq.gz", "wt") as f:
            f.write("@r\nACGT\n+\nIIII\n" * 1000)
    progetto = tmp_path / "locale.yaml"
    progetto.write_text(f"data_source: local\npaths:\n  local_reads_dir: {read}\n", encoding="utf-8")
    ev, codice = lancia(env, "stima", "--progetto", str(progetto))
    assert codice == 0 and ev[-1]["risultato"]["campioni"] == 1


def test_esegui_tempo_stimato(ambiente, tmp_path):
    """v0.2 (richiesta 3 di S4): eta_s con le regole di stima; qui le read sono locali, quindi niente rete."""
    env, _ = ambiente
    read = tmp_path / "read"
    read.mkdir()
    for m in (1, 2):
        with gzip.open(read / f"S1_R{m}.fastq.gz", "wt") as f:
            f.write("@r\nACGT\n+\nIIII\n" * 200000)
    progetto = tmp_path / "locale" / "config.yaml"
    progetto.parent.mkdir()
    progetto.write_text(f"data_source: local\npaths:\n  work_dir: {tmp_path / 'lavoro2'}\n  srr_list: {tmp_path / 'srr.txt'}\n"
                        f"  local_reads_dir: {read}\n", encoding="utf-8")
    ev, codice = lancia(env, "esegui", "--progetto", str(progetto))
    eta = [e["eta_s"] for e in ev if e["tipo"] == "avanzamento" and e["passo"] != "referto"]
    assert codice == 0 and all(isinstance(x, int) and x >= 0 for x in eta)
    assert eta == sorted(eta, reverse=True) and eta[0] > 0      # scende fino alla fine
