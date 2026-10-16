"""Pagina "Motore": segnaposto dello scheletro S5a, la scrive S5b (docs/interfaccia_S4.md §3.6).
Per ora mostra solo che `info` è arrivato dal motore (criterio di S5a)."""
from app.pagine.base import Pagina, etichetta, numero


class PaginaMotore(Pagina):
    titolo = "Motore"
    testo_principale = "Controlla il motore"
    aiuto = "Il controllo arriva con la sessione S5b."

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.principale_attivo = False
        self.corpo.addWidget(etichetta("Stato, database installati, controlla e installa."))
        self.stato = etichetta("", "sottotitolo")
        self.corpo.addWidget(self.stato)
        self.corpo.addWidget(etichetta("Pagina ancora vuota: arriva con la sessione S5b.", "nota"))

    def mostrata(self):
        i = self.contesto.info
        if i is None:
            self.stato.setText("Il motore non ha ancora risposto.")
        else:
            tipo = "di prova (finto)" if i.get("finto") else "installato"
            self.stato.setText(f"Il motore {tipo} risponde: {numero(i['ram_gb'])} GB di memoria, "
                               f"{i['processori']} processori, {numero(i['spazio_libero_gb'], 0)} GB liberi.")
