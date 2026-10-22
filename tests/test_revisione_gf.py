# -*- coding: utf-8 -*-
"""Revisione del 22/10, gruppo GF-varie: P16 (installatore, riavvio in sospeso) e P18 (chiave API della Fase C).
P16 solo su Windows, P18 solo su POSIX (si lancia nella WSL Ubuntu)."""
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
PS1 = RADICE / "installer" / "windows" / "installa_pmn.ps1"
sys.path.insert(0, str(RADICE / "steps"))
import _biomni_consent as cs  # noqa: E402


def powershell(script):
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; " + script],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.mark.skipif(os.name != "nt", reason="installatore Windows")
def test_p16_aggiornamento_di_windows_non_conta_come_riavvio_per_wsl(tmp_path):
    """P16: la chiave CBS RebootPending la crea qualsiasi aggiornamento di Windows. Da sola faceva credere che WSL
    non fosse pronta (permesso inutile, riavvio chiesto a ogni accesso). Conta solo dopo il NOSTRO wsl --install."""
    segno, nessuno = tmp_path / "wsl_installata.txt", tmp_path / "nessuno.txt"
    chiave = "HKCU:\\Software\\pmn_prova_rebootpending"
    powershell(f"Set-Content '{segno}' x; New-Item '{chiave}' -Force | Out-Null")
    try:
        r = powershell(f". '{PS1}'; RiavvioInSospeso '{nessuno}' '{chiave}'; RiavvioInSospeso '{segno}' '{chiave}'; "
                       f"RiavvioInSospeso '{segno}' '{chiave}_assente'").split()
    finally:
        powershell(f"Remove-Item '{chiave}' -Force")
    assert r == ["False", "True", "False"]   # aggiornamento estraneo: no; nostro wsl --install: sì; già riavviato: no
    testo = PS1.read_text(encoding="utf-8-sig")
    fase1 = testo[testo.index("if ($Fase -eq 1 -and -not (WslPronta))"):testo.index("# ===================== fase 2")]
    assert fase1.index("if ($c -ne 0) { Ferma") < fase1.index("wsl_installata.txt") < fase1.index("if (-not (WslPronta)) { ChiediRiavvio }")
    fase2 = testo[testo.index("# ===================== fase 2"):]
    assert fase2.index("if (-not (WslPronta)) { ChiediRiavvio }") < fase2.index("Remove-Item (Join-Path $Cartella 'wsl_installata.txt')")


def test_p18_chiave_api_mai_leggibile_da_altri_neanche_per_un_attimo(tmp_path, monkeypatch):
    """P18: store_credential scriveva il file con i permessi dell'umask (0644) e solo dopo faceva chmod 0600."""
    if os.name != "posix":
        pytest.skip("POSIX permissions only")
    path = tmp_path / "pmn" / "credentials"
    visti = []
    chmod_vero = os.chmod

    def spia(p, m, *a, **k):
        visti.append(stat.S_IMODE(os.stat(p).st_mode))
        return chmod_vero(p, m, *a, **k)

    monkeypatch.setattr(cs.os, "chmod", spia)
    vecchia = os.umask(0o022)
    try:
        cs.store_credential(path, "OPENAI_API_KEY", "secret")
    finally:
        os.umask(vecchia)
    assert visti and visti[0] == 0o600                                   # già 0600 prima del chmod
    assert stat.S_IMODE(os.stat(path.parent).st_mode) == 0o700           # cartella nuova solo per l'utente
