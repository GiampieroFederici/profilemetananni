"""Pagina "Scelte dell'analisi": segnaposto dello scheletro S5a, la scrive S5b (docs/interfaccia_S4.md §3)."""
from app.pagine.base import Pagina, etichetta


class PaginaScelte(Pagina):
    titolo = "Scelte dell'analisi"
    testo_principale = "Avvia l'analisi"
    destinazione = "esecuzione"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.corpo.addWidget(etichetta("Scelte consigliate già pronte e stima del tempo prima di partire."))
        self.corpo.addWidget(etichetta("Pagina ancora vuota: arriva con la sessione S5b.", "nota"))
