# -*- coding: utf-8 -*-
"""P5 (PC con Ubuntu, 12/11): il pacchetto per Linux della Release e l'installazione con un solo comando.
  installer/linux/costruisci_pacchetto_linux.py   costruisce il pacchetto dal commit e lo script con l'impronta dentro
  installer/linux/installa_da_internet.sh         il modello dello script: scarica, controlla, estrae, lancia
Niente di vero si scarica o si installa: una Release finta in una cartella, un finto curl (o wget) che copia da lì, un
finto installa_pmn.sh che scrive che cosa ha ricevuto.
Su Windows gli script girano con il bash di Git, mai con "bash" da solo (sarebbe quello della WSL); i due test che
vogliono un terminale vero o nessun terminale girano solo su Linux.
  app\\.venv\\Scripts\\python -m pytest tests/test_pacchetto_linux.py -q -p no:cacheprovider"""
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
sys.path.insert(0, str(RADICE / "installer" / "linux"))
import costruisci_pacchetto_linux as c  # noqa: E402

MODELLO = RADICE / "installer" / "linux" / "installa_da_internet.sh"
VERSIONE = "9.8.7"
NOME = f"profilemetananni_v{VERSIONE}_linux.tar.gz"
INDIRIZZO = f"https://github.com/GiampieroFederici/profilemetananni/releases/download/v{VERSIONE}/{NOME}"


# ---------------- nomi, versione, testi: senza bash e senza git ----------------
def test_cerca_aggiornamenti_non_scambia_i_file_di_linux_per_lo_zip_di_windows():
    """MANUTENZIONE 4.3: l'app prende il primo profilemetananni*.zip della Release. I due file nuovi non sono zip."""
    from app import aggiorna
    assert c.nome_pacchetto("1.3.0") == "profilemetananni_v1.3.0_linux.tar.gz"
    assert not c.nome_pacchetto("1.3.0").endswith(".zip") and not c.SCRIPT.endswith(".zip")

    def asset(nome):
        return {"name": nome, "browser_download_url": "https://github.com/x/" + nome, "size": 1000}
    linux = [asset(c.nome_pacchetto("1.3.0")), asset(c.SCRIPT)]
    assert aggiorna._pacchetto({"assets": linux}) is None
    for ordine in (linux + [asset("profilemetananni_v1.3.0.zip")], [asset("profilemetananni_v1.3.0.zip")] + linux):
        assert aggiorna._pacchetto({"assets": ordine})["nome"] == "profilemetananni_v1.3.0.zip"


def test_versione_txt_come_nello_zip_di_windows():
    pytest.importorskip("PyInstaller")
    pytest.importorskip("PIL")
    sys.path.insert(0, str(RADICE / "installer" / "windows"))
    import costruisci_pacchetto
    assert c.versione_txt(costruisci_pacchetto.VERSIONE, "abc1234") == costruisci_pacchetto.versione_txt("abc1234")
    assert c.CARTELLE == ["app"] + sorted(costruisci_pacchetto.MOTORE)          # il motore dello zip, più l'app
    copiate = re.search(r"-cf - ([a-z ]+) \| tar", (RADICE / "installer" / "linux" / "installa_pmn.sh")
                        .read_text(encoding="utf-8")).group(1).split()
    assert c.CARTELLE == copiate                                                # ciò che installa_pmn.sh copia


def test_script_controlli_statici():
    """Ciò che si controlla leggendo: fine riga LF, modo severo, un solo indirizzo (HTTPS, GitHub, questo progetto),
    sudo mai eseguito (solo nel messaggio), niente eval, niente passato a una shell, tutto dentro principale()."""
    dati = MODELLO.read_bytes()
    testo = dati.decode("utf-8")
    assert dati.startswith(b"#!/usr/bin/env bash\n") and b"\r" not in dati
    assert "\nset -euo pipefail\n" in testo and testo.rstrip("\n").endswith('\nprincipale "$@"')
    assert testo.count("@VERSIONE@") == 1 and testo.count("@SHA256@") == 1
    codice = "\n".join(r for r in testo.splitlines() if not r.lstrip().startswith("#"))
    assert re.findall(r"\w+://[^\s\"']+", codice) == [
        "https://github.com/GiampieroFederici/profilemetananni/releases/download/v$VERSIONE/$nome"]
    assert not re.search(r"\beval\b|\|\s*(ba)?sh\b", codice)
    assert not re.search(r"(^|[;&|(]|\bthen|\bdo|\belse)\s*sudo\b", codice, re.M)
    assert "--proto '=https' --proto-redir '=https'" in codice                  # curl: nessun rinvio fuori da HTTPS
    assert codice.index("sha256sum") < codice.index("tar -xzf")                 # prima l'impronta, poi si apre
    assert "\u2014" not in testo


