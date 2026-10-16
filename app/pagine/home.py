"""Pagina "I miei progetti": segnaposto dello scheletro S5a, la scrive S5b (docs/interfaccia_S4.md §3)."""
from app.pagine.base import Pagina, etichetta


class PaginaHome(Pagina):
    titolo = "I miei progetti"
    testo_principale = "Nuovo progetto"
    destinazione = "campioni"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.corpo.addWidget(etichetta("Ritrovare e aprire i progetti; crearne uno nuovo."))
        self.corpo.addWidget(etichetta("Pagina ancora vuota: arriva con la sessione S5b.", "nota"))
