"""Pagina "Analisi in corso": segnaposto dello scheletro S5a, la scrive S6 (docs/interfaccia_S4.md §3)."""
from app.pagine.base import Pagina, etichetta


class PaginaEsecuzione(Pagina):
    titolo = "Analisi in corso"
    testo_principale = "Avanti: risultati"
    destinazione = "risultati"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.corpo.addWidget(etichetta("Barra, tempo che manca, passi; si può fermare."))
        self.corpo.addWidget(etichetta("Pagina ancora vuota: arriva con la sessione S6.", "nota"))
