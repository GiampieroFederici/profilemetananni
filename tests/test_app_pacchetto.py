# -*- coding: utf-8 -*-
"""B1: il pacchetto dell'app. installa_pmn.ps1 copia l'app e mette le icone (rifacibile); il pacchetto contiene
le stesse cartelle che prepara_pmn.sh copia nella WSL e il doppio clic punta all'installatore vero.
Solo su Windows:  app\\.venv\\Scripts\\python -m pytest tests/test_app_pacchetto.py"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="installatore Windows")
RADICE = Path(__file__).resolve().parent.parent
PS1 = RADICE / "installer" / "windows" / "installa_pmn.ps1"


def powershell(script):
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_installa_app_copia_e_mette_le_icone(tmp_path):
    sorgente = tmp_path / "pacchetto" / "ProfileMetaNanni"
    (sorgente / "_internal").mkdir(parents=True)
    (sorgente / "ProfileMetaNanni.exe").write_bytes(b"nuova")
    (sorgente / "_internal" / "libreria.dll").write_bytes(b"x")
    exe = tmp_path / "locale" / "app" / "ProfileMetaNanni.exe"
    exe.parent.mkdir(parents=True)
    (exe.parent / "vecchio.txt").write_text("di una versione prima")          # rifare l'installazione lo toglie
    lnk = [tmp_path / "Desktop.lnk", tmp_path / "Start.lnk"]
    chiama = f". '{PS1}'; InstallaApp '{sorgente}' '{exe}' @('{lnk[0]}', '{lnk[1]}')"
    powershell(chiama)
    powershell(chiama)                                                           # due volte: deve andare lo stesso
    assert exe.read_bytes() == b"nuova" and (exe.parent / "_internal" / "libreria.dll").is_file()
    assert not (exe.parent / "vecchio.txt").exists()
    for c in lnk:
        bersaglio = powershell(f"(New-Object -ComObject WScript.Shell).CreateShortcut('{c}').TargetPath").strip()
        assert Path(bersaglio) == exe


def test_pacchetto_come_prepara_pmn():
    sys.path.insert(0, str(RADICE / "installer" / "windows"))
    import costruisci_pacchetto as c
    from test_prepara_pmn import copiate
    assert set(c.MOTORE) == copiate()                                            # stesse cartelle copiate nella WSL
    bersaglio = c.LANCIATORE.split('"%~dp0')[1].split('"')[0].replace("\\", "/")
    assert (RADICE / bersaglio) == PS1                                           # il doppio clic avvia l'installatore vero
    assert "--headless" in c.LANCIATORE and c.LANCIATORE.endswith("\r\n")        # niente finestra nera; .cmd con CRLF


def test_doppio_clic_dentro_lo_zip_spiega_come_estrarre():
    """B2: dal doppio clic dentro lo zip Windows estrae solo il .cmd in %TEMP%: senza controllo non succedeva nulla."""
    import base64
    sys.path.insert(0, str(RADICE / "installer" / "windows"))
    import costruisci_pacchetto as c
    righe = c.LANCIATORE.split("\r\n")
    controllo = next(i for i, r in enumerate(righe) if r.startswith('if not exist "%~dp0installer\windows\installa_pmn.ps1"'))
    avvio = next(i for i, r in enumerate(righe) if "-File" in r)
    assert controllo < avvio                                                     # prima controlla, poi installa
    codice = righe[controllo].split("-EncodedCommand ")[1].split()[0].rstrip(")")
    testo = base64.b64decode(codice).decode("utf-16-le")
    assert "Estrai tutto" in testo and "Installa profilemetananni" in testo and "TopMost" in testo
    c.LANCIATORE.encode("ascii")                                                 # il .cmd resta ASCII


def test_installazione_lunga_senza_sospensione():
    """B2: col catalogo intero il download dura piu' del tempo dopo cui Windows sospende il PC: l'installatore lo impedisce."""
    stato = ("Add-Type -Namespace Prova -Name Energia -MemberDefinition "
             "'[DllImport(\"powrprof.dll\")] public static extern uint CallNtPowerInformation(int l, System.IntPtr i, uint il, out uint o, uint ol);'; "
             "$o = 0; [void][Prova.Energia]::CallNtPowerInformation(16, [System.IntPtr]::Zero, 0, [ref]$o, 4); $o")
    assert int(powershell(f". '{PS1}'; NienteSospensione; {stato}").strip()) & 0x1    # ES_SYSTEM_REQUIRED attivo
    testo = PS1.read_text(encoding="utf-8")
    assert testo.index("NienteSospensione\n") < testo.index("Riprendi   # se si interrompe")             # chiamata in fase 2
