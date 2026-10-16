"""Pagina "Come citare": segnaposto dello scheletro S5a, la scrive S5b (docs/interfaccia_S4.md §3)."""
from app.pagine.base import Pagina, etichetta


class PaginaCrediti(Pagina):
    titolo = "Come citare"
    testo_principale = "Torna ai progetti"
    destinazione = "home"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.corpo.addWidget(etichetta("Tutte le fonti degli strumenti e dei database (D036)."))
        self.corpo.addWidget(etichetta("Pagina ancora vuota: arriva con la sessione S5b.", "nota"))
