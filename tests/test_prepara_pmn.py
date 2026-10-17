# -*- coding: utf-8 -*-
"""installer/windows/prepara_pmn.sh copia nella WSL pmn tutte le cartelle che il motore legge (A3).
Il 16/10 (L1a) copiava solo installer/ e motore/: su un PC nuovo pmn-motore non partiva (4839902).
Gira con la suite del motore:  ~/miniforge3/envs/pmn_reports_py/bin/python -m pytest tests/test_prepara_pmn.py"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
# PMN_PREPARA: un'altra versione dello script, per vedere il test rosso su quella di prima di 4839902
PREPARA = Path(os.environ.get("PMN_PREPARA") or RADICE / "installer" / "windows" / "prepara_pmn.sh")
PYTHON = [RADICE / "motore", RADICE / "steps", RADICE / "bin" / "lib"]
SHELL = [RADICE / "bin" / "run.sh", *(RADICE / "bin" / "lib").glob("*.sh"), *(RADICE / "installer").glob("*.sh"),
         *(RADICE / "motore").glob("*.sh"), RADICE / "motore" / "pmn-motore", *(RADICE / "steps").glob("*.sh")]


def copiate(script=PREPARA):
    """Le cartelle che lo script copia in /home/pmn/profilemetananni (gli argomenti "$radice/<nome>" di cp)."""
    righe = [r for r in Path(script).read_text(encoding="utf-8").splitlines() if r.lstrip().startswith("cp ")]
    return {n for r in righe for n in re.findall(r'\$radice/([A-Za-z0-9_.-]+)', r)}


def lette():
    """Le cartelle del progetto che il motore legge: ROOT / "x" nel Python, $PMN_ROOT/x nella shell."""
    nomi = set()
    for d in PYTHON:
        for f in d.glob("*.py"):
            nomi |= set(re.findall(r'ROOT / "([A-Za-z0-9_.-]+)"', f.read_text(encoding="utf-8")))
    for f in SHELL:
        if f.is_file():
            nomi |= set(re.findall(r'\$\{?PMN_ROOT\}?/([A-Za-z0-9_.-]+)', f.read_text(encoding="utf-8")))
    return nomi


def test_copia_tutto_quello_che_il_motore_legge():
    assert lette() >= {"bin", "installer", "motore", "refs", "steps"}      # il controllo trova davvero qualcosa
    assert lette() <= copiate(), f"prepara_pmn.sh non copia: {sorted(lette() - copiate())}"
    assert all((RADICE / n).is_dir() for n in copiate())


def test_il_motore_parte_dalla_copia(tmp_path):
    """Come prepara_pmn.sh: solo le cartelle copiate, poi pmn-motore info da lì (senza installazione)."""
    copia = tmp_path / "profilemetananni"
    for n in copiate():
        shutil.copytree(RADICE / n, copia / n, ignore=shutil.ignore_patterns("__pycache__"))
    r = subprocess.run([sys.executable, str(copia / "motore" / "pmn_motore.py"), "info"], capture_output=True,
                       text=True, encoding="utf-8", timeout=120,
                       env={**os.environ, "PMN_HOME": str(tmp_path / "senza_installazione")})
    assert r.returncode == 0, r.stdout + r.stderr
    fine = json.loads(r.stdout.strip().splitlines()[-1])
    assert fine["tipo"] == "fine" and fine["esito"] == "ok"
