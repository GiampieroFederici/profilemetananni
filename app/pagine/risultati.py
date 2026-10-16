"""Pagina "Risultati": segnaposto dello scheletro S5a, la scrive S6 (docs/interfaccia_S4.md §3)."""
from app.pagine.base import Pagina, etichetta


class PaginaRisultati(Pagina):
    titolo = "Risultati"
    testo_principale = "Prevedi la sicurezza alimentare"
    destinazione = "sicurezza"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.corpo.addWidget(etichetta("Frase di sintesi, MetaPhlAn e Kraken separati, referto, citazioni."))
        self.corpo.addWidget(etichetta("Pagina ancora vuota: arriva con la sessione S6.", "nota"))
