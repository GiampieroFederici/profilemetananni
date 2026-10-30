"""Aggiornamento dell'app dalla Release "latest" di GitHub (R12, D168).

VERSIONE è il numero di questa versione (file motore/VERSIONE): costruisci_pacchetto.py lo scrive anche in VERSIONE.txt dello zip.
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
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from app.lingua import _

# D168, B2-2a: un solo numero per app, motore e zip, nel file motore/VERSIONE (nell'app impacchettata è in _internal)
VERSIONE = (Path(__file__).resolve().parent.parent / "motore" / "VERSIONE").read_text(encoding="utf-8").strip()
URL_ULTIMA = "https://api.github.com/repos/GiampieroFederici/profilemetananni/releases/latest"
TIMEOUT = 10                       # secondi: il controllo non deve bloccare a lungo
MAX_NOVITA = 1200                  # caratteri delle novità mostrati
MAX_BYTE = 2_000_000_000           # uno zip più grande non è il nostro pacchetto (la 1.0.0 pesa 50 MB)
LOCALI = {"127.0.0.1", "localhost", "::1"}   # http solo verso questo computer (prove con una Release finta)
PS1 = ("installer", "windows", "aggiorna_pmn.ps1")
APP_EXE = ("app_windows", "ProfileMetaNanni", "ProfileMetaNanni.exe")


class ErroreAggiorna(Exception):
    """codice: RETE, CERTIFICATO, LIMITE, RISPOSTA, INDIRIZZO, PACCHETTO_DIVERSO, INCOMPATIBILE, SPAZIO, DISCO, ANNULLATO."""
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


def errore_http(codice, intestazioni):
    """GitHub ha risposto con un codice di errore: limite di richieste (403/429) o altro."""
    if codice == 429 or (codice == 403 and intestazioni.get("x-ratelimit-remaining") == "0"):
        try:
            ora = datetime.fromtimestamp(int(intestazioni.get("x-ratelimit-reset"))).strftime("%H:%M")
        except (TypeError, ValueError, OSError):
            ora = None
        return ErroreAggiorna("LIMITE", _("GitHub accetta pochi controlli all'ora da questa rete e il limite è "
                                          "raggiunto."),
                              _("Riprova dopo le {ora}.", ora=ora) if ora else _("Riprova fra un'ora."))
    return ErroreAggiorna("RISPOSTA", _("GitHub ha risposto con un errore (codice {codice}).", codice=codice),
                          _("Riprova più tardi."))


def errore_rete(errore_qt):
    """Errore della rete di Qt: certificato non verificato (B2-7a, punto 6) oppure rete assente o lenta."""
    from PySide6.QtNetwork import QNetworkReply
    if errore_qt == QNetworkReply.NetworkError.SslHandshakeFailedError:
        return ErroreAggiorna("CERTIFICATO", _("Windows non riesce a verificare il certificato di sicurezza di "
                                               "GitHub."),
                              _("Controlla che data e ora del computer siano giuste, poi riprova. Se la rete è di "
                                "un'azienda o di un ente, chiedi a chi la gestisce se blocca GitHub."))
    return ErroreAggiorna("RETE", _("Non riesco a raggiungere GitHub."),
                          _("Controlla la connessione a internet e riprova."))


def _chiedi(url, timeout, su_dati=None):
    """GET con la rete di Qt; torna i byte della risposta (vuoti se su_dati riceve i pezzi man mano).
    B2-7a (come app/progetto.py): urllib di Python si fida solo delle radici già nell'archivio di Windows, e una
    Windows appena installata non le ha tutte; Qt fa completare la catena a Windows, che scarica la radice che
    manca come fanno i browser. Rinvii solo verso indirizzi non meno sicuri (GitHub manda lo zip a un altro server
    HTTPS). Un ciclo di eventi locale aspetta la risposta: intanto la finestra resta viva."""
    from PySide6.QtCore import QEventLoop, QUrl
    from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
    rete = QNetworkAccessManager()
    richiesta = QNetworkRequest(QUrl(sicuro(url)))
    richiesta.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, f"ProfileMetaNanni/{VERSIONE}")
    richiesta.setRawHeader(b"Accept", b"application/vnd.github+json")
    richiesta.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                           QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
    richiesta.setTransferTimeout(int(timeout * 1000))       # niente byte per tanto tempo: si ferma
    risposta = rete.get(richiesta)
    pezzi, problema = [], []

    def leggi():
        dati = bytes(risposta.readAll().data())
        if problema or not dati:
            return
        if su_dati is None:
            pezzi.append(dati)
            return
        try:
            su_dati(dati)
        except (ErroreAggiorna, OSError) as e:
            problema.append(e)
            risposta.abort()
    risposta.readyRead.connect(leggi)
    giro = QEventLoop()
    risposta.finished.connect(giro.quit)
    if not risposta.isFinished():
        giro.exec()
    leggi()
    codice = risposta.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
    intestazioni = {bytes(k).decode("latin-1").lower(): bytes(v).decode("latin-1") for k, v in risposta.rawHeaderPairs()}
    errore, finale = risposta.error(), risposta.url().toString()
    risposta.deleteLater()
    if problema:
        raise problema[0]
    if codice is not None and codice >= 400:
        raise errore_http(codice, intestazioni)
    if errore != QNetworkReply.NetworkError.NoError:
        raise errore_rete(errore)
    sicuro(finale)
    return b"".join(pezzi)


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
    grezzo = _chiedi(url, timeout)
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
    h, fatti = hashlib.sha256(), [0]
    diverso = ErroreAggiorna("PACCHETTO_DIVERSO", _("Il file scaricato non è quello pubblicato."),
                             _("Riprova: se succede ancora, scarica la versione nuova dalla pagina della Release."))
    try:
        with open(dest, "wb") as f:
            def pezzo(blocco):
                fatti[0] += len(blocco)
                if fatti[0] > pacchetto["byte"]:
                    raise diverso
                h.update(blocco)
                f.write(blocco)
                if avanzamento:
                    avanzamento(fatti[0], pacchetto["byte"])
                if fermo and fermo():
                    raise ErroreAggiorna("ANNULLATO", _("Aggiornamento annullato: non ho cambiato nulla."))
            _chiedi(pacchetto["url"], timeout, pezzo)
        if fatti[0] != pacchetto["byte"] or (pacchetto["sha256"] and h.hexdigest() != pacchetto["sha256"]):
            raise diverso
    except ErroreAggiorna:
        dest.unlink(missing_ok=True)
        raise
    except OSError:                            # il file non si scrive (disco pieno, cartella bloccata)
        dest.unlink(missing_ok=True)
        raise ErroreAggiorna("DISCO", _("Non riesco a preparare la versione nuova sul disco."),
                             _("Scaricala dalla pagina della Release e installala con il doppio clic."))
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
