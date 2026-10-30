"""Pagina "I miei progetti" (S5b, docs/interfaccia_S4.md §3): ritrovare e aprire i progetti; crearne uno nuovo.

Il nome del progetto nuovo si scrive nella pagina (già proposto, R4): "Nuovo progetto" lo crea con le regole
di progetto.nuovo e porta a "Campioni e prodotto". Mentre un'analisi gira si lavora solo sul suo progetto:
gli altri non si aprono e non se ne creano di nuovi (si spiega perché).
"Prova il campione d'esempio" (A2) crea o riapre il progetto d'esempio con il mini-campione che il motore annuncia
in `info.esempio`: si arriva alle scelte già pronte, e un clic su "Avvia l'analisi" basta.
"Versione e aggiornamenti" (R12): versione installata, "Cerca aggiornamenti" (Release latest di GitHub, app/aggiorna.py),
"Aggiorna adesso" solo dopo il Sì, "Torna alla versione precedente" se c'è; tutto spento mentre il motore lavora.
"""
import shutil
from datetime import date, datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLineEdit, QMessageBox, QProgressDialog, QPushButton, QVBoxLayout

from app import aggiorna, progetto
from app.lingua import N_, _
from app.pagine.base import Pagina, etichetta, pannello, riquadro, svuota
from app.pagine.progetto import regola

NOME_ESEMPIO = "esempio_SF3RAt7"


