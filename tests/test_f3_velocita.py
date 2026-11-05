# -*- coding: utf-8 -*-
"""F3 (PMN 1.2, 5/11/2026): più veloce senza cambiare i risultati. Proposte e criteri, fissati prima dei dati:
implementazione/decisioni/2026-11-05_F3_proposte_velocita_RAM.md (privata).
- run.sh non si ferma più se il database di Kraken sta su un disco senza lettura anticipata (tmpfs, rete).
- L5: la stima del tempo usa le quote d'ospite misurate (anche per i campioni non ancora filtrati).
I test con bash girano nella WSL:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_f3_velocita.py"""
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "motore"))
import pmn_motore as pm  # noqa: E402

linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="bin/run.sh: Linux/WSL only")
INDICE = "mpa_vJan25_CHOCOPhlAnSGB_202503"

# --- strumenti finti del motore installato (PMN_ENVS) ---
READ_FASTX = """#!/usr/bin/env bash
printf '@r1__1\\nACGT\\n+\\nIIII\\n'
echo "2 100.0 0" >&2
"""
BOWTIE2 = """#!/usr/bin/env bash
while [ $# -gt 0 ]; do case "$1" in -S) SAM="$2"; shift 2;; -x) X="$2"; shift 2;; *) shift;; esac; done
echo "$X" >> "$TRACCIA/bowtie2.txt"
printf 'r1__1\\t0\\tGeneID:1\\t1\\t42\\t4M\\t*\\t0\\t0\\tACGT\\tIIII\\tAS:i:0\\n' > "$SAM"
"""
# python di pmn_metaphlan (metaphlan_mapout.py): annota gli argomenti e scrive il profilo
MPA_PY = """#!/usr/bin/env python3
import sys, os
a = sys.argv[2:]
with open(os.path.join(os.environ["TRACCIA"], "metaphlan.txt"), "a") as f:
    f.write(" ".join(a) + "\\n")
open(a[a.index("-o") + 1], "w").write("#metaphlan " + a[0] + "\\n")
"""
MERGE = """#!/usr/bin/env bash
cat "$@"
"""


def motore(tmp_path, campioni=("S1", "S2"), tool="metaphlan"):
    """Motore installato finto, read senza ospite già pronte (nonhost) e config del progetto. -> (config, env)"""
    envs, lavoro, tr = tmp_path / "envs", tmp_path / "lavoro", tmp_path / "traccia"
    for d in (envs / "pmn_metaphlan" / "bin", envs / "pmn_reports_py" / "bin", tmp_path / "pmn_tmp", tr,
              lavoro / "nonhost", tmp_path / "read", tmp_path / "db_mpa", tmp_path / "krk"):
        d.mkdir(parents=True, exist_ok=True)
    for nome, testo in (("read_fastx.py", READ_FASTX), ("bowtie2", BOWTIE2), ("python", MPA_PY),
                        ("merge_metaphlan_tables.py", MERGE)):
        f = envs / "pmn_metaphlan" / "bin" / nome
        f.write_text(testo, encoding="utf-8")
        f.chmod(0o755)
    (envs / "pmn_reports_py" / "bin" / "python").symlink_to(sys.executable)   # parse_config.py e l'arbitro veri
    home = tmp_path / "home"
    home.mkdir()
    (home / "installazione.env").write_text(
        f"PMN_ENVS={envs}\nPMN_TMP={tmp_path / 'pmn_tmp'}\nPMN_FETTE={tmp_path / 'fette'}\nPMN_MPA_DB={tmp_path / 'db_mpa'}\n"
        f"PMN_KRAKEN_COMPLETO={tmp_path / 'krk'}\n", encoding="utf-8")
    for s in campioni:
        for i in (1, 2):
            dati = gzip.compress(b"@r\nACGT\n+\nIIII\n")
            (tmp_path / "read" / f"{s}_{i}.fastq.gz").write_bytes(dati)
            (lavoro / "nonhost" / f"{s}_nonhost_{i}.fastq.gz").write_bytes(dati)
    cfg = tmp_path / "progetto" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_text(f"project_name: prova\ndata_source: local\nhosts: [sus_scrofa]\npaths:\n  work_dir: {lavoro}\n"
                   f"  local_reads_dir: {tmp_path / 'read'}\nprofiling:\n  tool: {tool}\n  metaphlan_index: {INDICE}\n"
                   "motore:\n  metaphlan_modo: fette\n  kraken_db: completo\nexecution:\n  threads: 2\n"
                   "analysis:\n  report: false\n  diversity: false\n", encoding="utf-8")
    env = {**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1", "PMN_LANG": "en", "TRACCIA": str(tr)}
    return cfg, env


def run_sh(cfg, env, *extra):
    p = subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight", "--phase", "b",
                        *extra], capture_output=True, text=True, timeout=120, cwd=cfg.parent, env=env)
    return p, p.stdout + p.stderr


