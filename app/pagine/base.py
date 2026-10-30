"""Pagina: l'interfaccia comune di tutte le pagine (S5a). S5b e S6 scrivono solo le loro pagine.

Una pagina mette il suo contenuto in `self.corpo` e dichiara la barra delle azioni:
  testo_principale   verbo che dice cosa succede (R1: un solo pulsante principale, in basso a destra)
  azione_principale  che cosa fa (predefinito: va alla pagina `destinazione`)
  aiuto              frase accanto al pulsante; aiuto_livello "avviso" la colora d'ambra (R9)
  secondari          altri pulsanti della barra: [(testo, funzione)]
  principale_pericolo  True se il principale interrompe un lavoro ("Ferma l'analisi"): bianco col bordo rosso
Dopo averli cambiati chiama self.azioni_cambiate.emit(). La finestra chiama mostrata() a ogni ingresso.
Se la pagina cambia contesto.info chiama self.info_cambiata.emit(): la testata aggiorna il pallino del motore.

Qui ci sono anche i pezzi grafici comuni (schede di scelta, pannelli, svuota); il loro stile è in stile.qss.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QRadioButton, QVBoxLayout, QWidget

from app import lingua
from app.lingua import N_, _


class Contesto:
    """Ciò che le pagine condividono: l'ultimo `info` del motore e il progetto aperto (app.progetto.Progetto).
    avvia_analisi: "Scelte" lo mette a True (dopo aver scritto config.yaml) prima di vai("esecuzione");
    "Analisi in corso" lancia `esegui` solo se è True e lo rimette subito a False.
    progetto_in_analisi: il progetto della corsa che sta girando (None se non gira nulla); intanto non se ne
    apre un altro."""
    def __init__(self):
        self.info = None
        self.progetto = None
        self.avvia_analisi = False
        self.progetto_in_analisi = None


class Pagina(QWidget):
    vai = Signal(str)               # chiave della pagina dove andare
    azioni_cambiate = Signal()      # la barra delle azioni va ridisegnata
    respira = Signal(bool)          # l'avatar "respira" durante un lavoro lungo (D046)
    info_cambiata = Signal()        # contesto.info è cambiato (per esempio dopo `installa`)
    analisi_finita = Signal()       # la corsa di esegui è finita (la manda "Analisi in corso")

    titolo = ""
    testo_principale = ""
    destinazione = None
    aiuto = ""
    aiuto_livello = ""
    principale_pericolo = False

    def __init__(self, contesto, parent=None):
        super().__init__(parent)
        self.contesto = contesto
        self.titolo, self.testo_principale = _(self.titolo), _(self.testo_principale)   # lingua di quando si crea
        self.principale_attivo = True
        self.secondari = []
        self.corpo = QVBoxLayout(self)
        self.corpo.setContentsMargins(40, 28, 40, 28)
        self.corpo.setSpacing(12)
        self.corpo.setAlignment(Qt.AlignTop)
        if self.titolo:
            self.corpo.addWidget(etichetta(self.titolo, "titolo"))

    def azione_principale(self):
        if self.destinazione:
            self.vai.emit(self.destinazione)

    def mostrata(self):
        pass


# D115: Kraken e FSSP portano questa scritta nella prova con le persone, finché K4 e L3 non sono fatte
PROTOTIPO = N_("Prototipo, non per decisioni.")


def etichetta(testo, nome=None):
    """Testo che va a capo da solo; nome = objectName per lo stile (titolo, sottotitolo, nota)."""
    e = QLabel(testo)
    e.setWordWrap(True)
    e.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if nome:
        e.setObjectName(nome)
    return e


def riquadro(titolo, testo, livello="info"):
    """Avviso, errore o informazione con la barra colorata a sinistra (livello: info, avviso, errore, R8-R9)."""
    r = QFrame()
    r.setProperty("livello", livello)
    r.setObjectName("riquadro")
    s = QVBoxLayout(r)
    s.setContentsMargins(18, 12, 18, 12)
    if titolo:
        s.addWidget(etichetta(titolo, "riquadro_titolo"))
    if testo:
        s.addWidget(etichetta(testo))
    return r


def numero(x, cifre=1):
    """Formatta un numero nella lingua scelta (R11: l'interfaccia formatta, non calcola): 15.6 -> '15,6'."""
    return lingua.separatori(f"{x:,.{cifre}f}")


class Scelta(QFrame):
    """Scheda grande con un pulsante tondo, il titolo e una frase che dice cosa fa (R5); si sceglie con un clic."""
    scelta = Signal()

    def __init__(self, titolo, spiega, gruppo, consigliato=False):
        super().__init__(objectName="scelta")
        s = QVBoxLayout(self)
        s.setContentsMargins(18, 14, 18, 14)
        riga = QHBoxLayout()
        self.pulsante = QRadioButton(titolo)
        self.pulsante.setStyleSheet("font-weight: bold;")
        gruppo.addButton(self.pulsante)
        riga.addWidget(self.pulsante)
        if consigliato:
            riga.addWidget(QLabel(_("consigliato"), objectName="consigliato"))
        riga.addStretch(1)
        s.addLayout(riga)
        self.spiega = etichetta(spiega)
        self.spiega.setContentsMargins(30, 0, 0, 0)
        s.addWidget(self.spiega)
        self.pulsante.toggled.connect(self._ridisegna)
        self._ridisegna()

    def mousePressEvent(self, evento):
        if self.pulsante.isEnabled():
            self.pulsante.setChecked(True)
        super().mousePressEvent(evento)

    def _ridisegna(self, *_):
        self.setProperty("scelto", self.pulsante.isChecked())
        self.setProperty("spento", not self.pulsante.isEnabled())
        self.style().unpolish(self)
        self.style().polish(self)
        if self.pulsante.isChecked():
            self.scelta.emit()

    def setEnabled(self, si):
        self.pulsante.setEnabled(si)
        self._ridisegna()


class PulsanteACapo(QPushButton):
    """Pulsante il cui testo va a capo quando la finestra è stretta (B2-2b): lo scrive una QLabel dentro, il
    pulsante resta cliccabile, selezionabile e raggiungibile col Tab come prima."""
    def __init__(self, testo="", **opzioni):
        super().__init__(**opzioni)
        self.scritta = QLabel()
        self.scritta.setWordWrap(True)
        self.scritta.setAttribute(Qt.WA_TransparentForMouseEvents)
        s = QHBoxLayout(self)
        s.setContentsMargins(0, 4, 0, 4)
        s.addWidget(self.scritta)
        politica = self.sizePolicy()
        politica.setHeightForWidth(True)
        self.setSizePolicy(politica)
        self.setText(testo)

    def setText(self, testo):
        self.scritta.setText(testo)
        self.setAccessibleName(testo)
        self.updateGeometry()

    def text(self):
        return self.scritta.text()

    def sizeHint(self):
        return self.layout().sizeHint()

    def minimumSizeHint(self):
        return self.layout().minimumSize()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, larghezza):
        return self.layout().totalHeightForWidth(larghezza)

    def _sottolinea(self, si):                 # come QPushButton#apri:hover/:focus di stile.qss
        f = self.scritta.font()
        f.setUnderline(si)
        self.scritta.setFont(f)

    def enterEvent(self, evento):
        self._sottolinea(True)
        super().enterEvent(evento)

    def leaveEvent(self, evento):
        self._sottolinea(self.hasFocus())
        super().leaveEvent(evento)

    def focusInEvent(self, evento):
        self._sottolinea(True)
        super().focusInEvent(evento)

    def focusOutEvent(self, evento):
        self._sottolinea(self.underMouse())
        super().focusOutEvent(evento)


