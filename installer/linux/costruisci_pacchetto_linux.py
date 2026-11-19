# -*- coding: utf-8 -*-
"""P5 (PC con Ubuntu, 12/11): costruisce dal commit corrente i due file per Linux della Release.

Uso (dalla cartella del progetto, su Windows o su Linux: bastano Python e git):
    app\\.venv\\Scripts\\python installer\\linux\\costruisci_pacchetto_linux.py
Uscita in build/pacchetto_linux/:
    profilemetananni_v<versione>_linux.tar.gz   la cartella profilemetananni/ con app bin installer motore refs steps
                                                (quelle che installer/linux/installa_pmn.sh copia), LICENSE,
                                                READ_ME_LEGGIMI.txt e VERSIONE.txt (uguale a quello dello zip di Windows)
    installa_profilemetananni_linux.sh          installer/linux/installa_da_internet.sh con la versione e l'impronta
                                                SHA-256 del pacchetto scritte dentro: e' il file del comando unico
I file vengono dal commit (git archive), non dalla cartella di lavoro: fine riga e permessi sono quelli di git anche
su Windows. Sullo stesso computer lo stesso commit da' gli stessi byte, quindi la stessa impronta.
I due file vanno caricati insieme nella Release: lo script scarica il pacchetto e ne controlla l'impronta.
I nomi NON finiscono per .zip: "Cerca aggiornamenti" (app/aggiorna.py) prende il primo profilemetananni*.zip che trova.
"""
import gzip
import hashlib
import io
import subprocess
import sys
import tarfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
CARTELLE = ["app", "bin", "installer", "motore", "refs", "steps"]     # come installer/linux/installa_pmn.sh
ALTRI = ["LICENSE"]
MODELLO = "installer/linux/installa_da_internet.sh"
SCRIPT = "installa_profilemetananni_linux.sh"                         # nome fisso: releases/latest/download/<nome>
LEGGIMI = """ProfileMetaNanni {v} for Linux (Ubuntu, x86_64)

To install: open a terminal in this folder and run

    bash installer/linux/installa_pmn.sh

The script says what it will download and asks before starting. After the installation this folder is not needed
any more: you can delete it.
Guide: https://github.com/GiampieroFederici/profilemetananni/blob/main/docs/guida_ubuntu_EN.md

----

ProfileMetaNanni {v} per Linux (Ubuntu, x86_64)

Per installare: apri un terminale in questa cartella e lancia

    bash installer/linux/installa_pmn.sh

Lo script dice che cosa scaricherà e chiede prima di partire. Dopo l'installazione questa cartella non serve più:
puoi cancellarla.
Guida: https://github.com/GiampieroFederici/profilemetananni/blob/main/docs/guida_ubuntu_IT.md
"""


def git(radice, *arg):
    # Su Windows git archive mette i fine riga di Windows nei file di testo senza eol=lf in .gitattributes (motore/VERSIONE,
    # i .json, LICENSE): servono tutte e due le impostazioni, con la sola autocrlf=false vale core.eol del sistema (CRLF).
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", *arg], cwd=radice, check=True,
                          capture_output=True).stdout


def nome_pacchetto(versione):
    return f"profilemetananni_v{versione}_linux.tar.gz"


def versione_txt(versione, commit):
    """Come installer/windows/costruisci_pacchetto.py: prima riga la versione, seconda il commit."""
    return f"profilemetananni {versione}\ncommit {commit}\n"


def script_da_internet(modello, versione, sha256):
    """Il modello con la versione e l'impronta del pacchetto al posto dei due segnaposto (uno per ciascuno)."""
    for segnaposto in ("@VERSIONE@", "@SHA256@"):
        if modello.count(segnaposto) != 1:
            sys.exit(f"{MODELLO}: il segnaposto {segnaposto} deve comparire una volta sola.")
    return modello.replace("@VERSIONE@", versione).replace("@SHA256@", sha256)


def costruisci(radice=RADICE, uscita=None):
    """Scrive i due file in uscita (predefinita build/pacchetto_linux) e torna (pacchetto, script)."""
    radice = Path(radice)
    uscita = Path(uscita) if uscita else radice / "build" / "pacchetto_linux"
    if git(radice, "status", "--porcelain", "--", *CARTELLE, *ALTRI):
        sys.exit("Ci sono modifiche non salvate in git nei file del pacchetto: prima il commit.")
    versione = git(radice, "show", "HEAD:motore/VERSIONE").decode("utf-8").strip()
    commit = git(radice, "rev-parse", "--short", "HEAD").decode("ascii").strip()
    quando = int(git(radice, "log", "-1", "--format=%ct", "HEAD"))
    modello = None
    tar_gz = io.BytesIO()
    # mtime=0 nel gzip e data del commit nei file: lo stesso commit da' lo stesso pacchetto
    with gzip.GzipFile(filename="", mode="wb", fileobj=tar_gz, mtime=0) as gz, \
            tarfile.open(fileobj=gz, mode="w") as nuovo, \
            tarfile.open(fileobj=io.BytesIO(git(radice, "archive", "--format=tar", "HEAD", "--", *CARTELLE, *ALTRI))) as da_git:

        def aggiungi(nome, dati, modo=0o644):
            t = tarfile.TarInfo("profilemetananni/" + nome)
            t.size, t.mode, t.mtime = len(dati), modo, quando
            nuovo.addfile(t, io.BytesIO(dati))

        for m in da_git:
            if not m.isfile():
                continue
            dati = da_git.extractfile(m).read()
            if m.name == MODELLO:
                modello = dati.decode("utf-8")
            aggiungi(m.name, dati, 0o755 if m.mode & 0o100 else 0o644)
        aggiungi("READ_ME_LEGGIMI.txt", LEGGIMI.format(v=versione).encode("utf-8"))
        aggiungi("VERSIONE.txt", versione_txt(versione, commit).encode("utf-8"))
    if modello is None:
        sys.exit(f"Nel commit manca {MODELLO}.")
    uscita.mkdir(parents=True, exist_ok=True)
    pacchetto = uscita / nome_pacchetto(versione)
    pacchetto.write_bytes(tar_gz.getvalue())
    script = uscita / SCRIPT
    script.write_bytes(script_da_internet(modello, versione, hashlib.sha256(tar_gz.getvalue()).hexdigest()).encode("utf-8"))
    return pacchetto, script


if __name__ == "__main__":
    for f in costruisci():
        print(f"{f} ({f.stat().st_size} byte, SHA-256 {hashlib.sha256(f.read_bytes()).hexdigest()})")
