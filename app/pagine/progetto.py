"""Pagina "Campioni e prodotto": segnaposto dello scheletro S5a, la scrive S5b (docs/interfaccia_S4.md §3)."""
from app.pagine.base import Pagina, etichetta


class PaginaCampioni(Pagina):
    titolo = "Campioni e prodotto"
    testo_principale = "Avanti: scelte dell'analisi"
    destinazione = "scelte"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.corpo.addWidget(etichetta("Da dove vengono le read e che prodotto è (per scegliere l'ospite da togliere)."))
        self.corpo.addWidget(etichetta("Pagina ancora vuota: arriva con la sessione S5b.", "nota"))
