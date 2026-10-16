"""Pagina: l'interfaccia comune di tutte le pagine (S5a). S5b e S6 scrivono solo le loro pagine.

Una pagina mette il suo contenuto in `self.corpo` e dichiara la barra delle azioni:
  testo_principale   verbo che dice cosa succede (R1: un solo pulsante principale, in basso a destra)
  azione_principale  che cosa fa (predefinito: va alla pagina `destinazione`)
  aiuto              frase accanto al pulsante; aiuto_livello "avviso" la colora d'ambra (R9)
  secondari          altri pulsanti della barra: [(testo, funzione)]
Dopo averli cambiati chiama self.azioni_cambiate.emit(). La finestra chiama mostrata() a ogni ingresso.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class Contesto:
    """Ciò che le pagine condividono: l'ultimo `info` del motore e il progetto aperto (app.progetto.Progetto)."""
    def __init__(self):
        self.info = None
        self.progetto = None


class Pagina(QWidget):
    vai = Signal(str)               # chiave della pagina dove andare
    azioni_cambiate = Signal()      # la barra delle azioni va ridisegnata
    respira = Signal(bool)          # l'avatar "respira" durante un lavoro lungo (D046)

    titolo = ""
    testo_principale = ""
    destinazione = None
    aiuto = ""
    aiuto_livello = ""

    def __init__(self, contesto, parent=None):
        super().__init__(parent)
        self.contesto = contesto
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
    """Formatta un numero all'italiana (R11: l'interfaccia formatta, non calcola): 15.6 -> '15,6'."""
    testo = f"{x:,.{cifre}f}"
    return testo.replace(",", " ").replace(".", ",").replace(" ", ".")
