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