def passi(testo, prefisso):
    return [r.split(prefisso, 1)[1].strip() for r in testo.splitlines() if prefisso in r]


@linux
def test_kraken_su_un_disco_senza_lettura_anticipata(tmp_path):
    """Database di Kraken su tmpfs (qui tmp_path): lsblk falliva e run.sh si fermava senza un messaggio (uscita 32)."""
    cfg, env = motore(tmp_path, ("S1", "S2", "S3"), tool="both")
    p, testo = run_sh(cfg, env, "--dry-run")
    assert p.returncode == 0, testo
    profilatori = [x for x in passi(testo, "DRY-RUN step:") if x.startswith(("mpa_", "krk_"))]
    assert profilatori == ["mpa_S1", "krk_S1", "mpa_S2", "krk_S2", "mpa_S3", "krk_S3"]


# --- L5: stima del tempo con le quote d'ospite misurate ---
CFG = {"hosts": ["sus_scrofa"], "profiling": {"tool": "both"}, "motore": {"kraken_db": "completo"}}


def test_l5_campioni_non_misurati_prendono_la_media_delle_quote_misurate():
    camp = [("A", 1_000_000, 0), ("B", 1_000_000, 0)]
    sec = {e: s for e, _, _, s in pm.piano(camp, CFG, {"A": 0.9})}       # A filtrato: 90 % di ospite
    assert sec["krk_B"] == pytest.approx(sec["krk_A"])                    # B: 90 %, non il 53 % fisso
    senza = {e: s for e, _, _, s in pm.piano(camp, CFG)}
    assert senza["krk_B"] == pytest.approx(senza["krk_A"])
    assert sec["krk_A"] == pytest.approx(senza["krk_A"] * 0.1 / (1 - pm.OSPITE_QUOTA))


def test_l5_stima_usa_le_quote_di_una_corsa_precedente(tmp_path):
    """Progetto già analizzato una volta (log dell'ospite in pmn_work): la stima usa la quota misurata (90 %)."""
    read = tmp_path / "read"
    read.mkdir()
    for i in (1, 2):
        with gzip.open(read / f"A_R{i}.fastq.gz", "wt") as f:
            f.write("@r\nACGT\n+\nIIII\n" * 1_000_000)   # 1 M di coppie: Kraken stimato in minuti, non in secondi
    cfg = tmp_path / "progetto" / "config.yaml"
    cfg.parent.mkdir()
    cfg.write_text(f"data_source: local\nhosts: [sus_scrofa]\npaths:\n  local_reads_dir: {read}\n", encoding="utf-8")

    def kraken():
        r = subprocess.run([sys.executable, str(RADICE / "motore" / "pmn_motore.py"), "stima", "--progetto", str(cfg)],
                           capture_output=True, text=True, encoding="utf-8", timeout=120,
                           env={**os.environ, "PMN_HOME": str(tmp_path / "pmn_vuota")})
        assert r.returncode == 0, r.stdout + r.stderr
        return json.loads(r.stdout.strip().splitlines()[-1])["risultato"]["tempo_s"]["kraken"]
    prima = kraken()
    log = cfg.parent / "pmn_work" / "hostfilter_logs"
    log.mkdir(parents=True)
    (log / "A.sus_scrofa.bowtie2.log").write_text(
        "1000 reads; of these:\n  1000 (100.00%) were paired; of these:\n    100 (10.00%) aligned concordantly 0 times\n")
    assert kraken() == pytest.approx(prima * 0.1 / (1 - pm.OSPITE_QUOTA), abs=1)
