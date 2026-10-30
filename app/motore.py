"""MotoreClient: parla con pmn-motore (docs/contratto_motore.md) attraverso QProcess.

Il motore scrive su stdout una riga JSON per evento; qui ogni riga diventa il segnale `evento(dict)`.
L'app legge solo stdout (stderr e righe non JSON finiscono in `diagnostica`, mai all'utente: R2).

Garanzia per le pagine (come il contratto, §4): ogni corsa finisce sempre con UN solo `fine`, seguito da
`finito(codice_uscita, evento_fine)`. Se il motore non parte o si chiude senza `fine`, il client manda lui
un `errore` e un `fine` (codice MOTORE_NON_AVVIATO o ERRORE_INTERNO), così le pagine trattano un caso solo.

Su Windows Qt avvia wsl.exe senza finestra di console quando l'app non ne ha una (qprocess_win.cpp).

Quale motore: il vero in WSL (predefinito) oppure il finto (D032) con la variabile d'ambiente
PMN_MOTORE=finto; PMN_FINTO_OPZIONI aggiunge opzioni al finto (per esempio "--velocita 0 --scenario DB_MANCANTE").
"""
import json
import os
import re
import shlex
import shutil
import sys
from datetime import datetime
from pathlib import Path, PureWindowsPath

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from app import lingua
from app.lingua import _

RADICE = Path(__file__).resolve().parent.parent
DISTRO = "pmn"                                   # nome della WSL del motore (installer/windows/installa_pmn.ps1)
MOTORE_WSL = "/home/pmn/.pmn/bin/pmn-motore"     # collegato dall'installatore (D053)

    # nell'app impacchettata sys.executable è l'exe stesso: il finto la rilancerebbe a catena (30/10)
def finto():
    # nell app impacchettata sys.executable e l exe stesso: il finto la rilancerebbe a catena (30/10)
    return os.environ.get("PMN_MOTORE") == "finto" and not getattr(sys, "frozen", False)


