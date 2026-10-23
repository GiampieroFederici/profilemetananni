"""La finestra dell'app (docs/interfaccia_S4.md §3): testata, percorso a sinistra, pagina al centro,
barra delle azioni in basso con un solo pulsante principale (R1). Prima di tutto l'avvio: l'avatar
saltella e si ferma mentre arriva `info` dal motore (D046). Tastiera (R15): Tab segue l'ordine di lettura,
Invio preme il pulsante che ha il fuoco.

Si cambia solo in S5a (D061): S5b e S6 scrivono le loro pagine in app/pagine/.
"""
import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from app import lingua
from app.lingua import N_, _
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
PERCORSO = [("campioni", "1", N_("Campioni e prodotto")), ("scelte", "2", N_("Scelte dell'analisi")),
            ("esecuzione", "3", N_("Analisi in corso")), ("risultati", "4", N_("Risultati"))]
EXTRA = ("sicurezza", "+", N_("Sicurezza alimentare"))
MENU = [("home", N_("I miei progetti")), ("motore", N_("Motore")), ("crediti", N_("Come citare"))]
AVVIO_MIN_MS = 2500                  # l'avatar resta almeno 2,5 s (prototipo: 2-3 s)
AVVIO_LENTO_MS = 5000                # info oltre 5 s: avvio a freddo della WSL, lo si spiega (A2)
AVVIO_MAX_MS = 90000                 # info oltre 90 s: WSL appesa, si chiude e si va avanti (oltre il minuto a freddo)
AVVIO_LENTO = N_("Il motore si sta avviando. La prima volta dopo l'accensione del computer può volerci fino a un "
                 "minuto: è normale, non chiudere la finestra.")


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


def misure(libero):
    """B2 (P7): misura iniziale e minima della finestra, mai più grandi dello spazio libero dello schermo (sulla VM la
    finestra usciva a destra e la testata era tagliata). 40 px per la barra del titolo, che Qt non conta."""
    w, h = libero.width(), libero.height() - 40
    return QSize(min(1366, w), min(860, h)), QSize(min(1100, w), min(700, h))


