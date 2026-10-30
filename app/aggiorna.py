"""Aggiornamento dell'app dalla Release "latest" di GitHub (R12, D168).

VERSIONE è il numero di questa versione: costruisci_pacchetto.py lo scrive anche in VERSIONE.txt dello zip.
  controlla()   legge la Release latest (solo HTTPS, nessun token, timeout breve) e confronta il tag vX.Y.Z
  scarica()     scarica lo zip della Release controllando byte e SHA-256 (campo `digest` dell'API di GitHub)
  estrai()      estrae lo zip in una cartella di lavoro, senza uscire da quella cartella
  avvia_script() lancia installer/windows/aggiorna_pmn.ps1 (del pacchetto nuovo, o la sua copia per il ripristino),
                che aspetta la chiusura dell'app, sostituisce app e motore e, se qualcosa va storto, rimette i vecchi.
Nessun dato dell'utente passa da qui: Documenti\\ProfileMetaNanni, impostazioni e ospiti aggiunti non si toccano.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from app.lingua import _

VERSIONE = "1.1.0"
URL_ULTIMA = "https://api.github.com/repos/GiampieroFederici/profilemetananni/releases/latest"
TIMEOUT = 10                       # secondi: il controllo non deve bloccare a lungo
MAX_NOVITA = 1200                  # caratteri delle novità mostrati
MAX_BYTE = 2_000_000_000           # uno zip più grande non è il nostro pacchetto (la 1.0.0 pesa 50 MB)
LOCALI = {"127.0.0.1", "localhost", "::1"}   # http solo verso questo computer (prove con una Release finta)
PS1 = ("installer", "windows", "aggiorna_pmn.ps1")
APP_EXE = ("app_windows", "ProfileMetaNanni", "ProfileMetaNanni.exe")


class ErroreAggiorna(Exception):
    """codice: RETE, LIMITE, RISPOSTA, INDIRIZZO, PACCHETTO_DIVERSO, INCOMPATIBILE, SPAZIO, DISCO, ANNULLATO."""
    def __init__(self, codice, messaggio, cosa_fare=""):
        super().__init__(messaggio)
        self.codice, self.messaggio, self.cosa_fare = codice, messaggio, cosa_fare


def versione(testo):
    """'v1.2.3' o '1.2.3' -> (1, 2, 3); ValueError se il testo non è così."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(testo).strip())
    if not m:
        raise ValueError(f"Versione non valida: {testo!r}")
    return tuple(int(x) for x in m.groups())


def sicuro(url):
    """Solo HTTPS; http solo verso questo computer."""
    p = urlsplit(url)
    if not (p.scheme == "https" or (p.scheme == "http" and p.hostname in LOCALI)):
        raise ErroreAggiorna("INDIRIZZO", _("Indirizzo non sicuro per l'aggiornamento."),
                             _("Scarica la versione nuova dalla pagina della Release su GitHub."))
    return url