def test_messaggi_dello_script_in_italiano_e_in_inglese():
    """Ogni frase per la persona ha la traduzione nella tabella EN, con gli stessi %s (come installa_motore.sh)."""
    testo = MODELLO.read_text(encoding="utf-8")
    tabella = dict(re.findall(r'^  \["(.*)"\]="(.*)"$', testo, re.M))
    usate = set(re.findall(r"(?:dice|fallisci) '([^']*)'", testo)) | set(re.findall(r'(?:dice|fallisci) "([^"]*)"', testo))
    assert len(usate) == 8 and sorted(usate - set(tabella)) == []
    for it in usate:
        assert it.count("%s") == tabella[it].count("%s"), it
        assert "\u2014" not in tabella[it]


# ---------------- il pacchetto dal commit ----------------
def git(cartella, *arg):
    subprocess.run(["git", "-c", "user.name=prova", "-c", "user.email=prova@example.invalid", "-c", "commit.gpgsign=false",
                    "-c", "core.autocrlf=true", *arg], cwd=cartella, check=True, capture_output=True)


BINARIO = b"\x89PNG\r\n\x1a\n\x00a\nb\r\nc\x00"          # un file binario ha i suoi \r\n: deve restare com'è


@pytest.fixture
def progetto(tmp_path):
    """Un progetto piccolo in un deposito git suo, con le cartelle del pacchetto e qualcosa che non ci deve entrare."""
    if not shutil.which("git"):
        pytest.skip("serve git")
    p = tmp_path / "progetto"
    file = {"motore/VERSIONE": VERSIONE + "\n", "motore/pmn-motore": "#!/usr/bin/env bash\n", "app/main.py": "x = 1\n",
            "app/risorse/lingua_en.json": "{}\n", "bin/run.sh": "#!/usr/bin/env bash\n", "refs/a.tsv": "a\tb\n",
            "steps/01.sh": "#!/usr/bin/env bash\n", "installer/linux/installa_pmn.sh": "#!/usr/bin/env bash\n",
            "installer/windows/installa_pmn.cmd": "@echo off\n", "LICENSE": "MIT\n",
            "docs/guida.md": "fuori dal pacchetto\n", "tests/test_x.py": "fuori dal pacchetto\n", "README.md": "fuori\n",
            ".gitattributes": (RADICE / ".gitattributes").read_text(encoding="utf-8")}
    for nome, testo in file.items():
        (p / nome).parent.mkdir(parents=True, exist_ok=True)
        (p / nome).write_bytes(testo.encode("utf-8"))
    (p / "app" / "risorse" / "avatar.png").write_bytes(BINARIO)
    (p / "motore" / "pmn-motore").chmod(0o755)   # su Linux git guarda i permessi: come --chmod=+x qui sotto
    shutil.copyfile(MODELLO, p / "installer" / "linux" / MODELLO.name)   # senza i permessi del disco di Windows
    git(p, "init", "-q")
    git(p, "add", "-A")
    git(p, "update-index", "--chmod=+x", "motore/pmn-motore")
    git(p, "commit", "-q", "-m", "prova")
    return p


