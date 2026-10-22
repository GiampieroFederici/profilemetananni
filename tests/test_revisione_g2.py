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


# ---------------- P01 (D2 di GD1): barra e tempo restante dopo un cambio di parametri ----------------
def test_p01_gia_fatti_non_conta_le_uscite_che_run_sh_rifa(tmp_path, monkeypatch):
    """Kraken completo già fatto con l'ospite maiale (80 % delle coppie), poi rilancio con l'ospite bovino: run.sh,
    prima del primo passo, cancella profili e log dell'ospite fatti coi parametri vecchi (timbri .parametri) e li
    rifà. Barra e tempo restante non devono dare per fatto Kraken né usare la quota dell'ospite vecchio."""
    from types import SimpleNamespace
    sys.path.insert(0, str(RADICE / "motore"))
    import pmn_motore as pm
    prog = tmp_path / "p"
    lavoro = prog / "w"
    vecchi = [lavoro / "kraken" / "S1.bracken", lavoro / "hostfilter_logs" / "S1.sus_scrofa.bowtie2.log"]
    for f in vecchi:
        f.parent.mkdir(parents=True)
    vecchi[0].write_text("Kraken completo, ospite maiale\n", encoding="utf-8")
    vecchi[1].write_text("1000000 reads; of these:\n  1000000 (100.00%) were paired; of these:\n"
                         "    200000 (20.00%) aligned concordantly 0 times\n", encoding="utf-8")
    (prog / "campioni.txt").write_text("S1\n", encoding="utf-8")
    cfg = {"data_source": "ncbi", "hosts": ["bos_taurus"], "profiling": {"tool": "kraken"},
           "motore": {"kraken_db": "completo"}, "paths": {"work_dir": "./w", "srr_list": str(prog / "campioni.txt")}}

    class RunShFinto:   # come bin/run.sh: il blocco dei timbri gira prima di qualsiasi passo
        pid = 0

        def __init__(self, *a, **k):
            self.stdout = self.righe()

        @staticmethod
        def righe():
            for f in vecchi:
                f.unlink()
            yield "[WARN] Parametri della rimozione dell'ospite cambiati: rifaccio ospite, MetaPhlAn e Kraken\n"
            for e in ("size", "trim_S1", "hf_S1", "multiqc", "krk_S1", "kmatrix"):
                yield f"[INFO] [locale] {e}\n"

        def wait(self):
            return 0
    monkeypatch.setattr(pm.subprocess, "Popen", RunShFinto)
    monkeypatch.setattr(pm, "STATO", tmp_path / "stato")
    (tmp_path / "stato").mkdir()
    m = pm.Motore(SimpleNamespace(comando="esegui", progetto=str(prog / "config.yaml")))
    m.log = tmp_path / "x.log"
    av = []
    monkeypatch.setattr(m, "avanza", lambda passo, *a, **k: av.append({"passo": passo, **k}))
    camp = [("S1", 3_000_000, 0)]
    m._run_sh(prog / "config.yaml", cfg, tmp_path / "stato" / "esegui.lock", camp)
    sec = {e: s for e, _, _, s in pm.piano(camp, cfg)}            # quota dell'ospite ancora da misurare
    assert abs(av[0]["eta_s"] - sum(sec.values())) <= 1            # niente è fatto
    kraken = next(e for e in av if e["passo"] == "kraken")
    assert kraken["passo_s"] == round(sec["krk_S1"])               # Kraken si rifà intero
