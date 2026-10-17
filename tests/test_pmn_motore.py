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
for l in ${STUB_ETICHETTE:-size dl_S1 tq_S1 th_S1 trim_S1 hf_S1 multiqc mpa_S1 krk_S1 merge kmatrix report}; do
  echo "[INFO] [locale] $l"
  case "${STUB_MODO:-ok}" in
    lento) sleep 1 ;;
    spazio) [ "$l" = size ] && { echo "[FAIL] Not enough space: need ~9.0 GB, have 1.0 GB."; exit 1; } ;;
    rete) [ "$l" = size ] && { echo "[FAIL] ENA and NCBI could not be reached - nothing to download."; exit 1; } ;;
    ospite) case "$l" in hf_*) mkdir -p "$work/hostfilter_logs"   # come steps/21: 80 % delle coppie e' ospite
      printf '1000000 reads; of these:\n  1000000 (100.00%%) were paired; of these:\n    200000 (20.00%%) aligned concordantly 0 times\n' \
        > "$work/hostfilter_logs/${l#hf_}.sus_scrofa.bowtie2.log" ;; esac ;;
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


def due_campioni(tmp_path, nome, prima=()):
    """Progetto con read locali S1 e S2 (niente rete); prima = uscite gia' sul disco (corsa ripresa)."""
    read = tmp_path / "read"
    if not read.is_dir():
        read.mkdir()
        for s, n in (("S1", 200000), ("S2", 400000)):
            for m in (1, 2):
                with gzip.open(read / f"{s}_R{m}.fastq.gz", "wt") as f:
                    f.write("".join(f"@r{i}\nACGT\n+\nIIII\n" for i in range(n)))
    lavoro = tmp_path / f"lavoro_{nome}"
    for f in prima:
        (lavoro / f).parent.mkdir(parents=True, exist_ok=True)
        (lavoro / f).write_text("x", encoding="utf-8")
    progetto = tmp_path / nome / "config.yaml"
    progetto.parent.mkdir()
    progetto.write_text(f"data_source: local\npaths:\n  work_dir: {lavoro}\n  local_reads_dir: {read}\n", encoding="utf-8")
    sys.path.insert(0, os.path.join(ROOT, "motore"))
    import pmn_motore as pm
    camp = [(n, round(sum((read / x).stat().st_size for x in file) / pm.BYTE_PER_COPPIA), 0)
            for n, file in pm.campioni_locali(read)]
    return progetto, {e: s for e, _, _, s in pm.piano(camp, {})}


ETICHETTE_2 = "size trim_S1 hf_S1 trim_S2 hf_S2 multiqc mpa_S1 krk_S1 mpa_S2 krk_S2 merge kmatrix report"


def test_eta_segue_l_ordine_di_run_sh(ambiente, tmp_path):
    """17/10: MetaPhlAn e Kraken alternati per campione, MultiQC dopo l'ospite, il passo che parte conta intero."""
    env, _ = ambiente
    progetto, sec = due_campioni(tmp_path, "nuovo")
    ev, codice = lancia(env, "esegui", "--progetto", str(progetto), STUB_ETICHETTE=ETICHETTE_2)
    av = [e for e in ev if e["tipo"] == "avanzamento"]
    assert codice == 0 and [e["eta_s"] for e in av] == sorted((e["eta_s"] for e in av), reverse=True)
    pct = [e["percentuale"] for e in av]
    assert pct == sorted(pct) and pct[0] == 0 and pct[-1] < 100
    per = {(e["passo"], e["campione"]): e for e in av}
    resto = sec["krk_S1"] + sec["mpa_S2"] + sec["krk_S2"] + sec["riepilogo"] + sec["referto"]
    assert abs(per[("kraken", "S1")]["eta_s"] - resto) <= 1                       # Kraken di S1 non e' gia' fatto
    assert per[("kraken", "S1")]["passo_s"] == round(sec["krk_S1"])                # 17/10: durata del passo
    assert per[("controllo_qualita", None)]["eta_s"] < per[("ospite", "S2")]["eta_s"]   # MultiQC: l'ospite non torna
    assert av[-1]["passo"] == "referto" and av[-1]["eta_s"] == round(sec["referto"])
    assert abs(av[0]["eta_s"] - sum(sec.values())) <= 1                           # niente e' fatto