def test_pacchetto_dal_commit(progetto, tmp_path):
    pacchetto, script = c.costruisci(progetto, tmp_path / "uscita")
    assert pacchetto.name == NOME and script.name == "installa_profilemetananni_linux.sh"
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=progetto, capture_output=True, text=True).stdout.strip()
    with tarfile.open(pacchetto) as t:
        membri = {m.name: m for m in t.getmembers()}
        dentro = {n: t.extractfile(m).read() for n, m in membri.items()}
    assert sorted(membri) == sorted("profilemetananni/" + n for n in (
        "LICENSE", "READ_ME_LEGGIMI.txt", "VERSIONE.txt", "app/main.py", "app/risorse/avatar.png",
        "app/risorse/lingua_en.json", "bin/run.sh",
        "installer/linux/installa_da_internet.sh", "installer/linux/installa_pmn.sh", "installer/windows/installa_pmn.cmd",
        "motore/VERSIONE", "motore/pmn-motore", "refs/a.tsv", "steps/01.sh"))                # niente docs, tests, README
    assert dentro["profilemetananni/VERSIONE.txt"] == f"profilemetananni {VERSIONE}\ncommit {commit}\n".encode()
    # fine riga di Linux in tutti i file di testo, anche se il progetto è su Windows; i binari restano identici
    assert dentro.pop("profilemetananni/app/risorse/avatar.png") == BINARIO
    assert [n for n, d in dentro.items() if b"\r" in d] == []
    assert {m.mode for n, m in membri.items() if not n.endswith("pmn-motore")} == {0o644}
    assert membri["profilemetananni/motore/pmn-motore"].mode == 0o755                       # i permessi sono quelli di git
    leggimi = dentro["profilemetananni/READ_ME_LEGGIMI.txt"].decode("utf-8")
    assert leggimi.count("bash installer/linux/installa_pmn.sh") == 2 and VERSIONE in leggimi and "\u2014" not in leggimi
    assert leggimi.index("To install") < leggimi.index("Per installare")                    # prima inglese, poi italiano
    # lo script: il modello con la versione e l'impronta di QUESTO pacchetto, senza segnaposto
    testo = script.read_bytes()
    impronta = hashlib.sha256(pacchetto.read_bytes()).hexdigest()
    assert f"\nVERSIONE={VERSIONE}\nSHA256={impronta}\n".encode() in testo
    assert b"@VERSIONE@" not in testo and b"@SHA256@" not in testo and b"\r" not in testo
    # lo stesso commit dà gli stessi byte
    prima = pacchetto.read_bytes(), testo
    c.costruisci(progetto, tmp_path / "uscita")
    assert (pacchetto.read_bytes(), script.read_bytes()) == prima


def test_modifiche_non_salvate_niente_pacchetto(progetto, tmp_path):
    (progetto / "app" / "main.py").write_bytes(b"x = 2\n")
    with pytest.raises(SystemExit, match="prima il commit"):
        c.costruisci(progetto, tmp_path / "uscita")
    assert not (tmp_path / "uscita").exists()


# ---------------- lo script: scarica, controlla, estrae, lancia ----------------
def trova_bash():
    """(bash, cartella degli strumenti di sistema). Su Windows solo il bash di Git, cercato accanto a git."""
    if sys.platform == "linux":
        return shutil.which("bash"), None
    git_exe = shutil.which("git")
    for su in (Path(git_exe).resolve().parents if git_exe else ()):
        if (su / "usr" / "bin" / "bash.exe").is_file():
            return str(su / "usr" / "bin" / "bash.exe"), su / "usr" / "bin"
    return None, None


BASH, STRUMENTI_GIT = trova_bash()
con_bash = pytest.mark.skipif(not BASH, reason="serve bash: su Linux quello del sistema, su Windows quello di Git "
                                               "(mai 'bash' da solo, che su Windows è la WSL)")
solo_linux = pytest.mark.skipif(sys.platform != "linux", reason="serve Linux: un terminale finto (pty) e una sessione "
                                                                "senza terminale non si fanno su Windows")
# installa_pmn.sh finto: scrive gli argomenti, se l'ingresso è un terminale e, se non c'è --si, la risposta che legge
INSTALLATORE = r'''#!/usr/bin/env bash
printf '%s\n' "$@" > "$PMN_PROVA/argomenti"
if [ -t 0 ]; then echo terminale > "$PMN_PROVA/ingresso"; else echo altro > "$PMN_PROVA/ingresso"; fi
case " $* " in *" --si "* | *" --stima "*) ;; *) read -r r || r=FINE; printf '%s\n' "$r" > "$PMN_PROVA/risposta" ;; esac
pwd > "$PMN_PROVA/cartella"; dirname "$0" >> "$PMN_PROVA/cartella"
exit "${PMN_PROVA_ESITO:-0}"
'''
# curl o wget finto: l'ultimo argomento è l'indirizzo, dopo -o (curl) o -O (wget) c'è il file; copia dalla Release finta
SCARICATORE = r'''#!/usr/bin/env bash
printf '%s %s\n' "${0##*/}" "${!#}" >> "$PMN_PROVA/scaricati"
while [ $# -gt 1 ]; do
  if [ "$1" = -o ] || [ "$1" = -O ]; then dove=$2; fi
  shift
done
[ -f "$PMN_FINTA_RELEASE/${1##*/}" ] || exit 22
cp "$PMN_FINTA_RELEASE/${1##*/}" "$dove"
'''


def per_bash(p):
    """Un percorso come lo vuole bash: su Windows /c/Users/... (tar prende C: per il nome di un altro computer)."""
    p = Path(p).resolve()
    return str(p) if sys.platform == "linux" else "/" + p.drive[0].lower() + p.as_posix()[2:]