class _SoloSicuri(urllib.request.HTTPRedirectHandler):
    """Anche i rinvii (GitHub manda lo zip a un altro server) devono restare HTTPS."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        sicuro(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _apri(url, timeout):
    richiesta = urllib.request.Request(sicuro(url), headers={
        "Accept": "application/vnd.github+json", "User-Agent": f"ProfileMetaNanni/{VERSIONE}"})
    try:
        return urllib.request.build_opener(_SoloSicuri).open(richiesta, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 429 or (e.code == 403 and e.headers.get("X-RateLimit-Remaining") == "0"):
            try:
                ora = datetime.fromtimestamp(int(e.headers.get("X-RateLimit-Reset"))).strftime("%H:%M")
            except (TypeError, ValueError, OSError):
                ora = None
            raise ErroreAggiorna("LIMITE", _("GitHub accetta pochi controlli all'ora da questa rete e il limite è "
                                             "raggiunto."),
                                 _("Riprova dopo le {ora}.", ora=ora) if ora else _("Riprova fra un'ora."))
        raise ErroreAggiorna("RISPOSTA", _("GitHub ha risposto con un errore (codice {codice}).", codice=e.code),
                             _("Riprova più tardi."))
    except (urllib.error.URLError, OSError) as e:
        if isinstance(getattr(e, "reason", None), ErroreAggiorna):
            raise e.reason
        raise ErroreAggiorna("RETE", _("Non riesco a raggiungere GitHub."),
                             _("Controlla la connessione a internet e riprova."))


def testo_semplice(corpo, massimo=MAX_NOVITA):
    """Il corpo della Release (Markdown) come testo semplice e corto: niente HTML, niente link attivi."""
    t = re.sub(r"<[^>]*>", "", str(corpo or ""))
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)                 # immagini
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)             # link: resta il testo
    t = re.sub(r"^[ \t]{0,3}#+[ \t]*", "", t, flags=re.M)      # titoli
    t = re.sub(r"[*_`]{1,3}([^*_`\n]+)[*_`]{1,3}", r"\1", t)   # grassetto, corsivo, codice
    t = re.sub(r"[^\S\n]+", " ", re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", t.replace("\r", "")))
    t = re.sub(r"\n\s*\n\s*(\n\s*)+", "\n\n", t).strip()
    if len(t) > massimo:
        t = t[:massimo].rsplit(" ", 1)[0].rstrip() + " ..."
    return t


def _pacchetto(release):
    """Il primo asset zip di profilemetananni con nome, indirizzo, byte e SHA-256 (se GitHub lo dà); None se manca."""
    for a in release.get("assets") or []:
        if not isinstance(a, dict):
            continue
        nome, url, byte = a.get("name"), a.get("browser_download_url"), a.get("size")
        if not (isinstance(nome, str) and re.fullmatch(r"profilemetananni[\w.-]*\.zip", nome, re.I)
                and isinstance(url, str) and isinstance(byte, int) and 0 < byte <= MAX_BYTE):
            continue
        digest = a.get("digest")
        m = re.fullmatch(r"sha256:([0-9a-f]{64})", digest.lower()) if isinstance(digest, str) else None
        return {"nome": nome, "url": sicuro(url), "byte": byte, "sha256": m.group(1) if m else None}
    return None


def controlla(url=URL_ULTIMA, installata=VERSIONE, timeout=TIMEOUT):
    """{"stato": "nuova" | "uguale" | "vecchia", "installata", "nuova", "novita", "pacchetto" (o None), "pagina"}."""
    with _apri(url, timeout) as r:
        grezzo = r.read(2_000_000)
    try:
        d = json.loads(grezzo.decode("utf-8"))
        nuova = versione(d["tag_name"])
    except (UnicodeDecodeError, ValueError, KeyError, TypeError):
        raise ErroreAggiorna("RISPOSTA", _("La risposta di GitHub non è quella attesa."), _("Riprova più tardi."))
    attuale = versione(installata)
    stato = "nuova" if nuova > attuale else "uguale" if nuova == attuale else "vecchia"
    pagina = d.get("html_url") if isinstance(d.get("html_url"), str) else ""
    return {"stato": stato, "installata": installata, "nuova": "%d.%d.%d" % nuova,
            "novita": testo_semplice(d.get("body")), "pacchetto": _pacchetto(d) if stato == "nuova" else None,
            "pagina": pagina if pagina.startswith("https://") else ""}


def scarica(pacchetto, cartella, avanzamento=None, fermo=None, timeout=TIMEOUT):
    """Scarica lo zip in cartella; byte e SHA-256 devono tornare. avanzamento(fatti, totali); fermo() True = annulla."""
    cartella = Path(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
    dest = cartella / pacchetto["nome"]
    h, fatti = hashlib.sha256(), 0
    diverso = ErroreAggiorna("PACCHETTO_DIVERSO", _("Il file scaricato non è quello pubblicato."),
                             _("Riprova: se succede ancora, scarica la versione nuova dalla pagina della Release."))
    try:
        with _apri(pacchetto["url"], timeout) as r, open(dest, "wb") as f:
            while blocco := r.read(1 << 20):
                fatti += len(blocco)
                if fatti > pacchetto["byte"]:
                    raise diverso
                h.update(blocco)
                f.write(blocco)
                if avanzamento:
                    avanzamento(fatti, pacchetto["byte"])
                if fermo and fermo():
                    raise ErroreAggiorna("ANNULLATO", _("Aggiornamento annullato: non ho cambiato nulla."))
        if fatti != pacchetto["byte"] or (pacchetto["sha256"] and h.hexdigest() != pacchetto["sha256"]):
            raise diverso
    except ErroreAggiorna:
        dest.unlink(missing_ok=True)
        raise
    except OSError:
        dest.unlink(missing_ok=True)
        raise ErroreAggiorna("RETE", _("Lo scaricamento si è interrotto."),
                             _("Controlla la connessione a internet e riprova."))
    return dest


def estrai(zip_, cartella):
    """Estrae lo zip in cartella (accanto allo zip) e torna la radice profilemetananni/ (con lo script e l'app nuova).
    Percorso corto apposta: il file più profondo dello zip ha già 121 caratteri e Windows si ferma a 260."""
    dentro = Path(cartella)
    shutil.rmtree(dentro / "profilemetananni", ignore_errors=True)
    dentro.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_) as z:
            membri = z.infolist()
            for m in membri:                       # niente file fuori dalla cartella (../, percorsi assoluti)
                if not (dentro / m.filename).resolve().is_relative_to(dentro.resolve()):
                    raise ErroreAggiorna("PACCHETTO_DIVERSO", _("Il file scaricato non è quello pubblicato."))
            if 2 * sum(m.file_size for m in membri) > shutil.disk_usage(dentro).free:   # estratto + copia dell'app
                raise ErroreAggiorna("SPAZIO", _("Non c'è abbastanza spazio sul disco per l'aggiornamento."),
                                     _("Libera almeno {gb} GB e riprova.",
                                       gb=max(1, round(2 * sum(m.file_size for m in membri) / 1e9))))
            z.extractall(dentro)
    except zipfile.BadZipFile:
        raise ErroreAggiorna("PACCHETTO_DIVERSO", _("Il file scaricato non è quello pubblicato."))
    except OSError:                            # disco pieno, percorso troppo lungo, file bloccato
        raise ErroreAggiorna("DISCO", _("Non riesco a preparare la versione nuova sul disco."),
                             _("Scaricala dalla pagina della Release e installala con il doppio clic."))
    radice = dentro / "profilemetananni"
    if not (radice.joinpath(*PS1).is_file() and radice.joinpath(*APP_EXE).is_file()):
        raise ErroreAggiorna("INCOMPATIBILE", _("Questa versione non si installa dal pulsante Aggiorna."),
                             _("Scaricala dalla pagina della Release e installala con il doppio clic."))
    return radice


# ---------------- installazione sul computer ----------------
def cartella_installata():
    """Dove l'installatore mette l'app (installer/windows/installa_pmn.ps1): %LOCALAPPDATA%\\profilemetananni."""
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "profilemetananni"


def cartella_lavoro():
    return cartella_installata() / "aggiornamento"


def puo_installare():
    """Solo l'app installata (PyInstaller) su Windows si sostituisce da sola; da una copia di sviluppo si controlla."""
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def precedente():
    """Lo script di ripristino se c'è una versione precedente da rimettere, altrimenti None."""
    c = cartella_installata()
    script = c / PS1[-1]
    return script if (c / "app.precedente" / APP_EXE[-1]).is_file() and script.is_file() else None


def avvia_script(script, ripristina=False):
    """Lancia aggiorna_pmn.ps1 senza finestre nere; aspetta che questa app si chiuda (-Attendi) prima di toccarla."""
    comando = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
               "-Attendi", str(os.getpid())] + (["-Ripristina"] if ripristina else [])
    subprocess.Popen(comando, cwd=str(cartella_installata()), close_fds=True,
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP)
