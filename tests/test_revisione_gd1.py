# -*- coding: utf-8 -*-
"""Gruppo di correzione GD1 (revisione del 22/10, ripresa su 245128e): P01, P04, P07.
Ogni test è rosso sul codice di 245128e e verde dopo la correzione.
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_revisione_gd1.py"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "motore"))
FINTO = RADICE / "installer" / "finto"
linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="bin/run.sh e steps/*.sh: Linux/WSL only")


def eseguibile(cartella, nome, testo):
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / nome).write_text(testo, encoding="utf-8")
    (cartella / nome).chmod(0o755)


# ---------------- P01: parametri cambiati -> si rifanno solo le uscite che ne dipendono ----------------
USCITE = {"ospite": "nonhost/S1_nonhost_1.fastq.gz", "log_ospite": "hostfilter_logs/S1.sus_scrofa.bowtie2.log",
          "kraken": "kraken/S1.bracken", "metaphlan": "metaphlan/S1_profile.txt"}


def prepara(lavoro):
    for f in USCITE.values():
        (lavoro / f).parent.mkdir(parents=True, exist_ok=True)
        (lavoro / f).write_text("vecchio", encoding="utf-8")


def presenti(lavoro):
    return {k for k, f in USCITE.items() if (lavoro / f).exists()}


def corsa(tmp_path, tool="both", kraken_db="db_completo", hosts="[sus_scrofa]"):
    """run.sh vero (non dry-run): data_source ncbi senza srr_list lo ferma al primo passo, dopo i controlli dei
    parametri. Nessun programma di analisi parte."""
    envs = tmp_path / "envs" / "pmn_reports_py" / "bin"
    home = tmp_path / "pmn"
    if not envs.exists():
        envs.mkdir(parents=True)
        os.symlink(sys.executable, envs / "python")     # parse_config.py con PyYAML, come il motore installato
        home.mkdir()
        (home / "installazione.env").write_text(f"PMN_ENVS={tmp_path / 'envs'}\nPMN_TMP={tmp_path / 'tmp'}\n",
                                                encoding="utf-8")
    cfg = tmp_path / "progetto" / "config.yaml"
    cfg.parent.mkdir(exist_ok=True)
    cfg.write_text(f"project_name: prova\ndata_source: ncbi\nhosts: {hosts}\npaths:\n  work_dir: {tmp_path / 'lavoro'}\n"
                   f"profiling:\n  tool: {tool}\n  kraken_db: {tmp_path / kraken_db}\nmotore: {{kraken_db: rapido}}\n",
                   encoding="utf-8")
    r = subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight"],
                       capture_output=True, text=True, timeout=120, cwd=cfg.parent,
                       env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1"})
    testo = r.stdout + r.stderr
    assert r.returncode != 0 and "srr_list is empty" in testo, testo
    return testo


@linux
def test_p01_parametri_cambiati_rifanno_solo_le_uscite_che_ne_dipendono(tmp_path):
    lavoro = tmp_path / "lavoro"
    prepara(lavoro)
    testo = corsa(tmp_path)              # pmn_work senza timbri (di prima della correzione o di K4): si rifà tutto
    assert presenti(lavoro) == set(), testo
    assert "Kraken" in testo and "MetaPhlAn" in testo
    prepara(lavoro)
    corsa(tmp_path)                      # stessi parametri: nulla si tocca (ripresa)
    assert presenti(lavoro) == set(USCITE)
    corsa(tmp_path, kraken_db="db_08gb")   # altro database di Kraken: solo i profili di Kraken
    assert presenti(lavoro) == {"ospite", "log_ospite", "metaphlan"}
    prepara(lavoro)
    corsa(tmp_path, tool="metaphlan")    # corsa intermedia solo MetaPhlAn: il timbro di Kraken resta quello di 08gb
    corsa(tmp_path, kraken_db="db_08gb")
    assert presenti(lavoro) == set(USCITE)
    corsa(tmp_path, kraken_db="db_08gb", hosts="[bos_taurus]")   # altro ospite: altre read, si rifà tutto a valle
    assert presenti(lavoro) == set()


def motore(tmp_path, strumento="both", progetto=("SRRA",), lavoro=("SRRA", "SRRB")):
    """Motore._risultati vero su un pmn_work finto (profili di installer/finto); finti solo installazione, versioni
    e referto."""
    import pmn_motore as pm
    prog, w = tmp_path / "p", tmp_path / "p" / "w"
    for d in ("metaphlan", "kraken", "results"):
        (w / d).mkdir(parents=True)
    for nome in lavoro:
        shutil.copy(FINTO / "SRR4875279_profile.txt", w / "metaphlan" / f"{nome}_profile.txt")
        shutil.copy(FINTO / "SRR4875279.bracken", w / "kraken" / f"{nome}.bracken")
        shutil.copy(FINTO / "SRR4875279.k2report", w / "kraken" / f"{nome}.k2report")
    shutil.copy(FINTO / "parameters.tsv", w / "results" / "parameters.tsv")
    (prog / "campioni.txt").write_text("".join(f"{n}\n" for n in progetto), encoding="utf-8")
    cfg = {"data_source": "ncbi", "paths": {"layout": "managed", "work_dir": "./w", "srr_list": str(prog / "campioni.txt")},
           "profiling": {"tool": strumento}}
    (prog / "config.yaml").write_text(json.dumps(cfg), encoding="utf-8")
    m = pm.Motore(SimpleNamespace(comando="esegui", progetto=str(prog / "config.yaml")))
    m._referto = lambda r, p: {"html": None, "pdf": None, "xlsx": None}
    m.log = tmp_path / "x.log"
    m.log.write_text("", encoding="utf-8")
    return m, prog, cfg


@pytest.fixture
def finti(monkeypatch):
    import pmn_motore as pm
    monkeypatch.setattr(pm, "installazione", lambda: {})
    monkeypatch.setattr(pm, "versione", lambda *a: None)


@pytest.mark.parametrize("strumento,resta,manca", [("metaphlan", "metaphlan", "kraken"), ("kraken", "kraken", "metaphlan")])
def test_p01_referto_solo_coi_profili_del_metodo_che_gira(tmp_path, finti, strumento, resta, manca):
    """Corsa con entrambi, poi rilancio con un solo metodo: i profili dell'altro in pmn_work sono vecchi e i loro
    parametri non sono più in parameters.tsv (Kraken senza soglia né database nel referto)."""
    m, prog, cfg = motore(tmp_path, strumento, lavoro=("SRRA",))
    out = m._risultati(prog / "config.yaml", cfg)
    assert [list(c["file"]) for c in out["campioni"]] == [[resta]]
    assert not list((prog / "risultati" / manca).iterdir())


# ---------------- P04: risultati.json e referto solo coi campioni del progetto ----------------
def test_p04_risultati_solo_campioni_del_progetto(tmp_path, finti):
    m, prog, cfg = motore(tmp_path)
    out = m._risultati(prog / "config.yaml", cfg)
    assert [c["nome"] for c in out["campioni"]] == ["SRRA"]
    assert not (prog / "risultati" / "metaphlan" / "SRRB_profile.txt").exists()
    assert not (prog / "risultati" / "kraken" / "SRRB.bracken").exists()


def test_p04_senza_elenco_leggibile_restano_tutti(tmp_path, finti):
    """Ripiego: se l'elenco dei campioni non si legge, come prima (tutti quelli in pmn_work)."""
    m, prog, cfg = motore(tmp_path)
    (prog / "campioni.txt").unlink()
    out = m._risultati(prog / "config.yaml", cfg)
    assert [c["nome"] for c in out["campioni"]] == ["SRRA", "SRRB"]