class Rilascio:
    """La Release finta, lo script generato dal modello e l'ambiente per lanciarlo."""

    def __init__(self, tmp, scaricatori=("curl",), impronta=None):
        self.prova, self.tmp, release, finti = tmp / "prova", tmp / "tmp", tmp / "release", tmp / "finti"
        for d in (self.prova, self.tmp, release, finti):
            d.mkdir()
        dati = io.BytesIO()
        with tarfile.open(fileobj=dati, mode="w:gz") as t:
            m = tarfile.TarInfo("profilemetananni/installer/linux/installa_pmn.sh")
            m.size = len(INSTALLATORE.encode())
            t.addfile(m, io.BytesIO(INSTALLATORE.encode()))
        (release / NOME).write_bytes(dati.getvalue())
        self.script = tmp / c.SCRIPT
        self.script.write_bytes(c.script_da_internet(MODELLO.read_text(encoding="utf-8"), VERSIONE,
                                                     impronta or hashlib.sha256(dati.getvalue()).hexdigest()).encode())
        for nome in scaricatori:
            (finti / nome).write_bytes(SCARICATORE.encode())
            (finti / nome).chmod(0o755)
        if STRUMENTI_GIT:
            strumenti = STRUMENTI_GIT                    # usr/bin di Git: ha tar, sha256sum, mktemp; non ha curl né wget
        else:                                            # Linux: solo gli strumenti che servono, così curl e wget veri non si vedono
            strumenti = tmp / "strumenti"
            strumenti.mkdir()
            for nome in ("bash", "tar", "gzip", "sha256sum", "mktemp", "rm", "id", "cp", "dirname"):
                (strumenti / nome).symlink_to(shutil.which(nome))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("LC_")}
        self.env.update(PATH=os.pathsep.join([str(finti), str(strumenti)]), LANG="it_IT.UTF-8", TMPDIR=per_bash(self.tmp),
                        PMN_PROVA=per_bash(self.prova), PMN_FINTA_RELEASE=per_bash(release))

    def lancia(self, *arg, dalla_pipe=False, **env):
        """bash script argomenti; con dalla_pipe lo script arriva dall'ingresso, come con "wget ... | bash -s -- argomenti"."""
        comando = [BASH, "-s", "--", *arg] if dalla_pipe else [BASH, str(self.script), *arg]
        with open(self.script if dalla_pipe else os.devnull, "rb") as ingresso:
            return subprocess.run(comando, stdin=ingresso, capture_output=True, text=True, encoding="utf-8", timeout=120,
                                  env=dict(self.env, **env), start_new_session=sys.platform == "linux")

    def letto(self, nome):
        f = self.prova / nome
        return f.read_text(encoding="utf-8").split("\n")[:-1] if f.exists() else None


@con_bash
@pytest.mark.parametrize("dalla_pipe", [False, True], ids=["dal_file", "dalla_pipe"])
def test_scarica_controlla_estrae_e_lancia(tmp_path, dalla_pipe):
    r = Rilascio(tmp_path)
    p = r.lancia("--si", "--connessioni", "4", dalla_pipe=dalla_pipe)
    assert p.returncode == 0, p.stdout + p.stderr
    assert r.letto("scaricati") == ["curl " + INDIRIZZO]                           # un solo scarico, dalla Release di GitHub
    assert r.letto("argomenti") == ["--si", "--connessioni", "4"]                  # gli argomenti arrivano all'installatore
    assert r.letto("cartella")[1].endswith("/profilemetananni/installer/linux")    # lanciato dalla cartella estratta
    assert list(r.tmp.iterdir()) == []                                             # la cartella temporanea è sparita
    assert p.stdout.splitlines() == [f"[PMN] Scarico ProfileMetaNanni {VERSIONE} per Linux...",
                                     "[PMN] Ho già cancellato io quella cartella temporanea: non devi fare altro."]
    assert p.stderr == ""


@con_bash
def test_con_wget_se_curl_manca(tmp_path):
    """Su Ubuntu desktop curl può mancare e wget c'è."""
    r = Rilascio(tmp_path, scaricatori=("wget",))
    p = r.lancia("--si")
    assert p.returncode == 0, p.stdout + p.stderr
    assert r.letto("scaricati") == ["wget " + INDIRIZZO] and r.letto("argomenti") == ["--si"]


@con_bash
def test_senza_curl_e_senza_wget_dice_la_riga_da_lanciare(tmp_path):
    r = Rilascio(tmp_path, scaricatori=())
    p = r.lancia("--si")
    assert p.returncode == 1 and r.letto("argomenti") is None
    assert p.stdout.splitlines() == ["[PMN] Per scaricare il programma serve curl oppure wget. Lancia questa riga, poi "
                                     "di nuovo lo stesso comando:", "    sudo apt install curl"]
    assert list(r.tmp.iterdir()) == []


