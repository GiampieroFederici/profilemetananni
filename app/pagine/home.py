"""Pagina "I miei progetti" (S5b, docs/interfaccia_S4.md §3): ritrovare e aprire i progetti; crearne uno nuovo.

Il nome del progetto nuovo si scrive nella pagina (già proposto, R4): "Nuovo progetto" lo crea con le regole
di progetto.nuovo e porta a "Campioni e prodotto". Mentre un'analisi gira si lavora solo sul suo progetto:
gli altri non si aprono e non se ne creano di nuovi (si spiega perché).
"Prova il campione d'esempio" (A2) crea o riapre il progetto d'esempio con il mini-campione che il motore annuncia
in `info.esempio`: si arriva alle scelte già pronte, e un clic su "Avvia l'analisi" basta.
"""
from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLineEdit, QPushButton, QVBoxLayout

from app import progetto
from app.lingua import N_, _
from app.pagine.base import Pagina, etichetta, pannello, riquadro, svuota
from app.pagine.progetto import regola

NOME_ESEMPIO = "esempio_SF3RAt7"


class PaginaHome(Pagina):
    titolo = N_("I miei progetti")
    testo_principale = N_("Nuovo progetto")

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.corpo.addWidget(etichetta(_("Un progetto raccoglie i campioni di un lotto o di uno studio, "
                                         "le scelte fatte e i risultati.")))
        self.zona_motore = QVBoxLayout()
        self.corpo.addLayout(self.zona_motore)
        self.zona_elenco = QVBoxLayout()
        self.corpo.addLayout(self.zona_elenco)
        self.errore_elenco = QVBoxLayout()        # vicino all'elenco (R9)
        self.corpo.addLayout(self.errore_elenco)

        self.esempio, s = pannello(_("Vuoi provare subito?"))
        self.frase_esempio = etichetta("")
        s.addWidget(self.frase_esempio)
        b = QPushButton(_("Prova il campione d'esempio"), objectName="secondario")
        b.clicked.connect(self.prova_esempio)
        s.addWidget(b, 0, Qt.AlignLeft)
        self.errore_esempio = QVBoxLayout()
        s.addLayout(self.errore_esempio)
        self.corpo.addWidget(self.esempio)

        self.corpo.addSpacing(8)
        self.corpo.addWidget(etichetta(_("Nuovo progetto"), "sottotitolo"))
        self.corpo.addWidget(etichetta(_("Nome del nuovo progetto"), "etichetta_campo"))
        self.nome = QLineEdit()
        self.nome.setMaximumWidth(560)
        self.nome.setAccessibleName(_("Nome del nuovo progetto"))
        self.nome.returnPressed.connect(self.azione_principale)
        self.corpo.addWidget(self.nome)
        self.corpo.addWidget(etichetta(_("Lo usi tu per ritrovarlo. Lettere senza accenti, numeri, punto, trattino e "
                                         "trattino basso, senza spazi: per esempio salame_lotto_12."), "nota"))
        self.errore = QVBoxLayout()
        self.corpo.addLayout(self.errore)

    def mostrata(self):
        svuota(self.zona_motore)
        if self.contesto.info is None:
            self.zona_motore.addWidget(riquadro(
                _("Il motore non ha risposto."),
                _("Puoi preparare i progetti, ma per l'analisi serve il motore: apri la pagina Motore in alto."),
                "avviso"))
        corsa = self.contesto.progetto_in_analisi
        if corsa is not None:
            self.zona_motore.addWidget(riquadro(
                _("Un'analisi è in corso sul progetto {nome}.", nome=corsa.nome),
                _("Finché non finisce puoi aprire solo quel progetto. Per aprirne un altro, prima ferma l'analisi."),
                "avviso"))
        svuota(self.errore)
        svuota(self.errore_elenco)
        svuota(self.errore_esempio)
        es = (self.contesto.info or {}).get("esempio")
        self.esempio.setVisible(bool(es))
        if es:
            self.frase_esempio.setText(es["frase"] + _(" Lo analizzo con le scelte consigliate: vedi come funziona "
                                                       "senza preparare nulla."))
        self._elenco()
        if not self.nome.text():
            self.nome.setText(self._nome_proposto())

    def _nome_proposto(self):
        oggi = f"{_('progetto')}_{date.today().isoformat()}"   # nome di cartella proposto: project_... con l'inglese
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
                _("Nessun progetto."), _("Scrivi il nome qui sotto e premi Nuovo progetto."), "info"))
            self.zona_elenco.addWidget(etichetta(_("Primo avvio? Il motore si installa una volta sola: lo trovi in "
                                                   "alto, alla voce Motore."), "nota"))
            return
        p, s = pannello()
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(28)
        griglia.setVerticalSpacing(6)
        for colonna, testo in enumerate((_("Progetto"), _("Stato"), _("Ultima modifica"))):
            griglia.addWidget(etichetta(testo, "etichetta_campo"), 0, colonna)
        for riga, pr in enumerate(progetti, start=1):
            apri = QPushButton(pr.nome, objectName="apri")
            apri.setToolTip(_("Apri il progetto"))
            apri.setAccessibleName(_("Apri il progetto {nome}", nome=pr.nome))
            apri.clicked.connect(lambda _=False, q=pr: self.apri(q))
            griglia.addWidget(apri, riga, 0)
            pronto = (pr.risultati / "risultati.json").is_file()
            corsa = self.contesto.progetto_in_analisi
            gira = corsa is not None and pr.cartella.resolve() == corsa.cartella.resolve()
            griglia.addWidget(etichetta(_("Analisi in corso") if gira else _("Analisi interrotta") if pr.interrotta
                                        else _("Risultati pronti") if pronto else _("Da avviare")), riga, 1)
            quando = datetime.fromtimestamp(pr.config.stat().st_mtime)
            griglia.addWidget(etichetta(f"{quando:%d/%m/%Y, %H:%M}"), riga, 2)
        griglia.setColumnStretch(3, 1)
        s.addLayout(griglia)
        self.zona_elenco.addWidget(p)
        self.zona_elenco.addWidget(etichetta(_("Premi il nome di un progetto per aprirlo."), "nota"))

    def occupato(self, pr=None):
        """True (e lo spiega vicino a dove si è premuto) se un'analisi gira su un progetto diverso da pr."""
        corsa = self.contesto.progetto_in_analisi
        if corsa is None or (pr is not None and pr.cartella.resolve() == corsa.cartella.resolve()):
            return False
        zona = self.errore if pr is None else self.errore_elenco
        svuota(zona)
        zona.addWidget(riquadro(_("Un'analisi è in corso sul progetto {nome}.", nome=corsa.nome),
                                _("Prima fermala dalla pagina Analisi in corso, poi apri o crea l'altro progetto."),
                                "errore"))
        return True

    def apri(self, pr):
        if self.occupato(pr):
            return
        corsa = self.contesto.progetto_in_analisi
        if corsa is not None:                      # è il progetto della corsa: si torna a seguirla
            self.contesto.progetto = corsa
            self.vai.emit("esecuzione")
            return
        self.contesto.progetto = pr
        self.vai.emit("esecuzione" if pr.interrotta else "risultati" if (pr.risultati / "risultati.json").is_file()
                      else "campioni")

    def prova_esempio(self):
        """Crea il progetto d'esempio (o lo riapre) e porta alle scelte; con i risultati pronti, ai risultati."""
        es = (self.contesto.info or {}).get("esempio")
        if not es or self.occupato():
            return
        svuota(self.errore_esempio)
        cartella = progetto.cartella_progetti() / NOME_ESEMPIO
        if (cartella / "config.yaml").is_file():
            pr = progetto.Progetto(cartella)
            if self.contesto.progetto_in_analisi is None and not (pr.risultati / "risultati.json").is_file():
                self.contesto.progetto = pr
                self.vai.emit("scelte")
            else:
                self.apri(pr)
            return
        try:
            pr = progetto.nuovo(NOME_ESEMPIO)
        except (OSError, ValueError):
            self.errore_esempio.addWidget(riquadro(_("Non riesco a creare il progetto d'esempio."),
                                                   _("Controlla di poter scrivere nella cartella Documenti."), "errore"))
            return
        cfg = progetto.base(pr.nome)
        cfg["data_source"] = "local"
        cfg["paths"]["local_reads_dir"] = es["cartella"]          # già come la vede il motore
        cfg["hosts"] = list(regola(self.contesto.info, es["prodotto"])[0])
        cfg["app"] = {"prodotto": es["prodotto"], "cartella_read": "", "esempio": True}
        pr.scrivi(cfg)
        self.contesto.progetto = pr
        self.vai.emit("scelte")

    def azione_principale(self):
        if self.occupato():
            return
        svuota(self.errore)
        nome = self.nome.text().strip()
        try:
            nuovo = progetto.nuovo(nome)
        except ValueError as e:
            self.errore.addWidget(riquadro(_("Questo nome non va bene."), str(e), "errore"))
            return
        except FileExistsError as e:
            self.errore.addWidget(riquadro(str(e), _("Scegli un altro nome, oppure apri quello che c'è già "
                                             "dall'elenco qui sopra."), "errore"))
            return
        except OSError:
            self.errore.addWidget(riquadro(_("Non riesco a creare la cartella del progetto."),
                                           _("Controlla di poter scrivere nella cartella Documenti."), "errore"))
            return
        nuovo.scrivi(progetto.base(nuovo.nome))      # config.yaml subito: così il progetto compare nell'elenco
        self.contesto.progetto = nuovo
        self.nome.clear()
        self.vai.emit("campioni")