class Finestra(QMainWindow):
    def __init__(self, movimento=None):
        super().__init__()
        self._movimento = movimento               # None: segue Windows; True o False: deciso (per i test)
        self.setWindowTitle("ProfileMetaNanni")
        self.setWindowIcon(QIcon(str(RISORSE / "avatar_512.png")))
        grande, minima = misure(QGuiApplication.primaryScreen().availableGeometry().size())
        self.resize(grande)
        self.setMinimumSize(minima)
        self.contesto = Contesto()
        self.pagine = {}
        self.attuale = None
        self._respiro = None

        self.fuori = QStackedWidget()
        self.setCentralWidget(self.fuori)
        self.fuori.addWidget(self._avvio())
        self.fuori.addWidget(self._area())

    @property
    def movimento(self):
        """L'avatar si muove? Letto da Windows a ogni animazione: vale anche se lo si cambia ad app aperta."""
        return not movimento_ridotto() if self._movimento is None else self._movimento

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
        self.messaggio_avvio = QLabel(_("Avvio il motore..."))
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
        QTimer.singleShot(AVVIO_LENTO_MS, self._avvio_lento)
        QTimer.singleShot(AVVIO_MAX_MS, self._avvio_scaduto)
        self.client_info = MotoreClient(self)
        self.client_info.evento.connect(self._evento_info)
        self.client_info.finito.connect(self._info_finito)
        self.client_info.avvia("info")
        self.client_lingua = MotoreClient(self)        # info di nuovo dopo un cambio di lingua (testi del motore)
        self.client_lingua.finito.connect(self._info_in_lingua)

    def _avvio_lento(self):
        if not self._pronto["info"]:
            self.messaggio_avvio.setText(_(AVVIO_LENTO))

    def _avvio_scaduto(self):
        if not self._pronto["info"]:
            self.client_info.ferma()

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
            p.info_cambiata.connect(self._stato_motore)
            self.pagine[chiave] = p
            scorre = QScrollArea()
            scorre.setWidgetResizable(True)
            scorre.setWidget(p)
            self.pila.addWidget(scorre)
        self.pagine["esecuzione"].analisi_finita.connect(self._analisi_finita)
        g.addWidget(self.pila, 1, 1)
        g.addWidget(self._barra(), 2, 0, 1, 2)
        g.setColumnStretch(1, 1)
        g.setRowStretch(1, 1)
        return w

    def _testata(self):
        t = self.zona_testata = QFrame(objectName="testata")
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
        self.stato_motore = QPushButton(_("Motore: controllo..."), objectName="link")
        self.stato_motore.clicked.connect(lambda: self.vai("motore"))
        s.addWidget(self.pallino)
        s.addWidget(self.stato_motore)
        for chiave, testo in MENU:
            b = QPushButton(_(testo), objectName="link")
            b.clicked.connect(lambda _x=False, c=chiave: self.vai(c))
            s.addWidget(b)
        scelta = QWidget(objectName="lingua")          # l'interruttore della lingua, sempre in testata (18/10)
        r = QHBoxLayout(scelta)
        r.setContentsMargins(0, 0, 0, 0)
        altra = "en" if lingua.attuale() == "it" else "it"
        self.pulsante_lingua = QPushButton(lingua.LINGUE[altra], objectName="link")
        self.pulsante_lingua.setAccessibleName(_("Cambia lingua: {lingua}", lingua=lingua.LINGUE[altra]))
        self.pulsante_lingua.setToolTip(self.pulsante_lingua.accessibleName())
        self.pulsante_lingua.clicked.connect(lambda: self.cambia_lingua(altra))
        r.addWidget(self.pulsante_lingua)
        s.addWidget(scelta)
        self._stato_motore()
        return t

    def _percorso(self):
        p = self.zona_percorso = QFrame(objectName="percorso")
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
            b.clicked.connect(lambda _x=False, c=chiave: self.vai(c))
            self.passi[chiave] = (b, numero, _(testo))
            s.addWidget(b)
        s.addStretch(1)
        return p

    def _barra(self):
        b = self.zona_barra = QFrame(objectName="azioni")
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
        self._azioni()

    def _analisi_finita(self):
        """Analisi finita con la pagina Motore aperta: si ridisegna come a un nuovo ingresso, così "Controlla il
        motore" si riaccende subito (prima restava spento finché non si cambiava pagina)."""
        if self.attuale == "motore":
            self.pagine["motore"].mostrata()

    def _passi_fatti(self):
        """I passi del percorso già fatti nel progetto aperto (letti dal progetto, non dalla pagina attuale)."""
        progetto = self.contesto.progetto
        if progetto is None:
            return set()
        try:
            app = progetto.leggi().get("app")
        except (OSError, ValueError):
            app = None
        app = app if isinstance(app, dict) else {}
        fatti = set()
        if app.get("prodotto"):                    # Campioni e prodotto salvati (D079)
            fatti.add("campioni")
        if app.get("scelte"):                      # scelte confermate (D081)
            fatti.add("scelte")
        if (progetto.risultati / "risultati.json").is_file():
            fatti |= {"esecuzione", "risultati"}
        return fatti

    def _percorso_stato(self):
        fatti = self._passi_fatti()
        for c, (b, numero, testo) in self.passi.items():
            stato = "attivo" if c == self.attuale else ("fatto" if c in fatti else "")
            b.setText(f"{'✓' if c in fatti else numero}   {testo}")
            b.setProperty("stato", stato)
            b.setAccessibleDescription(", ".join(d for d, si in ((_("passo attuale"), stato == "attivo"),
                                                                 (_("fatto"), c in fatti)) if si))
            b.style().unpolish(b)
            b.style().polish(b)

    def _azioni(self):
        p = self.pagine[self.attuale]
        self.principale.setText(p.testo_principale)
        self.principale.setEnabled(p.principale_attivo)
        self.principale.setProperty("pericolo", p.principale_pericolo)
        self.principale.style().unpolish(self.principale)
        self.principale.style().polish(self.principale)
        self.aiuto.setText(p.aiuto)
        self.aiuto.setProperty("livello", p.aiuto_livello)
        self.aiuto.style().unpolish(self.aiuto)
        self.aiuto.style().polish(self.aiuto)
        for b in self.secondari:
            b.hide()                               # deleteLater non lo toglie finché Qt non fa quel giro (L1a)
            b.deleteLater()
        self.secondari = []
        for testo, funzione in p.secondari:
            b = QPushButton(testo, objectName="secondario")
            b.clicked.connect(funzione)
            self.barra.insertWidget(self.barra.count() - 1, b)
            self.secondari.append(b)
        self._percorso_stato()                     # lo stato del progetto può essere cambiato (analisi finita)

    def _stato_motore(self):
        info = self.contesto.info
        if info is None and getattr(self, "client_info", None) and self.client_info.in_corso():
            stato, testo = "attesa", _("Motore: controllo...")
        elif info is None:
            stato, testo = "rosso", _("Motore da controllare")
        else:
            stato, testo = "", _("Motore di prova") if info.get("finto") else _("Motore pronto")
        self.pallino.setProperty("stato", stato)
        self.pallino.style().unpolish(self.pallino)
        self.pallino.style().polish(self.pallino)
        self.stato_motore.setText(testo)

    # ---------------- lingua (18/10) ----------------
    def occupato(self):
        """True se il motore sta lavorando (analisi, installazione, calcolo, stima...): intanto la lingua non cambia,
        perché le pagine si rifanno da capo e il lavoro in corso si perderebbe."""
        return self.contesto.progetto_in_analisi is not None or any(
            c.in_corso() for c in self.findChildren(MotoreClient))

    def cambia_lingua(self, codice):
        """Rifà testata, percorso, pagine e barra nella nuova lingua e torna alla stessa pagina; poi chiede di nuovo
        `info` al motore, così anche i suoi testi (consigli, prodotti) sono nella nuova lingua."""
        if self.occupato():
            self.aiuto.setText(_("Puoi cambiare lingua quando il motore ha finito il lavoro in corso."))
            self.aiuto.setProperty("livello", "avviso")
            self.aiuto.style().unpolish(self.aiuto)
            self.aiuto.style().polish(self.aiuto)
            return False
        lingua.imposta(codice)
        lingua.salva(codice)
        vecchia = self.fuori.widget(1)
        self.fuori.removeWidget(vecchia)
        vecchia.hide()
        vecchia.deleteLater()
        self.pagine, self.secondari = {}, []
        self.fuori.insertWidget(1, self._area())
        self.fuori.setCurrentIndex(1)
        self.vai(self.attuale or "home")
        self.pulsante_lingua.setFocus()
        if getattr(self, "client_lingua", None) is not None and self.contesto.info is not None:
            self.client_lingua.avvia("info")
        return True

    def _info_in_lingua(self, codice, fine):
        if fine.get("esito") == "ok":
            self.contesto.info = fine["risultato"]
        self._stato_motore()
        if self.attuale and not self.occupato():
            self.vai(self.attuale)

    # ---------------- tastiera (R15) ----------------
    def _fermate(self):
        """I comandi raggiungibili col Tab, nell'ordine in cui si leggono: testata, percorso, pagina, barra.
        Testata e barra sono righe: da sinistra a destra. Nel percorso e nella pagina i blocchi vanno dall'alto in
        basso e da sinistra a destra; dentro un blocco (per esempio
        le due colonne di Sicurezza) vale l'ordine in cui Qt li ha creati. Così anche i comandi comparsi dopo
        (l'elenco dei progetti, i pulsanti della barra) sono al posto giusto."""
        catena, w = {}, self.nextInFocusChain()
        while w is not self and w not in catena:
            catena[w] = len(catena)
            w = w.nextInFocusChain()
        scorre = self.pila.currentWidget()
        fermate = []
        for zona, radice, riga in ((self.zona_testata, self.zona_testata, True),
                                   (self.zona_percorso, self.zona_percorso, False),
                                   (scorre, scorre.widget(), False), (self.zona_barra, self.zona_barra, True)):
            def chiave(w):
                blocco = w
                while blocco.parentWidget() is not radice and blocco.parentWidget() is not None:
                    blocco = blocco.parentWidget()
                angolo = blocco.mapTo(zona, QPoint(0, 0))
                return 0 if riga else angolo.y() // 8, angolo.x(), catena.get(w, 0)    # 8 px: stessa riga
            dentro = [w for w in zona.findChildren(QWidget) if w.isVisible() and w.isEnabled()
                      and w.focusPolicy() & Qt.TabFocus and w.focusProxy() is None]
            if zona is scorre:
                fermate.append(scorre)          # con il fuoco sull'area le frecce fanno scorrere la pagina
            fermate += sorted(dentro, key=chiave)
        return fermate

    def focusNextPrevChild(self, avanti):
        if self.fuori.currentIndex() != 1:
            return super().focusNextPrevChild(avanti)
        fermate = self._fermate()
        attuale = self.focusWidget()
        if attuale in fermate:
            i = fermate.index(attuale) + (1 if avanti else -1)
        else:
            i = 0 if avanti else -1
        prossimo = fermate[i % len(fermate)]
        prossimo.setFocus(Qt.TabFocusReason if avanti else Qt.BacktabFocusReason)
        scorre = self.pila.currentWidget()
        if scorre.isAncestorOf(prossimo):
            scorre.ensureWidgetVisible(prossimo, 24, 24)
        return True

    def keyPressEvent(self, evento):
        """Invio (o il tasto Invio del tastierino) preme il pulsante che ha il fuoco, come la barra spaziatrice."""
        fuoco = self.focusWidget()
        if evento.key() in (Qt.Key_Return, Qt.Key_Enter) and isinstance(fuoco, QPushButton) and fuoco.isEnabled():
            fuoco.click()
            return
        super().keyPressEvent(evento)

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