# ---------------- P07: tabella unita e MultiQC rifatte se i campioni cambiano ----------------
MERGE = """#!/usr/bin/env bash
printf '#mpa_vJan25_CHOCOPhlAnSGB_202503\\nclade_name'
for f in "$@"; do b=$(basename "$f"); printf '\\t%s' "${b%_profile.txt}"; done
printf '\\n'
"""
MULTIQC = """#!/usr/bin/env bash
while [ $# -gt 0 ]; do case "$1" in --outdir) o="$2"; shift 2 ;; *) shift ;; esac; done
echo corsa >> "$o/prova_multiqc_report.html"
"""


def passo(script, bin_dir, *arg):
    r = subprocess.run(["bash", str(RADICE / "steps" / script), *map(str, arg)], capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "NO_COLOR": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout + r.stderr


@linux
def test_p07_tabella_unita_rifatta_con_un_profilo_nuovo(tmp_path):
    eseguibile(tmp_path / "bin", "merge_metaphlan_tables.py", MERGE)
    mpa, uscita = tmp_path / "mpa", tmp_path / "res" / "metaphlan_merged.tsv"
    mpa.mkdir()
    for n in ("A", "B"):
        (mpa / f"{n}_profile.txt").write_text("x", encoding="utf-8")
    passo("31_merge_metaphlan.sh", tmp_path / "bin", "--in", mpa, "--out", uscita)
    assert uscita.read_text().splitlines()[1] == "clade_name\tA\tB"
    (mpa / "C_profile.txt").write_text("x", encoding="utf-8")      # campione aggiunto al progetto
    passo("31_merge_metaphlan.sh", tmp_path / "bin", "--in", mpa, "--out", uscita)
    assert uscita.read_text().splitlines()[1] == "clade_name\tA\tB\tC"


@linux
def test_p07_multiqc_rifatto_solo_con_un_file_qc_nuovo(tmp_path):
    eseguibile(tmp_path / "bin", "multiqc", MULTIQC)
    w = tmp_path / "w"
    (w / "trim").mkdir(parents=True)
    (w / "trim" / "S1_fastp.json").write_text("{}", encoding="utf-8")
    rapporto = w / "multiqc" / "prova_multiqc_report.html"
    args = ("--in", w, "--out", w / "multiqc", "--title", "prova")
    passo("22_multiqc.sh", tmp_path / "bin", *args)
    passo("22_multiqc.sh", tmp_path / "bin", *args)                 # niente di nuovo: salto (ripresa)
    assert rapporto.read_text().splitlines() == ["corsa"]
    dopo = rapporto.stat().st_mtime + 10
    for f in ("results/parameters.tsv", "trim/S2.triage_qc.json"):   # file nuovi che non sono del QC: salto
        (w / f).parent.mkdir(exist_ok=True)
        (w / f).write_text("x", encoding="utf-8")
        os.utime(w / f, (dopo, dopo))
    passo("22_multiqc.sh", tmp_path / "bin", *args)
    assert rapporto.read_text().splitlines() == ["corsa"]
    (w / "trim" / "S2_fastp.json").write_text("{}", encoding="utf-8")   # campione aggiunto: MultiQC si rifà
    os.utime(w / "trim" / "S2_fastp.json", (dopo, dopo))
    passo("22_multiqc.sh", tmp_path / "bin", *args)
    assert rapporto.read_text().splitlines() == ["corsa", "corsa"]