def riga_di_scelte(*schede):
    """Schede affiancate; se la pagina è troppo stretta per affiancarle, una sotto l'altra (impila, B2-2b)."""
    r = QHBoxLayout(objectName="riga_di_scelte")
    r.setSpacing(16)
    for s in schede:
        r.addWidget(s, 1)
    return r


def impila(pagina, larghezza):
    """B2-2b: le righe di schede che a questa larghezza (spazio per il contenuto della pagina) non ci stanno
    affiancate vanno una sotto l'altra; quelle che ci stanno tornano affiancate."""
    for r in pagina.findChildren(QHBoxLayout, "riga_di_scelte"):
        schede = [r.itemAt(i).widget() for i in range(r.count())
                  if r.itemAt(i).widget() is not None and not r.itemAt(i).widget().isHidden()]
        affiancate = sum(s.minimumSizeHint().width() for s in schede) + r.spacing() * (len(schede) - 1)
        r.setDirection(QHBoxLayout.LeftToRight if affiancate <= larghezza else QHBoxLayout.TopToBottom)


def pannello(titolo=None):
    """Riquadro bianco con il bordo grigio; titolo facoltativo in grassetto."""
    p = QFrame(objectName="pannello")
    s = QVBoxLayout(p)
    s.setContentsMargins(22, 16, 22, 16)
    s.setSpacing(8)
    if titolo:
        s.addWidget(etichetta(titolo, "pannello_titolo"))
    return p, s


def svuota(disposizione):
    """Toglie i widget di un layout (per ridisegnare una zona della pagina), anche quelli dei layout dentro
    (B2-11a: la griglia della stima di prima restava visibile sotto quella nuova)."""
    while disposizione.count():
        voce = disposizione.takeAt(0)
        w, dentro = voce.widget(), voce.layout()
        if w:
            w.hide()
            w.deleteLater()
        elif dentro is not None:
            svuota(dentro)
            dentro.deleteLater()