def spazio_windows_gb():
    """B2 (P8): GB liberi del disco di Windows che contiene la WSL del motore. Dentro la WSL `info` vede il disco
    virtuale (sulla VM "990 GB liberi" con 146 veri); None se la WSL non si trova (non Windows, non installata)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Lxss") as lxss:
            for i in range(winreg.QueryInfoKey(lxss)[0]):
                with winreg.OpenKey(lxss, winreg.EnumKey(lxss, i)) as d:
                    if winreg.QueryValueEx(d, "DistributionName")[0] == DISTRO:
                        return shutil.disk_usage(winreg.QueryValueEx(d, "BasePath")[0]).free / 1e9
    except (ImportError, OSError):
        pass
    return None


def comando_motore():
    """Programma e primi argomenti per lanciare il motore."""
    if finto():
        opzioni = shlex.split(os.environ.get("PMN_FINTO_OPZIONI", ""))
        return [sys.executable, str(RADICE / "installer" / "finto_motore.py")], opzioni
    # -e e non "--": senza bash -c i percorsi con ' & $( ) arrivano intatti al motore
    return ["wsl.exe", "-d", DISTRO, "-u", "pmn", "-e", MOTORE_WSL], []


LINUX = re.compile(r"(?<![\w/.])/(?:home/pmn|mnt/([a-z]))(/[^\s\"'<>]*)?")


def percorso_windows(testo):
    """B2-13 (R18): nei testi del motore i percorsi Linux come si aprono da Windows. /home/pmn/... ->
    \\\\wsl.localhost\\pmn\\home\\pmn\\... (la WSL del motore), /mnt/c/... -> C:\\... ; il punto finale della frase
    resta fuori dal percorso."""
    def windows(m):
        resto, coda = m.group(2) or "", ""
        while resto and resto[-1] in ".,;:)":
            resto, coda = resto[:-1], resto[-1] + coda
        if m.group(1):
            return m.group(1).upper() + ":" + (resto.replace("/", "\\") or "\\") + coda
        return "\\\\wsl.localhost\\" + DISTRO + "\\home\\pmn" + resto.replace("/", "\\") + coda
    return LINUX.sub(windows, testo)


def percorso_per_motore(percorso):
    """Un percorso di Windows come lo vede il motore: C:\\a\\b -> /mnt/c/a/b nella WSL; invariato per il finto."""
    if finto():
        return str(percorso)
    p = PureWindowsPath(Path(percorso).resolve())
    if not p.drive.endswith(":"):
        raise ValueError(f"Percorso non su un disco locale: {percorso}")
    return "/mnt/" + p.drive[0].lower() + "/" + "/".join(p.parts[1:])


class MotoreClient(QObject):
    """Una corsa alla volta per client. Uso: c = MotoreClient(); c.evento.connect(...); c.avvia("info")."""
    evento = Signal(dict)
    finito = Signal(int, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.corsa = None            # id dell'evento inizio: serve ad annulla
        self.comando = None
        self.diagnostica = []        # stderr e righe non JSON: solo per "Dettagli tecnici" / registro
        self._fine = None
        self._resto = b""
        self._p = None

    def in_corso(self):
        return self._p is not None and self._p.state() != QProcess.NotRunning

    def avvia(self, comando, *argomenti):
        if self.in_corso():
            raise RuntimeError("Questo client ha già una corsa in corso")
        self.corsa, self.comando, self._fine, self._resto = None, comando, None, b""
        self.diagnostica = []
        programma, opzioni = comando_motore()
        p = QProcess(self)
        p.setProcessEnvironment(_ambiente())
        p.readyReadStandardOutput.connect(self._leggi)
        p.readyReadStandardError.connect(
            lambda: self.diagnostica.append(bytes(p.readAllStandardError()).decode("utf-8", "replace")))
        p.finished.connect(self._chiuso)
        p.errorOccurred.connect(self._non_partito)
        self._p = p
        p.start(programma[0], programma[1:] + [comando, *argomenti] + opzioni + lingua.per_motore())

    def annulla(self):
        """Chiede al motore di fermare la corsa in modo pulito (comando annulla --corsa <id>)."""
        if not (self.in_corso() and self.corsa):
            return False
        programma, opzioni = comando_motore()
        a = QProcess(self)
        a.setProcessEnvironment(_ambiente())
        a.finished.connect(a.deleteLater)
        a.start(programma[0], programma[1:] + ["annulla", "--corsa", self.corsa] + opzioni + lingua.per_motore())
        return True

    def ferma(self):
        """Chiude il processo se non risponde (wsl.exe appeso): _chiuso manda errore e fine come sempre."""
        if self.in_corso():
            self._p.kill()

    # ------------------------------------------------------------------
    def _leggi(self):
        self._resto += bytes(self._p.readAllStandardOutput())
        *righe, self._resto = self._resto.split(b"\n")
        for r in righe:
            self._riga(r)

    def _riga(self, r):
        testo = r.decode("utf-8", "replace").strip()
        if not testo:
            return
        try:
            e = json.loads(testo)
        except json.JSONDecodeError:
            self.diagnostica.append(testo)
            return
        if not isinstance(e, dict) or "tipo" not in e:
            self.diagnostica.append(testo)
            return
        if not finto():                            # B2-13: ciò che la persona legge, con percorsi apribili da Windows
            for chiave in ("messaggio", "cosa_fare", "log"):
                if isinstance(e.get(chiave), str):
                    e[chiave] = percorso_windows(e[chiave])
        if e["tipo"] == "inizio":
            self.corsa = e.get("corsa")
        if e["tipo"] == "fine":
            self._fine = e
        self.evento.emit(e)

    def _chiuso(self, codice, stato):
        if self._resto:
            self._riga(self._resto)
            self._resto = b""
        if self._fine is None and self.corsa is None:       # niente inizio: il motore non è mai partito
            self._sintetico("MOTORE_NON_AVVIATO", _("Non riesco ad avviare il motore."),
                            _("Apri la pagina Motore e premi Controlla il motore."))
            codice = 4
        elif self._fine is None:
            self._sintetico("ERRORE_INTERNO", _("Il motore si è chiuso senza finire il lavoro."),
                            _("Riprova. Se succede ancora, mandaci il registro del motore."))
            codice = 4
        elif stato != QProcess.NormalExit:
            codice = 4
        self._p = None
        self.finito.emit(codice, self._fine)

    def _non_partito(self, errore):
        if errore != QProcess.FailedToStart:
            return
        self.diagnostica.append(self._p.errorString())
        self._sintetico("MOTORE_NON_AVVIATO", _("Non riesco ad avviare il motore."),
                        _("Apri la pagina Motore e premi Controlla il motore."))
        self._p = None
        self.finito.emit(4, self._fine)

    def _sintetico(self, codice, messaggio, cosa_fare):
        ora = datetime.now().astimezone().isoformat(timespec="seconds")
        self.evento.emit({"tipo": "errore", "ora": ora, "codice": codice, "messaggio": messaggio,
                          "cosa_fare": cosa_fare, "passo": None})
        self._fine = {"tipo": "fine", "ora": ora, "esito": "errore", "messaggio": messaggio,
                      "risultato": {"codice": codice}}
        self.evento.emit(self._fine)


def _ambiente():
    """WSL_UTF8=1: i messaggi di wsl.exe in UTF-8 invece che UTF-16 (diagnostica leggibile)."""
    e = QProcessEnvironment.systemEnvironment()
    e.insert("WSL_UTF8", "1")
    return e
