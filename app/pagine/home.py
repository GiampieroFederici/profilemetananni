"""Pagina "I miei progetti" (S5b, docs/interfaccia_S4.md §3): ritrovare e aprire i progetti; crearne uno nuovo.

Il nome del progetto nuovo si scrive nella pagina (già proposto, R4): "Nuovo progetto" lo crea con le regole
di progetto.nuovo e porta a "Campioni e prodotto".
"""
from datetime import date, datetime

from PySide6.QtWidgets import QGridLayout, QLineEdit, QPushButton, QVBoxLayout

from app import progetto
from app.pagine.base import Pagina, etichetta, riquadro
from app.pagine.progetto import STILE, pannello, svuota


class PaginaHome(Pagina):
    titolo = "I miei progetti"
    testo_principale = "Nuovo progetto"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.setStyleSheet(STILE)
        self.corpo.addWidget(etichetta("Un progetto raccoglie i campioni di un lotto o di uno studio, "
                                       "le scelte fatte e i risultati."))
        self.zona_motore = QVBoxLayout()
        self.corpo.addLayout(self.zona_motore)
        self.zona_elenco = QVBoxLayout()
        self.corpo.addLayout(self.zona_elenco)

        self.corpo.addSpacing(8)
        self.corpo.addWidget(etichetta("Nuovo progetto", "sottotitolo"))
        self.corpo.addWidget(etichetta("Nome del nuovo progetto", "etichetta_campo"))
        self.nome = QLineEdit()
        self.nome.setMaximumWidth(560)
        self.nome.setAccessibleName("Nome del nuovo progetto")
        self.nome.returnPressed.connect(self.azione_principale)
        self.corpo.addWidget(self.nome)
        self.corpo.addWidget(etichetta("Lo usi tu per ritrovarlo. Lettere senza accenti, numeri, punto, trattino e "
                                       "trattino basso, senza spazi: per esempio salame_lotto_12.", "nota"))
        self.errore = QVBoxLayout()
        self.corpo.addLayout(self.errore)

    def mostrata(self):
        svuota(self.zona_motore)
        if self.contesto.info is None:
            self.zona_motore.addWidget(riquadro(
                "Il motore non ha risposto.",
                "Puoi preparare i progetti, ma per l'analisi serve il motore: apri la pagina Motore in alto.",
                "avviso"))
        svuota(self.errore)
        self._elenco()
        if not self.nome.text():
            self.nome.setText(self._nome_proposto())

    def _nome_proposto(self):
        oggi = f"progetto_{date.today().isoformat()}"
        esistenti = {p.cartella.name for p in self._progetti()}
        radice = progetto.cartella_progetti()
        nome, n = oggi, 2
        while nome in esistenti or (radice / nome).exists():
            nome, n = f"{oggi}_{n}", n + 1
        return nome

    def _progetti(self):
        try:
            return progetto.elenco()
        except OSError:
            return []

    def _elenco(self):
        svuota(self.zona_elenco)
        progetti = self._progetti()
        if not progetti:
            self.zona_elenco.addWidget(riquadro(
                "Nessun progetto.", "Scrivi il nome qui sotto e premi Nuovo progetto.", "info"))
            self.zona_elenco.addWidget(etichetta("Primo avvio? Il motore si installa una volta sola: lo trovi in "
                                                 "alto, alla voce Motore.", "nota"))
            return
        p, s = pannello()
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(28)
        griglia.setVerticalSpacing(6)
        for colonna, testo in enumerate(("Progetto", "Stato", "Ultima modifica")):
            griglia.addWidget(etichetta(testo, "etichetta_campo"), 0, colonna)
        for riga, pr in enumerate(progetti, start=1):
            apri = QPushButton(pr.nome, objectName="apri")
            apri.setToolTip("Apri il progetto")
            apri.setAccessibleName(f"Apri il progetto {pr.nome}")
            apri.clicked.connect(lambda _=False, q=pr: self.apri(q))
            griglia.addWidget(apri, riga, 0)
            pronto = (pr.risultati / "risultati.json").is_file()
            griglia.addWidget(etichetta("Risultati pronti" if pronto else "Da avviare"), riga, 1)
            quando = datetime.fromtimestamp(pr.config.stat().st_mtime)
            griglia.addWidget(etichetta(f"{quando:%d/%m/%Y, %H:%M}"), riga, 2)
        griglia.setColumnStretch(3, 1)
        s.addLayout(griglia)
        self.zona_elenco.addWidget(p)
        self.zona_elenco.addWidget(etichetta("Premi il nome di un progetto per aprirlo.", "nota"))

    def apri(self, pr):
        self.contesto.progetto = pr
        self.vai.emit("risultati" if (pr.risultati / "risultati.json").is_file() else "campioni")

    def azione_principale(self):
        svuota(self.errore)
        nome = self.nome.text().strip()
        try:
            nuovo = progetto.nuovo(nome)
        except ValueError as e:
            self.errore.addWidget(riquadro("Questo nome non va bene.", str(e), "errore"))
            return
        except FileExistsError as e:
            self.errore.addWidget(riquadro(str(e), "Scegli un altro nome, oppure apri quello che c'è già "
                                           "dall'elenco qui sopra.", "errore"))
            return
        except OSError:
            self.errore.addWidget(riquadro("Non riesco a creare la cartella del progetto.",
                                           "Controlla di poter scrivere nella cartella Documenti.", "errore"))
            return
        nuovo.scrivi(progetto.base(nuovo.nome))      # config.yaml subito: così il progetto compare nell'elenco
        self.contesto.progetto = nuovo
        self.nome.clear()
        self.vai.emit("campioni")