@con_bash
def test_impronta_diversa_non_apre_e_non_lancia(tmp_path):
    """Il file scaricato non è quello pubblicato: non si estrae nulla e l'installatore non parte."""
    r = Rilascio(tmp_path, impronta="0" * 64)
    p = r.lancia("--si", LANG="en_US.UTF-8")
    assert p.returncode == 1 and r.letto("argomenti") is None
    assert r.letto("scaricati") == ["curl " + INDIRIZZO] and list(r.tmp.iterdir()) == []
    assert p.stderr.startswith("[PMN] ERROR: The downloaded file is not the published one (different SHA-256 checksum): "
                               "I did not open it.")
    assert p.stdout == f"[PMN] Downloading ProfileMetaNanni {VERSIONE} for Linux...\n"


@con_bash
def test_scarico_fallito(tmp_path):
    r = Rilascio(tmp_path)
    (tmp_path / "release" / NOME).unlink()
    p = r.lancia("--si")
    assert p.returncode == 1 and r.letto("argomenti") is None and list(r.tmp.iterdir()) == []
    assert p.stderr == ("[PMN] ERRORE: Non riesco a scaricare il programma da GitHub. Controlla la connessione e rilancia "
                        "lo stesso comando.\n")


@con_bash
@pytest.mark.parametrize("arg, esito, ultima", [
    (["--si"], "3", "Scarico"),          # interrotta o annullata: il codice torna indietro, nessuna frase in più
    (["--si"], "2", "Scarico"),
    (["--stima"], "0", "Scarico"),       # solo la stima: niente è stato installato, niente frase sulla cartella
])
def test_il_codice_dell_installatore_torna_indietro(tmp_path, arg, esito, ultima):
    r = Rilascio(tmp_path)
    p = r.lancia(*arg, PMN_PROVA_ESITO=esito)
    assert p.returncode == int(esito) and r.letto("argomenti") == arg
    assert p.stdout.splitlines()[-1].startswith("[PMN] " + ultima) and list(r.tmp.iterdir()) == []


@con_bash
def test_il_modello_senza_versione_non_scarica_nulla(tmp_path):
    """Il file del progetto è il modello: lanciato così com'è lo dice e si ferma."""
    r = Rilascio(tmp_path)
    r.script.write_bytes(MODELLO.read_bytes())
    p = r.lancia("--si")
    assert p.returncode == 1 and r.letto("scaricati") is None
    assert "installa_profilemetananni_linux.sh" in p.stderr and p.stderr.startswith("[PMN] ERRORE: Questo file è il modello")


@con_bash
@solo_linux
def test_dalla_pipe_la_risposta_si_legge_dal_terminale(tmp_path):
    """Con "wget ... | bash" l'ingresso dello script è la pipe: la risposta alla domanda dell'installatore deve venire
    dalla tastiera. Qui la tastiera è un terminale finto (pty), terminale di controllo di una sessione nuova."""
    import fcntl
    import pty
    import termios
    r = Rilascio(tmp_path)
    padrone, schiavo = pty.openpty()

    def con_il_terminale():
        os.setsid()
        fcntl.ioctl(schiavo, termios.TIOCSCTTY, 0)
    try:
        with open(r.script, "rb") as ingresso:
            p = subprocess.Popen([BASH], stdin=ingresso, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=r.env,
                                 preexec_fn=con_il_terminale)
        os.write(padrone, b"s\n")
        uscita, errori = p.communicate(timeout=120)
    finally:
        os.close(padrone)
        os.close(schiavo)
    assert p.returncode == 0, uscita.decode() + errori.decode()
    assert r.letto("ingresso") == ["terminale"] and r.letto("risposta") == ["s"] and r.letto("argomenti") == [""]


@con_bash
@solo_linux
def test_senza_terminale_e_senza_si_si_ferma_prima_di_scaricare(tmp_path):
    """Nessuno può rispondere alla domanda: lo dice subito, prima di scaricare. Con --si invece parte."""
    r = Rilascio(tmp_path)
    p = r.lancia(dalla_pipe=True)                      # sessione nuova, senza terminale di controllo
    assert p.returncode == 1 and r.letto("scaricati") is None and r.letto("argomenti") is None
    assert "non c'è un terminale per rispondere" in p.stderr and "--si" in p.stderr
    p = r.lancia("--si", dalla_pipe=True)
    assert p.returncode == 0 and r.letto("ingresso") == ["altro"] and r.letto("risposta") is None
