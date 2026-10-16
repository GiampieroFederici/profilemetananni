"""Pagina "Sicurezza alimentare": segnaposto dello scheletro S5a, la scrive S6 (docs/interfaccia_S4.md §3)."""
from app.pagine.base import Pagina, etichetta


class PaginaSicurezza(Pagina):
    titolo = "Sicurezza alimentare"
    testo_principale = "Aggiungi al referto"
    destinazione = "risultati"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.corpo.addWidget(etichetta("Scenari di Listeria con i modelli FSSP."))
        self.corpo.addWidget(etichetta("Pagina ancora vuota: arriva con la sessione S6.", "nota"))
