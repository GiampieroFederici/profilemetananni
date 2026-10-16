"""La finestra dell'app (docs/interfaccia_S4.md §3): testata, percorso a sinistra, pagina al centro,
barra delle azioni in basso con un solo pulsante principale (R1). Prima di tutto l'avvio: l'avatar
saltella e si ferma mentre arriva `info` dal motore (D046).

Si cambia solo in S5a (D061): S5b e S6 scrivono le loro pagine in app/pagine/.
"""
import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from app.motore import MotoreClient
from app.pagine.base import Contesto
from app.pagine.crediti import PaginaCrediti
from app.pagine.esecuzione import PaginaEsecuzione
from app.pagine.home import PaginaHome
from app.pagine.motore import PaginaMotore
from app.pagine.progetto import PaginaCampioni
from app.pagine.risultati import PaginaRisultati
from app.pagine.scelte import PaginaScelte
from app.pagine.sicurezza import PaginaSicurezza

RISORSE = Path(__file__).resolve().parent / "risorse"
PAGINE = {"home": PaginaHome, "campioni": PaginaCampioni, "scelte": PaginaScelte, "esecuzione": PaginaEsecuzione,
          "risultati": PaginaRisultati, "sicurezza": PaginaSicurezza, "motore": PaginaMotore,
          "crediti": PaginaCrediti}
PERCORSO = [("campioni", "1", "Campioni e prodotto"), ("scelte", "2", "Scelte dell'analisi"),
            ("esecuzione", "3", "Analisi in corso"), ("risultati", "4", "Risultati")]
EXTRA = ("sicurezza", "+", "Sicurezza alimentare")
MENU = [("home", "I miei progetti"), ("motore", "Motore"), ("crediti", "Come citare")]
AVVIO_MIN_MS = 2500                  # l'avatar resta almeno 2,5 s (prototipo: 2-3 s)


def movimento_ridotto():
    """True se in Windows è spento "Mostra animazioni" (R15: l'avatar non si muove)."""
    if sys.platform != "win32":
        return False
    import ctypes
    acceso = ctypes.c_int(1)
    ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(acceso), 0)   # SPI_GETCLIENTAREAANIMATION
    return not acceso.value


