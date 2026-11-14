# -*- coding: utf-8 -*-
"""13/11/2026 (prova su Ubuntu in italiano): l'ordine dei campioni non dipende dalla lingua del sistema.
bash ordina i nomi trovati da un modello (*.gz, *_profile.txt) con la lingua del sistema: con it_IT "a" viene prima di
"B" e "C1_a" prima di "C1-b", con C il contrario. L'ordine dei campioni decide l'ordine delle colonne di
metaphlan_merged.tsv: la stessa analisi dava una tabella diversa su un PC in italiano.
Rosso sul codice di e574d05, verde dopo. Gira nella WSL:
  ~/.pmn/mamba/envs/pmn_reports_py/bin/python -m pytest tests/test_ordine_lingua.py"""
import shutil
import subprocess

import pytest

from test_f3_velocita import linux, motore, passi, run_sh

CAMPIONI = ("B", "a", "C1-b", "C1_a")
ORDINE_C = ["B", "C1-b", "C1_a", "a"]        # ordine dei codici dei caratteri, lo stesso di sorted() nel motore


def lingua_italiana():
    if not shutil.which("locale"):
        return False
    return "it_IT.utf8" in subprocess.run(["locale", "-a"], capture_output=True, text=True).stdout.split()


italiano = pytest.mark.skipif(not lingua_italiana(), reason="serve la lingua it_IT.UTF-8 (locale -a)")


def corsa(tmp_path, lingua):
    """Fase B vera di run.sh con gli strumenti finti: -> (campioni nell'ordine in cui sono profilati, tabella unita)"""
    cfg, env = motore(tmp_path, CAMPIONI, tool="metaphlan")
    env = {k: v for k, v in env.items() if not k.startswith("LC_")}
    p, testo = run_sh(cfg, {**env, "LANG": lingua, "LC_ALL": lingua})
    assert p.returncode == 0, testo
    ordine = [x[len("mpa_"):] for x in passi(testo, "[local] ") if x.startswith("mpa_")]
    return ordine, (tmp_path / "lavoro" / "results" / "metaphlan_merged.tsv").read_bytes()


@linux
@italiano
def test_ordine_dei_campioni_uguale_in_italiano_e_in_c(tmp_path):
    ordine_c, tabella_c = corsa(tmp_path / "c", "C")
    ordine_it, tabella_it = corsa(tmp_path / "it", "it_IT.UTF-8")
    assert ordine_c == ORDINE_C
    assert ordine_it == ORDINE_C                 # prima: a, B, C1_a, C1-b
    # profili uniti nello stesso ordine: stesse colonne di metaphlan_merged.tsv (i percorsi delle due prove cambiano)
    assert tabella_it.replace(b"/it/", b"/c/") == tabella_c
