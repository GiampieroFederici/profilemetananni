# -*- coding: utf-8 -*-
"""Revisione del 22/10, secondo giro (difetti dei revisori sulle correzioni del primo giro).
Ogni test è rosso sul codice di 7381eda e verde dopo la correzione.
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_revisione_g2.py"""
import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
linux = pytest.mark.skipif(os.name == "nt" or not shutil.which("bash"), reason="bin/run.sh: Linux/WSL only")


# ---------------- P01 (D3 di GD1): cartella nonhost personalizzata condivisa da due progetti ----------------
def installazione_finta(tmp_path):
    """Motore installato finto: python vero per parse_config.py, indici degli ospiti già pronti (niente download),
    fastp che fallisce (la corsa si ferma al primo campione da rifilare, nessun programma di analisi parte)."""
    envs, home, ospite = tmp_path / "envs", tmp_path / "pmn", tmp_path / "ospite"
    (envs / "pmn_reports_py" / "bin").mkdir(parents=True)
    os.symlink(sys.executable, envs / "pmn_reports_py" / "bin" / "python")
    (envs / "pmn_trim" / "bin").mkdir(parents=True)
    (envs / "pmn_trim" / "bin" / "fastp").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (envs / "pmn_trim" / "bin" / "fastp").chmod(0o755)
    for h in ("sus_scrofa", "bos_taurus"):
        (ospite / h).mkdir(parents=True)
        (ospite / h / f"{h}.1.bt2").write_text("indice finto", encoding="utf-8")
    home.mkdir()
    (home / "installazione.env").write_text(f"PMN_ENVS={envs}\nPMN_TMP={tmp_path / 'tmp'}\nPMN_OSPITE={ospite}\n",
                                            encoding="utf-8")
    return home


def progetto_custom(tmp_path, nome, campioni, condivisa):
    """Progetto con layout custom: read locali proprie, nonhost nella cartella condivisa."""
    letture = tmp_path / f"{nome}_read"
    letture.mkdir()
    for s in campioni:
        for m in (1, 2):
            with gzip.open(letture / f"{s}_{m}.fastq.gz", "wt") as g:
                g.write(f"@{s}\nACGT\n+\nIIII\n")
    cfg = tmp_path / nome / "config.yaml"
    cfg.parent.mkdir()
    return cfg, letture


def corsa_custom(home, cfg, letture, condivisa, hosts):
    cfg.write_text(f"project_name: {cfg.parent.name}\ndata_source: local\nhosts: {hosts}\nfilter_human: false\n"
                   f"paths:\n  layout: custom\n  work_dir: {cfg.parent / 'lavoro'}\n  local_reads_dir: {letture}\n"
                   f"  nonhost_dir: {condivisa}\nprofiling:\n  tool: metaphlan\n", encoding="utf-8")
    r = subprocess.run(["bash", str(RADICE / "bin" / "run.sh"), "--config", str(cfg), "--skip-preflight"],
                       capture_output=True, text=True, timeout=120, cwd=cfg.parent,
                       env={**os.environ, "PMN_HOME": str(home), "NO_COLOR": "1"})
    testo = r.stdout + r.stderr
    assert r.returncode != 0 and "step failed: trim_" in testo, testo
    return testo


def nonhost_finiti(condivisa, campione, contenuto):
    for m in (1, 2):
        (condivisa / f"{campione}_nonhost_{m}.fastq.gz").write_bytes(contenuto + bytes([m]))


def byte(condivisa, campione):
    return {f.name: f.read_bytes() for f in sorted(condivisa.glob(f"{campione}_nonhost*"))}


@linux
def test_p01_nonhost_condivisa_la_ripresa_non_tocca_i_file_dell_altro_progetto(tmp_path):
    """Due progetti (maiale e bovino) con la stessa cartella nonhost personalizzata: la ripresa di uno, anche coi
    parametri dell'ospite cambiati, cancella solo le uscite dei propri campioni; quelle dell'altro restano identiche."""
    home = installazione_finta(tmp_path)
    condivisa = tmp_path / "nonhost_condivisa"
    condivisa.mkdir()
    a = progetto_custom(tmp_path, "salame", ["A1", "A2"], condivisa)
    b = progetto_custom(tmp_path, "bresaola", ["B1", "B2"], condivisa)
    corsa_custom(home, *a, condivisa, "[sus_scrofa]")      # prime corse: ognuno registra i suoi parametri
    corsa_custom(home, *b, condivisa, "[bos_taurus]")
    nonhost_finiti(condivisa, "A1", b"maiale")              # rimozione dell'ospite finita su A1 e B1
    nonhost_finiti(condivisa, "B1", b"bovino")
    prima_a, prima_b = byte(condivisa, "A1"), byte(condivisa, "B1")
    assert len(prima_a) == len(prima_b) == 2

    corsa_custom(home, *a, condivisa, "[sus_scrofa]")      # ripresa del salame, stessi parametri: nulla si tocca
    assert byte(condivisa, "B1") == prima_b
    assert byte(condivisa, "A1") == prima_a

    testo = corsa_custom(home, *b, condivisa, "[bos_taurus, sus_scrofa]")   # bresaola con altri ospiti
    assert byte(condivisa, "B1") == {}, testo              # si rifanno le sue uscite...
    assert byte(condivisa, "A1") == prima_a                # ...non quelle del salame
    corsa_custom(home, *a, condivisa, "[sus_scrofa]")
    assert byte(condivisa, "A1") == prima_a
    assert not (condivisa / ".parametri").exists()         # il timbro sta nella cartella di lavoro del progetto