def _prova(funzione):
    """Il risultato di funzione() oppure l'ErroreAggiorna da mostrare (anche per un errore imprevisto). La rete è
    quella di Qt (punto 6): aspetta con un suo ciclo di eventi, la finestra resta viva senza fili a parte."""
    try:
        return funzione()
    except aggiorna.ErroreAggiorna as e:
        return e
    except Exception:                   # imprevisto: lo si dice, l'app non si ferma
        return aggiorna.ErroreAggiorna("RISPOSTA", _("Il controllo degli aggiornamenti non è riuscito."),
                                       _("Riprova più tardi."))


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

        self.corpo.addSpacing(8)
        p, s = pannello(_("Versione e aggiornamenti"))
        s.addWidget(etichetta(_("Versione installata: {versione}.", versione=aggiorna.VERSIONE)))
        riga = QHBoxLayout()
        self.cerca = QPushButton(_("Cerca aggiornamenti"), objectName="secondario")
        self.cerca.clicked.connect(self.cerca_aggiornamenti)
        self.indietro = QPushButton(_("Torna alla versione precedente"), objectName="secondario")
        self.indietro.clicked.connect(self.torna_indietro)
        riga.addWidget(self.cerca)
        riga.addWidget(self.indietro)
        riga.addStretch(1)
        s.addLayout(riga)
        self.nota_occupato = etichetta(_("Mentre il motore lavora non si aggiorna: aspetta che finisca."), "nota")
        s.addWidget(self.nota_occupato)
        self.zona_aggiorna = QVBoxLayout()
        s.addLayout(self.zona_aggiorna)
        self.corpo.addWidget(p)
        self.release, self.barra_scarico, self._in_rete, self._fermo = None, None, False, False

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
        self._stato_aggiorna()

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
            apri = QPushButton(objectName="apri")
            apri.setText(pr.nome if len(pr.nome) <= 26 else f"{pr.nome[:12]}…{pr.nome[-12:]}")   # B2-2b: nomi lunghi
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

    # ---------------- versione e aggiornamenti (R12) ----------------
    def motore_occupato(self):
        """Analisi, installazione o altro lavoro del motore in corso: intanto non si aggiorna (la finestra lo sa)."""
        f = self.window()
        return f.occupato() if hasattr(f, "occupato") else self.contesto.progetto_in_analisi is not None

    def _stato_aggiorna(self):
        occupato = self.motore_occupato()
        self.cerca.setEnabled(not (occupato or self._in_rete))
        self.indietro.setVisible(aggiorna.precedente() is not None)
        self.indietro.setEnabled(not (occupato or self._in_rete))
        self.nota_occupato.setVisible(occupato)

    def conferma(self, titolo, testo):
        return QMessageBox.question(self, titolo, testo) == QMessageBox.Yes

    def cerca_aggiornamenti(self):
        svuota(self.zona_aggiorna)
        self._stato_aggiorna()
        if self.motore_occupato():
            return
        self._in_rete = True
        self._stato_aggiorna()
        self.zona_aggiorna.addWidget(etichetta(_("Controllo su GitHub..."), "nota"))
        self._controllato(_prova(lambda: aggiorna.controlla()))

    def _controllato(self, r):
        self._in_rete = False
        svuota(self.zona_aggiorna)
        self._stato_aggiorna()
        if isinstance(r, aggiorna.ErroreAggiorna):
            self.zona_aggiorna.addWidget(riquadro(r.messaggio, r.cosa_fare, "avviso"))
            return
        self.release = r
        if r["stato"] == "uguale":
            self.zona_aggiorna.addWidget(riquadro(_("Hai già l'ultima versione ({versione}).", versione=r["nuova"]),
                                                  "", "info"))
            return
        if r["stato"] == "vecchia":
            self.zona_aggiorna.addWidget(riquadro(
                _("La versione installata ({installata}) è più nuova di quella pubblicata ({nuova}): non c'è nulla "
                  "da aggiornare.", installata=r["installata"], nuova=r["nuova"]), "", "info"))
            return
        self.zona_aggiorna.addWidget(riquadro(_("È disponibile la versione {nuova}.", nuova=r["nuova"]),
                                              _("Versione installata: {versione}.", versione=r["installata"]), "info"))
        if r["novita"]:
            self.zona_aggiorna.addWidget(etichetta(_("Novità"), "etichetta_campo"))
            novita = etichetta(r["novita"])
            novita.setTextFormat(Qt.PlainText)       # testo della Release: mai interpretato come HTML
            self.zona_aggiorna.addWidget(novita)
        if r["pacchetto"] is None:
            self.zona_aggiorna.addWidget(riquadro(_("Il pacchetto della versione nuova non è ancora pronto."),
                                                  _("Riprova più tardi."), "avviso"))
        elif not aggiorna.puo_installare():
            self.zona_aggiorna.addWidget(riquadro(
                _("Da questa copia del programma posso solo controllare."),
                _("Per aggiornare, scarica lo zip dalla pagina della Release su GitHub e installalo con il doppio "
                  "clic."), "avviso"))
        else:
            b = QPushButton(_("Aggiorna adesso"), objectName="secondario")
            b.clicked.connect(self.aggiorna_adesso)
            self.zona_aggiorna.addWidget(b, 0, Qt.AlignLeft)

    def aggiorna_adesso(self):
        r = self.release
        if self.motore_occupato() or not r or not r.get("pacchetto"):
            self._stato_aggiorna()
            return
        mb = max(1, round(r["pacchetto"]["byte"] / 1e6))
        if not self.conferma(_("Aggiorna ProfileMetaNanni"), _(
                "Scarico la versione {nuova} (circa {mb} MB). Poi il programma si chiude, si aggiorna e si riapre da "
                "solo.\n\nSe il motore nuovo ha bisogno di altri database, prima di scaricarli te lo chiedo. I tuoi "
                "progetti, i risultati e le impostazioni restano dove sono; se qualcosa non va, puoi tornare alla "
                "versione precedente.\n\nProcedo?", nuova=r["nuova"], mb=mb)):
            return
        self._in_rete, self._fermo = True, False
        self._stato_aggiorna()
        self.barra_scarico = QProgressDialog(_("Scarico la versione {nuova}...", nuova=r["nuova"]), _("Annulla"),
                                             0, 100, self)
        self.barra_scarico.setWindowModality(Qt.WindowModal)     # intanto non si avvia un'analisi
        self.barra_scarico.setMinimumDuration(0)
        self.barra_scarico.setAutoClose(False)
        self.barra_scarico.setAutoReset(False)
        self.barra_scarico.canceled.connect(self._annulla_scarico)
        self.barra_scarico.show()
        pacchetto, lavoro = r["pacchetto"], aggiorna.cartella_lavoro()

        def scarica_ed_estrai():
            shutil.rmtree(lavoro, ignore_errors=True)            # resti di un aggiornamento passato
            zip_ = aggiorna.scarica(pacchetto, lavoro, self._passo, lambda: self._fermo)
            return aggiorna.estrai(zip_, lavoro)
        self._scaricato(_prova(scarica_ed_estrai))

    def _annulla_scarico(self):
        self._fermo = True

    def _passo(self, fatti, totali):
        if self.barra_scarico is not None and totali:
            self.barra_scarico.setValue(int(100 * fatti / totali))

    def _scaricato(self, r):
        self._in_rete = False
        if self.barra_scarico is not None:
            self.barra_scarico.hide()
            self.barra_scarico.deleteLater()
            self.barra_scarico = None
        svuota(self.zona_aggiorna)
        self._stato_aggiorna()
        if isinstance(r, aggiorna.ErroreAggiorna):
            self.zona_aggiorna.addWidget(riquadro(r.messaggio, r.cosa_fare, "avviso"))
            return
        if self.motore_occupato():
            self.zona_aggiorna.addWidget(riquadro(_("Il motore ha cominciato un lavoro: non aggiorno adesso."),
                                                  _("Riprova quando ha finito."), "avviso"))
            return
        self._lancia(r.joinpath(*aggiorna.PS1), False)

    def torna_indietro(self):
        script = aggiorna.precedente()
        if script is None or self.motore_occupato():
            self._stato_aggiorna()
            return
        if self.conferma(_("Torna alla versione precedente"), _(
                "Il programma si chiude, rimette la versione di prima (programma e motore) e si riapre. I tuoi "
                "progetti, i risultati e le impostazioni restano dove sono.\n\nProcedo?")):
            self._lancia(script, True)

    def _lancia(self, script, ripristina):
        """Lo script aspetta che l'app sia chiusa prima di toccarla: qui si lancia e si chiude la finestra."""
        try:
            aggiorna.avvia_script(script, ripristina)
        except OSError:
            self.zona_aggiorna.addWidget(riquadro(_("Non riesco ad avviare l'aggiornamento."),
                                                  _("Scarica la versione nuova dalla pagina della Release su GitHub."),
                                                  "errore"))
            return
        self.window().close()