def arrotondata(pixmap, lato, raggio):
    """L'immagine dell'avatar con gli angoli arrotondati, come nel prototipo."""
    sorgente = pixmap.scaled(lato, lato, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    uscita = QPixmap(sorgente.size())
    uscita.fill(Qt.transparent)
    pittore = QPainter(uscita)
    pittore.setRenderHint(QPainter.Antialiasing)
    bordo = QPainterPath()
    bordo.addRoundedRect(0, 0, sorgente.width(), sorgente.height(), raggio, raggio)
    pittore.setClipPath(bordo)
    pittore.drawPixmap(0, 0, sorgente)
    pittore.end()
    return uscita


class Finestra(QMainWindow):
    def __init__(self, movimento=None):
        super().__init__()
        self.movimento = not movimento_ridotto() if movimento is None else movimento
        self.setWindowTitle("ProfileMetaNanni")
        self.setWindowIcon(QIcon(str(RISORSE / "avatar_512.png")))
        self.resize(1366, 860)
        self.setMinimumSize(1100, 700)
        self.contesto = Contesto()
        self.pagine = {}
        self.attuale = None
        self._respiro = None

        self.fuori = QStackedWidget()
        self.setCentralWidget(self.fuori)
        self.fuori.addWidget(self._avvio())
        self.fuori.addWidget(self._area())

    # ---------------- avvio ----------------
    def _avvio(self):
        w = QWidget(objectName="avvio")
        s = QVBoxLayout(w)
        s.setAlignment(Qt.AlignCenter)
        self.palco = QWidget()                   # spazio dove l'avatar cade e rimbalza
        self.palco.setFixedSize(460, 560)
        self.avatar = QLabel(self.palco)
        self.avatar.setPixmap(arrotondata(QPixmap(str(RISORSE / "avatar_512.png")), 440, 28))
        self.avatar.setFixedSize(440, 440)
        self.avatar.move(10, 110)
        self.avatar.setAccessibleName("ProfileMetaNanni")
        self.messaggio_avvio = QLabel("Avvio il motore...")
        self.messaggio_avvio.setAlignment(Qt.AlignCenter)
        self.messaggio_avvio.setWordWrap(True)
        s.addWidget(self.palco, 0, Qt.AlignHCenter)
        s.addWidget(self.messaggio_avvio)
        return w

    def avvia(self):
        """Mostra l'avvio e chiede `info` al motore; passa a "I miei progetti" quando ci sono entrambi."""
        self.fuori.setCurrentIndex(0)
        self._pronto = {"info": False, "tempo": False}
        if self.movimento:
            self._salto = QPropertyAnimation(self.avatar, b"pos", self)
            self._salto.setStartValue(QPoint(10, -60))
            self._salto.setEndValue(QPoint(10, 110))
            self._salto.setDuration(1400)
            self._salto.setEasingCurve(QEasingCurve.OutBounce)
            self._salto.start()
        QTimer.singleShot(AVVIO_MIN_MS, lambda: self._avvio_pronto("tempo"))
        self.client_info = MotoreClient(self)
        self.client_info.evento.connect(self._evento_info)
        self.client_info.finito.connect(self._info_finito)
        self.client_info.avvia("info")

    def _evento_info(self, e):
        if e["tipo"] == "fine":
            self.messaggio_avvio.setText(e["messaggio"])
            if e["esito"] == "ok":
                self.contesto.info = e["risultato"]

    def _info_finito(self, codice, fine):
        self._stato_motore()
        self._avvio_pronto("info")

    def _avvio_pronto(self, cosa):
        self._pronto[cosa] = True
        if all(self._pronto.values()):
            self.fuori.setCurrentIndex(1)
            self.vai("home")

    # ---------------- finestra ----------------
    def _area(self):
        w = QWidget(objectName="area")
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(0)
        g.addWidget(self._testata(), 0, 0, 1, 2)
        g.addWidget(self._percorso(), 1, 0)
        self.pila = QStackedWidget()
        for chiave, classe in PAGINE.items():
            p = classe(self.contesto)
            p.vai.connect(self.vai)
            p.azioni_cambiate.connect(self._azioni)
            p.respira.connect(self.respira)
            self.pagine[chiave] = p
            scorre = QScrollArea()
            scorre.setWidgetResizable(True)
            scorre.setWidget(p)
            self.pila.addWidget(scorre)
        g.addWidget(self.pila, 1, 1)
        g.addWidget(self._barra(), 2, 0, 1, 2)
        g.setColumnStretch(1, 1)
        g.setRowStretch(1, 1)
        return w

    def _testata(self):
        t = QFrame(objectName="testata")
        s = QHBoxLayout(t)
        s.setContentsMargins(20, 10, 20, 10)
        s.setSpacing(16)
        self.emblema = QLabel(objectName="emblema")
        self.emblema.setFixedSize(84, 42)
        self.emblema.setAlignment(Qt.AlignCenter)
        self.emblema.setPixmap(QPixmap(str(RISORSE / "avatar_baffi.png")).scaled(
            74, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.emblema.setAccessibleName("ProfileMetaNanni")
        s.addWidget(self.emblema)
        s.addWidget(QLabel("ProfileMetaNanni", objectName="nome"))
        self.nome_progetto = QLabel("", objectName="nome_progetto")
        s.addWidget(self.nome_progetto)
        s.addStretch(1)
        self.pallino = QLabel(objectName="pallino")
        self.pallino.setFixedSize(14, 14)
        self.stato_motore = QPushButton("Motore: controllo...", objectName="link")
        self.stato_motore.clicked.connect(lambda: self.vai("motore"))
        s.addWidget(self.pallino)
        s.addWidget(self.stato_motore)
        for chiave, testo in MENU:
            b = QPushButton(testo, objectName="link")
            b.clicked.connect(lambda _=False, c=chiave: self.vai(c))
            s.addWidget(b)
        self._stato_motore()
        return t

    def _percorso(self):
        p = QFrame(objectName="percorso")
        p.setFixedWidth(306)
        s = QVBoxLayout(p)
        s.setContentsMargins(16, 24, 16, 24)
        s.setSpacing(4)
        self.passi = {}
        for chiave, numero, testo in PERCORSO + [EXTRA]:
            if chiave == EXTRA[0]:
                s.addSpacing(16)
                s.addWidget(QFrame(objectName="separatore"))
                s.addSpacing(12)
            b = QPushButton(objectName="passo")
            b.clicked.connect(lambda _=False, c=chiave: self.vai(c))
            self.passi[chiave] = (b, numero, testo)
            s.addWidget(b)
        s.addStretch(1)
        return p

    def _barra(self):
        b = QFrame(objectName="azioni")
        self.barra = QHBoxLayout(b)
        self.barra.setContentsMargins(24, 12, 24, 12)
        self.barra.setSpacing(16)
        self.aiuto = QLabel(objectName="aiuto")
        self.aiuto.setWordWrap(True)
        self.barra.addWidget(self.aiuto, 1)
        self.secondari = []
        self.principale = QPushButton(objectName="principale")
        self.principale.clicked.connect(lambda: self.pagine[self.attuale].azione_principale())
        self.barra.addWidget(self.principale)
        return b

    # ---------------- navigazione ----------------
    def vai(self, chiave):
        self.attuale = chiave
        pagina = self.pagine[chiave]
        self.pila.setCurrentIndex(list(self.pagine).index(chiave))
        pagina.mostrata()
        progetto = self.contesto.progetto
        self.nome_progetto.setText(f"· {progetto.nome}" if progetto else "")
        indice = next((i for i, (c, _, _) in enumerate(PERCORSO) if c == chiave), -1)
        for i, (c, (b, numero, testo)) in enumerate(self.passi.items()):
            stato = "attivo" if c == chiave else ("fatto" if 0 <= i < indice else "")
            b.setText(f"{'✓' if stato == 'fatto' else numero}   {testo}")
            b.setProperty("stato", stato)
            b.setAccessibleDescription("passo attuale" if stato == "attivo" else "")
            b.style().unpolish(b)
            b.style().polish(b)
        self._azioni()

    def _azioni(self):
        p = self.pagine[self.attuale]
        self.principale.setText(p.testo_principale)
        self.principale.setEnabled(p.principale_attivo)
        self.aiuto.setText(p.aiuto)
        self.aiuto.setProperty("livello", p.aiuto_livello)
        self.aiuto.style().unpolish(self.aiuto)
        self.aiuto.style().polish(self.aiuto)
        for b in self.secondari:
            b.deleteLater()
        self.secondari = []
        for testo, funzione in p.secondari:
            b = QPushButton(testo, objectName="secondario")
            b.clicked.connect(funzione)
            self.barra.insertWidget(self.barra.count() - 1, b)
            self.secondari.append(b)

    def _stato_motore(self):
        info = self.contesto.info
        if info is None and getattr(self, "client_info", None) and self.client_info.in_corso():
            stato, testo = "attesa", "Motore: controllo..."
        elif info is None:
            stato, testo = "rosso", "Motore da controllare"
        else:
            stato, testo = "", "Motore di prova" if info.get("finto") else "Motore pronto"
        self.pallino.setProperty("stato", stato)
        self.pallino.style().unpolish(self.pallino)
        self.pallino.style().polish(self.pallino)
        self.stato_motore.setText(testo)

    # ---------------- avatar che respira ----------------
    def respira(self, si):
        """Durante un lavoro lungo l'avatar della testata si illumina piano; si ferma alla fine (D046)."""
        if self._respiro:
            self._respiro.stop()
            self._respiro = None
            self.emblema.setGraphicsEffect(None)
        if not (si and self.movimento):
            return
        luce = QGraphicsDropShadowEffect(self.emblema)
        luce.setColor(QColor("#5BFF5B"))
        luce.setOffset(0, 0)
        self.emblema.setGraphicsEffect(luce)
        self._respiro = QPropertyAnimation(luce, b"blurRadius", self)
        self._respiro.setKeyValues([(0, 0.0), (0.5, 22.0), (1, 0.0)])
        self._respiro.setDuration(2400)
        self._respiro.setEasingCurve(QEasingCurve.InOutSine)
        self._respiro.setLoopCount(-1)
        self._respiro.start()