def test_eta_dopo_l_ospite_usa_le_coppie_vere(ambiente, tmp_path):
    """A1, 17/10: SF3RAt3 aveva il 68 % di ospite, non il 53 %: tolto l'ospite, il tempo che manca si ricalcola
    sulle coppie rimaste davvero (log di Bowtie2 di steps/21)."""
    env, _ = ambiente
    progetto, _ = due_campioni(tmp_path, "ospite")
    progetto.write_text(progetto.read_text(encoding="utf-8") + "hosts: [sus_scrofa]\n", encoding="utf-8")
    ev, codice = lancia(env, "esegui", "--progetto", str(progetto), STUB_ETICHETTE=ETICHETTE_2, STUB_MODO="ospite")
    import pmn_motore as pm
    read = tmp_path / "read"
    camp = [(n, round(sum((read / x).stat().st_size for x in file) / pm.BYTE_PER_COPPIA), 0)
            for n, file in pm.campioni_locali(read)]
    cfg = {"hosts": ["sus_scrofa"]}
    prima = {e: s for e, _, _, s in pm.piano(camp, cfg)}                         # quota fissa, 53 %
    dopo = {e: s for e, _, _, s in pm.piano(camp, cfg, {"S1": 0.8, "S2": 0.8})}  # misurata, 80 %
    per = {(e["passo"], e["campione"]): e for e in ev if e["tipo"] == "avanzamento"}
    assert codice == 0
    assert abs(per[("ospite", "S1")]["eta_s"] - sum(prima.values()) + prima["trim_S1"]) <= 1   # prima: quota fissa
    resto = dopo["krk_S1"] + dopo["mpa_S2"] + dopo["krk_S2"] + dopo["riepilogo"] + dopo["referto"]
    assert abs(per[("kraken", "S1")]["eta_s"] - resto) <= 1                                       # dopo: coppie vere


def test_quote_dai_log_dell_ospite(tmp_path):
    sys.path.insert(0, os.path.join(ROOT, "motore"))
    import pmn_motore as pm
    log = tmp_path / "hostfilter_logs"
    log.mkdir()
    pe = "{} reads; of these:\n  {} (100.00%) were paired; of these:\n    {} (31.71%) aligned concordantly 0 times\n"
    (log / "SRR4875285.sus_scrofa.bowtie2.log").write_text(pe.format(4351080, 4351080, 1379760), encoding="utf-8")
    (log / "SRR4875285.homo_sapiens.bowtie2.log").write_text(pe.format(1379760, 1379760, 1378590), encoding="utf-8")
    se = "1000 reads; of these:\n  1000 (100.00%) were unpaired; of these:\n    250 (25.00%) aligned 0 times\n"
    (log / "C.1.homo_sapiens.bowtie2.log").write_text(se, encoding="utf-8")          # lettura singola, nome col punto
    q = pm.quote_ospite(tmp_path)
    assert abs(q["SRR4875285"] - (1 - 1378590 / 4351080)) < 1e-9 and q["C.1"] == 0.75
    assert pm.quote_ospite(tmp_path / "manca") == {}


def test_eta_corsa_ripresa_salta_i_passi_fatti(ambiente, tmp_path):
    env, _ = ambiente
    progetto, sec = due_campioni(tmp_path, "nuovo")
    nuovo, _ = lancia(env, "esegui", "--progetto", str(progetto), STUB_ETICHETTE=ETICHETTE_2)
    fatti = ("nonhost/S1_nonhost_1.fastq.gz", "metaphlan/S1_profile.txt")   # run.sh salta trim, ospite e MetaPhlAn di S1
    ripreso, _ = due_campioni(tmp_path, "ripreso", fatti)
    ev, codice = lancia(env, "esegui", "--progetto", str(ripreso),
                        STUB_ETICHETTE="size trim_S2 hf_S2 multiqc krk_S1 mpa_S2 krk_S2 merge")
    primo = lambda ev: next(e for e in ev if e["tipo"] == "avanzamento")  # noqa: E731
    assert codice == 0 and abs(primo(nuovo)["eta_s"] - primo(ev)["eta_s"]
                               - (sec["trim_S1"] + sec["hf_S1"] + sec["mpa_S1"])) <= 1
    assert primo(ev)["percentuale"] > 0                                     # la barra riparte da dove era
