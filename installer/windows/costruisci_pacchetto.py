# -*- coding: utf-8 -*-
"""B1: costruisce il pacchetto da dare alle persone (uno zip): app impacchettata + motore + installatore.

Uso (dalla cartella del progetto, con l'ambiente dell'app):
    app\\.venv\\Scripts\\python installer\\windows\\costruisci_pacchetto.py
Uscita in build\\pacchetto\\: la cartella profilemetananni\\ e profilemetananni_<commit>.zip con dentro
    Installa profilemetananni.cmd    il doppio clic (avvia installer\\windows\\installa_pmn.ps1)
    app_windows\\ProfileMetaNanni\\   l'app di PyInstaller a cartella (--onedir): ProfileMetaNanni.exe + _internal\\
    installer\\ motore\\ bin\\ steps\\ refs\\   i file del motore, solo quelli in git (prepara_pmn.sh li copia nella WSL)
    VERSIONE.txt                     "profilemetananni 1.1.0" e "commit <commit>" (D168; numero nel file motore/VERSIONE)
Le librerie (PyInstaller, Pillow) sono in installer/windows/requisiti_pacchetto.txt.
"""
import base64
import shutil
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__
from PIL import Image

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE))
from app.aggiorna import VERSIONE   # noqa: E402  (D168: un solo numero, quello che l'app confronta col tag della Release)

BUILD = RADICE / "build"
USCITA = BUILD / "pacchetto"
PACCHETTO = USCITA / "profilemetananni"
MOTORE = ["installer", "motore", "bin", "steps", "refs"]     # come prepara_pmn.sh
ESCLUSI = {"installer/windows/prova.conf"}                   # solo per le prove con lo specchio locale
# B2: col doppio clic dentro lo zip Windows estrae solo il .cmd in %TEMP%: l'installatore manca e prima non succedeva
# nulla. Il messaggio va a PowerShell codificato (UTF-16 in base64), così il .cmd resta ASCII e le lettere accentate restano.
# P12: italiano o inglese come l'installatore (lingua di Windows: it -> italiano, altro -> inglese).
ESTRAI = ("Add-Type -AssemblyName System.Windows.Forms; "
          "$t = if ((Get-UICulture).Name -like 'it*') { \"Il programma è ancora dentro il file zip: da qui non può "
          "installarsi.`n`nFai così:`n1. premi OK;`n2. fai clic destro sul file zip e scegli 'Estrai tutto...', poi "
          "'Estrai';`n3. nella cartella che si apre, fai doppio clic su 'Installa profilemetananni'.\" } "
          "else { \"The program is still inside the zip file: it cannot install from here.`n`nDo this:`n1. press OK;"
          "`n2. right-click the zip file and choose 'Extract All...', then 'Extract';`n3. in the folder that opens, "
          "double-click 'Installa profilemetananni'.\" }; "
          "$o = New-Object Windows.Forms.Form -Property @{ TopMost = $true }; "
          "[void][Windows.Forms.MessageBox]::Show($o, $t, 'profilemetananni', 'OK', 'Information')")
LANCIATORE = ('@echo off\r\n'
              'rem Doppio clic per installare profilemetananni: app, ambiente Linux (WSL) e motore.\r\n'
              'if not exist "%~dp0installer\\windows\\installa_pmn.ps1" (start "" conhost.exe --headless powershell.exe '
              '-NoProfile -EncodedCommand ' + base64.b64encode(ESTRAI.encode("utf-16-le")).decode("ascii") + ' & exit /b 1)\r\n'
              'start "" conhost.exe --headless powershell.exe -NoProfile -ExecutionPolicy Bypass '
              '-File "%~dp0installer\\windows\\installa_pmn.ps1"\r\n')


def git(*arg):
    return subprocess.run(["git", *arg], cwd=RADICE, check=True, capture_output=True, text=True).stdout


def versione_txt(commit):
    """D168: prima riga il numero di versione (lo legge aggiorna_pmn.ps1), seconda il commit come prima."""
    return f"profilemetananni {VERSIONE}\ncommit {commit}\n"


def icona():
    """L'avatar dell'app in formato .ico (tutte le misure che usa Windows)."""
    ico = BUILD / "ProfileMetaNanni.ico"
    ico.parent.mkdir(parents=True, exist_ok=True)
    Image.open(RADICE / "app" / "risorse" / "avatar_512.png").save(
        ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ico


def app(ico):
    """PyInstaller a cartella. Si parte da app.main come modulo, così i percorsi relativi a __file__
    (app/risorse, app/stile.qss, refs/kraken_profili.tsv) valgono uguali dentro _internal\\."""
    avvio = BUILD / "avvia_app.py"
    avvio.write_text("import sys\nfrom app.main import main\nsys.exit(main())\n", encoding="utf-8")
    sep = ";"   # separatore di --add-data su Windows
    PyInstaller.__main__.run([
        str(avvio), "--name", "ProfileMetaNanni", "--onedir", "--windowed", "--noconfirm", "--clean",
        "--icon", str(ico), "--paths", str(RADICE),
        "--distpath", str(BUILD / "dist"), "--workpath", str(BUILD / "pyi"), "--specpath", str(BUILD),
        "--add-data", f"{RADICE / 'app' / 'risorse'}{sep}app/risorse",
        "--add-data", f"{RADICE / 'app' / 'stile.qss'}{sep}app",
        "--add-data", f"{RADICE / 'refs' / 'kraken_profili.tsv'}{sep}refs",
        "--add-data", f"{RADICE / 'motore' / 'VERSIONE'}{sep}motore",       # D168: la versione che legge app/aggiorna.py
        "--exclude-module", "pytest", "--exclude-module", "pytestqt",
    ])
    return BUILD / "dist" / "ProfileMetaNanni"


def main():
    if git("status", "--porcelain", "--", *MOTORE, "app"):
        sys.exit("Ci sono modifiche non salvate in git nei file del pacchetto: prima il commit.")
    commit = git("rev-parse", "--short", "HEAD").strip()
    shutil.rmtree(USCITA, ignore_errors=True)
    PACCHETTO.mkdir(parents=True)
    for rel in git("ls-files", "--", *MOTORE).splitlines():   # solo i file in git: niente prove, log, __pycache__
        if rel not in ESCLUSI:
            (PACCHETTO / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(RADICE / rel, PACCHETTO / rel)
    shutil.copytree(app(icona()), PACCHETTO / "app_windows" / "ProfileMetaNanni")
    (PACCHETTO / "Installa profilemetananni.cmd").write_bytes(LANCIATORE.encode("ascii"))
    (PACCHETTO / "VERSIONE.txt").write_text(versione_txt(commit), encoding="utf-8")
    zip_ = shutil.make_archive(str(USCITA / f"profilemetananni_{commit}"), "zip", USCITA, "profilemetananni")
    print(f"Pacchetto: {zip_} ({Path(zip_).stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
