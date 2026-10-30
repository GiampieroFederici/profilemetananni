"""Pagina "Campioni e prodotto" (S5b, docs/interfaccia_S4.md §3.1): da dove vengono le read e che prodotto è.

Il prodotto (o l'ambiente) propone l'ospite da togliere: la regola la dà il motore (`info.prodotti`, System One v0,
contratto v0.3), con il testo del menu (`testo`) e il segno `sperimentale` degli ambienti nuovi; la tabella PRODOTTI
qui sotto fa da ripiego se il motore non ha risposto. R8 (30/10): la persona può cambiare l'ospite proposto (ospiti
pronti, "nessuno", o un ospite che aggiunge lei con il codice NCBI o un file FASTA, FinestraOspite). Salva in
config.yaml con Progetto.scrivi; i percorsi vanno scritti come li vede il motore (percorso_per_motore), perché il
motore li legge così come sono.
"""
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                               QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from app import progetto
from app.lingua import N_, _
from app.motore import percorso_per_motore
from app.pagine.base import Pagina, Scelta, etichetta, numero, riga_di_scelte, riquadro, svuota

# prodotto -> (testo nel menu, ospiti oltre all'uomo (nomi di refs/hosts.tsv), frase che dice perché, livello);
# ospiti, frase, perché e livello sono il ripiego di info.prodotti (stessi testi, motore/system_one.py)
# D074: maiale, bovino, pecora, altro (il pollo no: il suo indice non è nel motore installato, D021).
PRODOTTI = {
    "maiale": (N_("Salume di maiale (salame, salsiccia, prosciutto...)"), ["sus_scrofa"],
               N_("Toglierò il DNA del maiale e quello umano."),
               N_("Sono la gran parte delle read di un salume e non dicono nulla dei taxa del prodotto. "
                  "Il DNA umano si toglie sempre."), "info"),
    "bovino": (N_("Prodotto di bovino (bresaola, carne secca...)"), ["bos_taurus"],
               N_("Toglierò il DNA del bovino e quello umano."),
               N_("Sono la gran parte delle read di un prodotto di carne e non dicono nulla dei taxa del prodotto. "
                  "Il DNA umano si toglie sempre."), "info"),
    "pecora": (N_("Prodotto di pecora o agnello"), ["ovis_aries"],
               N_("Toglierò il DNA della pecora e quello umano."),
               N_("Sono la gran parte delle read di un prodotto di carne e non dicono nulla dei taxa del prodotto. "
                  "Il DNA umano si toglie sempre."), "info"),
    "altro": (N_("Altro o misto"), [],
              N_("Toglierò solo il DNA umano."),
              N_("Se il prodotto contiene carne di maiale, bovino o pecora, sceglila qui sopra: senza, molte read "
                 "della carne finiscono assegnate per errore a qualche taxon."), "avviso"),
}


# ospiti pronti (R8, D167): chiave scritta in hosts (refs/hosts.tsv) e testo del menu; NESSUNO = hosts vuoto.
# L'uomo (GRCh38) si toglie sempre (filter_human): "Uomo" e "Nessuno" tolgono tutti e due solo il DNA umano.
NESSUNO = "nessuno"
OSPITI = [("sus_scrofa", N_("Maiale (Sus scrofa)")), ("bos_taurus", N_("Bovino (Bos taurus)")),
          ("ovis_aries", N_("Pecora (Ovis aries)")), ("grch38", N_("Uomo (Homo sapiens)")),
          ("vitis_vinifera", N_("Vite (Vitis vinifera)")), (NESSUNO, N_("Nessuno"))]
INSTALLATI = {"sus_scrofa", "bos_taurus", "ovis_aries"}
VITE_BASI = 494_873_210          # GCF_030704535.1 (NCBI Datasets, 30/10)


def regola(info, chiave):
    """(ospiti, frase, perché, livello) del prodotto: da info.prodotti del motore, altrimenti da PRODOTTI."""
    for r in (info or {}).get("prodotti") or []:
        if r.get("prodotto") == chiave:
            return list(r["ospiti"]), r["frase"], r["perche"], r["livello"]
    ospiti, frase, perche, livello = PRODOTTI.get(chiave, PRODOTTI["altro"])[1:]
    return ospiti, _(frase), _(perche), livello


def voci_prodotti(info):
    """[(chiave, testo del menu)]: da info.prodotti (ambienti nuovi compresi), altrimenti da PRODOTTI."""
    regole = [r for r in (info or {}).get("prodotti") or [] if r.get("prodotto")]
    if not regole:
        return [(k, _(v[0])) for k, v in PRODOTTI.items()]
    out = []
    for r in regole:
        k = r["prodotto"]
        testo = r.get("testo") or (_(PRODOTTI[k][0]) if k in PRODOTTI else k)
        out.append((k, testo + (_(" (sperimentale)") if r.get("sperimentale") else "")))
    return out


def stima_in_parole(stima):
    return _("{tempo} e {ram} di memoria", tempo=progetto.durata_in_parole(stima["secondi"]),
             ram=progetto.spazio_in_parole(stima["ram_gb"]))


def prodotto_da_ospiti(ospiti):
    """Il prodotto che corrisponde agli ospiti già scritti nel progetto (per riaprirlo)."""
    for chiave, (_, o, *_resto) in PRODOTTI.items():
        if list(ospiti or []) == o:
            return chiave
    return "altro"


def stringibile(tendina):
    """B4-1: la tendina si stringe con la finestra (la pagina Campioni restava larga 559 px); l'elenco che si apre
    resta largo quanto la voce più lunga."""
    tendina.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    tendina.setMinimumContentsLength(12)
    tendina.model().rowsInserted.connect(
        lambda *_x: tendina.view().setMinimumWidth(tendina.view().sizeHintForColumn(0) + 24))


class PaginaCampioni(Pagina):
    titolo = N_("Campioni e prodotto")
    testo_principale = N_("Avanti: scelte dell'analisi")

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.cartella = None
        self.corpo.addWidget(etichetta(_("Dimmi da dove arrivano le read e che prodotto stai analizzando. "
                                         "Al resto penso io.")))
        self.senza_progetto = riquadro(_("Nessun progetto aperto."),
                                       _("Apri un progetto o creane uno nuovo nella pagina I miei progetti."), "avviso")
        self.corpo.addWidget(self.senza_progetto)
        self.esempio = False                             # progetto d'esempio (home): read e prodotto già decisi
        self.avviso_esempio = riquadro(_("Questo è il progetto d'esempio."),
                                       _("Le read sono già nel motore e il prodotto è un salame di maiale: qui non c'è "
                                         "nulla da scegliere. Premi Avanti."), "info")
        self.corpo.addWidget(self.avviso_esempio)

        self.corpo.addSpacing(8)
        self.corpo.addWidget(etichetta(_("Dove sono le read?"), "sottotitolo"))
        self.gruppo_fonte = QButtonGroup(self)
        self.scelta_pc = Scelta(_("Sul mio computer"), _("File che ti ha mandato il laboratorio di sequenziamento "
                                                         "(finiscono in .fastq.gz)."), self.gruppo_fonte)
        self.scelta_ncbi = Scelta(_("In un archivio pubblico"), _("Le scarico io da NCBI o ENA con il loro codice "
                                                                  "(per esempio SRR4875279)."), self.gruppo_fonte)
        self.corpo.addLayout(riga_di_scelte(self.scelta_pc, self.scelta_ncbi))

        # sul mio computer: una cartella; le coppie R1/R2 le trovo da solo
        self.zona_pc = QFrame()
        s = QVBoxLayout(self.zona_pc)
        s.setContentsMargins(0, 4, 0, 0)
        s.addWidget(etichetta(_("Cartella delle read"), "etichetta_campo"))
        riga = QHBoxLayout()
        b = QPushButton(_("Scegli la cartella..."), objectName="secondario")
        b.clicked.connect(self.scegli_cartella)
        riga.addWidget(b)
        self.nome_cartella = etichetta("")
        riga.addWidget(self.nome_cartella, 1)
        s.addLayout(riga)
        self.esito_cartella = QVBoxLayout()
        s.addLayout(self.esito_cartella)
        s.addWidget(etichetta(_("Si apre nella cartella Documenti, o nell'ultima che hai usato. Trovo da solo le "
                                "coppie di file (R1 e R2) di ogni campione."), "nota"))
        self.corpo.addWidget(self.zona_pc)

        # archivio pubblico: codici, uno per riga, con il conteggio dei validi
        self.zona_ncbi = QFrame()
        s = QVBoxLayout(self.zona_ncbi)
        s.setContentsMargins(0, 4, 0, 0)
        s.addWidget(etichetta(_("Codici dei campioni, uno per riga"), "etichetta_campo"))
        self.testo_codici = QPlainTextEdit()
        self.testo_codici.setFixedHeight(110)
        self.testo_codici.setMaximumWidth(560)
        self.testo_codici.setTabChangesFocus(True)
        self.testo_codici.setAccessibleName(_("Codici dei campioni, uno per riga"))
        self.testo_codici.textChanged.connect(self._conta_codici)
        s.addWidget(self.testo_codici)
        self.conteggio = etichetta("", "nota")
        s.addWidget(self.conteggio)
        self.corpo.addWidget(self.zona_ncbi)

        self.errore = QVBoxLayout()           # errore vicino ai campi (R8, R9)
        self.corpo.addLayout(self.errore)

        self.corpo.addSpacing(8)
        self.corpo.addWidget(etichetta(_("Che prodotto è?"), "sottotitolo"))
        self.prodotto = QComboBox()
        self.prodotto.setMaximumWidth(560)
        stringibile(self.prodotto)
        self.prodotto.setAccessibleName(_("Prodotto"))
        self._riempi_prodotti()
        self.prodotto.currentIndexChanged.connect(self._ospite)
        self.corpo.addWidget(self.prodotto)
        self.zona_ospite = QVBoxLayout()
        self.corpo.addLayout(self.zona_ospite)

        # R8: l'ospite proposto dal prodotto si può cambiare
        self.corpo.addWidget(etichetta(_("DNA dell'ospite da togliere"), "etichetta_campo"))
        riga = QHBoxLayout(objectName="riga_di_scelte")   # B4-1: stretta, il pulsante va sotto (impila)
        self.ospite = QComboBox()
        self.ospite.setMaximumWidth(400)
        stringibile(self.ospite)
        self.ospite.setAccessibleName(_("DNA dell'ospite da togliere"))
        self.ospite.activated.connect(self._ospite_cambiato)
        riga.addWidget(self.ospite, 1, Qt.AlignTop)     # stesso bordo in alto: per il Tab sono sulla stessa riga
        self.pulsante_ospite = QPushButton(_("Aggiungi un ospite..."), objectName="secondario")
        self.pulsante_ospite.clicked.connect(self.aggiungi_ospite)
        riga.addWidget(self.pulsante_ospite, 0, Qt.AlignTop)
        riga.addStretch(1)
        self.corpo.addLayout(riga)
        self.nota_ospite = etichetta("", "nota")
        self.corpo.addWidget(self.nota_ospite)
        self.ospite_scelto = None        # None = quello proposto dal prodotto
        self.personali_progetto = {}     # ospiti_personali già nel config.yaml del progetto (come li vede il motore)

        self.scelta_pc.scelta.connect(self._fonte)
        self.scelta_ncbi.scelta.connect(self._fonte)
        self.scelta_ncbi.pulsante.setChecked(True)
        self._ospite()

    # ---------------- stato della pagina ----------------
    def mostrata(self):
        p = self.contesto.progetto
        self.senza_progetto.setVisible(p is None)
        self.testo_principale = _("Avanti: scelte dell'analisi") if p else _("Vai ai miei progetti")
        self.azioni_cambiate.emit()
        svuota(self.errore)
        self._riempi_prodotti()                          # info.prodotti può essere arrivato dopo la costruzione
        self._ospite()
        cfg = p.leggi() if p else {}
        app = cfg.get("app") if isinstance(cfg.get("app"), dict) else {}
        self.esempio = bool(app.get("esempio"))
        self.avviso_esempio.setVisible(self.esempio)
        for w in (self.scelta_pc, self.scelta_ncbi, self.prodotto, self.ospite, self.pulsante_ospite):
            w.setEnabled(not self.esempio)
        if p is None:
            return
        self.prodotto.setCurrentIndex(max(0, self.prodotto.findData(app.get("prodotto")
                                                                    or prodotto_da_ospiti(cfg.get("hosts", [])))))
        voci = cfg.get("ospiti_personali")
        self.personali_progetto = voci if isinstance(voci, dict) else {}
        self.ospite_scelto = app.get("ospite") or None
        self._riempi_ospiti()
        codici = p.codici_campioni.read_text(encoding="utf-8") if p.codici_campioni.is_file() else ""
        self.testo_codici.setPlainText(codici.strip())
        self.cartella = None
        self.nome_cartella.setText("")
        svuota(self.esito_cartella)
        if app.get("cartella_read") and Path(app["cartella_read"]).is_dir():
            self.usa_cartella(app["cartella_read"])
        (self.scelta_pc if cfg.get("data_source") == "local" else self.scelta_ncbi).pulsante.setChecked(True)
        if self.esempio:                                 # la cartella sta dentro il motore: niente da mostrare
            self.zona_pc.setVisible(False)
            self.zona_ncbi.setVisible(False)

    def _fonte(self):
        pc = self.scelta_pc.pulsante.isChecked()
        self.zona_pc.setVisible(pc)
        self.zona_ncbi.setVisible(not pc)
        svuota(self.errore)

    # ---------------- prodotto e ospite (R8) ----------------
    def _riempi_prodotti(self):
        attuale = self.prodotto.currentData()
        self.prodotto.blockSignals(True)
        self.prodotto.clear()
        for chiave, testo in voci_prodotti(self.contesto.info):
            self.prodotto.addItem(testo, chiave)
        self.prodotto.setCurrentIndex(max(0, self.prodotto.findData(attuale)))
        self.prodotto.blockSignals(False)

    def _proposta(self):
        """L'ospite che il prodotto propone (il primo dei suoi ospiti, o NESSUNO)."""
        ospiti = regola(self.contesto.info, self.prodotto.currentData())[0]
        return ospiti[0] if ospiti else NESSUNO

    def _personali(self):
        """{nome: voce} degli ospiti aggiunti: quelli già nel progetto, poi l'elenco della persona (che vince)."""
        out = {n: v for n, v in self.personali_progetto.items() if isinstance(v, dict)}
        out.update(progetto.ospiti_personali())
        return out

    def _riempi_ospiti(self):
        proposta = self._proposta()
        voci = [(k, _(t)) for k, t in OSPITI]
        if proposta not in dict(voci):
            voci.insert(0, (proposta, proposta))
        voci += [(n, _("{nome} (aggiunto da te: {fonte})", nome=n,
                       fonte=v.get("accession") or Path(str(v.get("fasta", ""))).name))
                 for n, v in self._personali().items()]
        if self.ospite_scelto not in dict(voci):         # ospite che non c'è più: torna a quello proposto
            self.ospite_scelto = None
        self.ospite.blockSignals(True)
        self.ospite.clear()
        for k, testo in voci:
            self.ospite.addItem(testo + (_(" (consigliato)") if k == proposta else ""), k)
        self.ospite.setCurrentIndex(max(0, self.ospite.findData(self.ospite_scelto or proposta)))
        self.ospite.blockSignals(False)
        self._mostra_ospite()

    def _ospite(self):
        """Prodotto cambiato: si torna all'ospite che propone."""
        self.ospite_scelto = None
        self._riempi_ospiti()

    def _ospite_cambiato(self):
        k = self.ospite.currentData()
        self.ospite_scelto = None if k == self._proposta() else k
        self._mostra_ospite()

    def _mostra_ospite(self):
        _ospiti, titolo, perche, livello = regola(self.contesto.info, self.prodotto.currentData())
        svuota(self.zona_ospite)
        if self.ospite_scelto is None:
            self.zona_ospite.addWidget(riquadro(titolo, perche, livello))
        else:
            self.zona_ospite.addWidget(riquadro(
                _("Hai cambiato l'ospite proposto per questo prodotto."),
                _("Va bene se sai che il campione contiene il DNA di un altro organismo. Il DNA dell'ospite che "
                  "resta nelle read finisce assegnato per errore a qualche taxon."), "avviso"))
        k = self.ospite.currentData()
        voce = self._personali().get(k)
        if k == NESSUNO:
            testo = _("Non tolgo il DNA di nessun ospite: tolgo solo il DNA umano, che può arrivare da chi ha toccato "
                      "il campione (per esempio nel suolo).")
        elif k == "grch38":
            testo = _("Tolgo il DNA umano (GRCh38), per esempio da feci o cute.")
        elif k in INSTALLATI:
            testo = _("L'indice di questo ospite è già nel motore. Tolgo anche il DNA umano.")
        elif k == "vitis_vinifera":
            testo = _("Alla prima analisi scarico il genoma della vite da NCBI e costruisco il suo indice ({costo}), "
                      "una volta sola. Tolgo anche il DNA umano.",
                      costo=stima_in_parole(progetto.stima_indice(VITE_BASI, scaricare=True)))
        elif voce is not None:
            basi = voce.get("basi") if isinstance(voce.get("basi"), int) else progetto.BASI_GRANDE
            testo = _("Ospite aggiunto da te. Se il suo indice non è ancora pronto, la prima analisi lo costruisce "
                      "({costo}), una volta sola. Tolgo anche il DNA umano.",
                      costo=stima_in_parole(progetto.stima_indice(basi, scaricare=bool(voce.get("accession")))))
        else:
            testo = _("Tolgo anche il DNA umano.")
        self.nota_ospite.setText(testo)

    def aggiungi_ospite(self):
        info = self.contesto.info or {}
        finestra = FinestraOspite(info.get("ram_gb"), info.get("spazio_libero_gb"), self)
        if finestra.exec() == QDialog.Accepted and finestra.aggiunto:
            self.ospite_scelto = finestra.aggiunto
            self._riempi_ospiti()

    def _voce_progetto(self, nome):
        """L'ospite aggiunto come va scritto nel config.yaml (il FASTA col percorso che vede il motore), o None."""
        voce = progetto.ospiti_personali().get(nome)
        if voce is None:                                 # non più nell'elenco: resta com'era nel progetto
            return self.personali_progetto.get(nome)
        out = {"accession": voce["accession"]} if voce.get("accession") else \
            {"fasta": percorso_per_motore(voce["fasta"])}
        if isinstance(voce.get("basi"), int):
            out["basi"] = voce["basi"]
        return out

    def _conta_codici(self):
        validi, scartati = progetto.codici(self.testo_codici.toPlainText())
        n = len(validi)
        testo = {0: _("Non ho ancora riconosciuto nessun codice."), 1: _("Ho riconosciuto 1 codice valido.")}.get(
            n, _("Ho riconosciuto {n} codici validi.", n=n))
        if scartati:
            testo += _(" Non riconosco: {codici} (un codice è fatto come SRR4875279, ERR... o DRR...).",
                       codici=f"{', '.join(scartati[:5])}{'...' if len(scartati) > 5 else ''}")
        self.conteggio.setText(testo)

    # ---------------- cartella delle read ----------------
    def scegli_cartella(self):
        impostazioni = QSettings("ProfileMetaNanni", "app")
        documenti = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        partenza = impostazioni.value("ultima_cartella_read", documenti)       # R10
        if not Path(str(partenza)).is_dir():
            partenza = documenti
        scelta = QFileDialog.getExistingDirectory(self, _("Scegli la cartella delle read"), str(partenza))
        if scelta:
            impostazioni.setValue("ultima_cartella_read", scelta)
            self.usa_cartella(scelta)

    def usa_cartella(self, cartella):
        """Controlla la cartella scelta e dice che cosa ci ha trovato (i file li conta come il motore)."""
        svuota(self.esito_cartella)
        svuota(self.errore)
        self.cartella = None
        cartella = Path(cartella)
        self.nome_cartella.setText(str(cartella))
        if not progetto.percorso_sicuro(cartella):
            self.esito_cartella.addWidget(riquadro(
                _("Il nome di questa cartella ha un carattere che il motore non accetta."),
                _("Togli dal nome della cartella (e da quelle che la contengono) i simboli come ; & ! $ e riprova."),
                "errore"))
            return
        try:
            percorso_per_motore(cartella)
            trovati, saltati = progetto.campioni_locali(cartella)
        except (ValueError, OSError):
            self.esito_cartella.addWidget(riquadro(
                _("Non riesco a leggere questa cartella."),
                _("Scegli una cartella che sta su questo computer (non su un disco di rete)."), "errore"))
            return
        if not trovati:
            self.esito_cartella.addWidget(riquadro(
                _("In questa cartella non ci sono read."),
                _("Le read sono i file che finiscono in .fastq.gz. Scegli la cartella che ti ha mandato il laboratorio."),
                "errore"))
        else:
            self.cartella = cartella
            nomi = [n for n, _, _ in trovati]
            soli = [n for n, _, r2 in trovati if r2 is None]
            n = len(trovati)
            testo = (_("Ho trovato 1 campione: {nome}.", nome=nomi[0]) if n == 1 else
                     _("Ho trovato {n} campioni: {nomi}.", n=n, nomi=f"{', '.join(nomi[:6])}{'...' if n > 6 else ''}"))
            if soli:
                testo += _(" Per {nomi} c'è un solo file invece della coppia R1 e R2: lo analizzo da solo.",
                           nomi=f"{', '.join(soli[:4])}{'...' if len(soli) > 4 else ''}")
            self.esito_cartella.addWidget(etichetta(testo))
        if saltati:                                      # come il motore (contratto §3): non li analizza
            self.esito_cartella.addWidget(riquadro(
                _("Salto {file}: manca l'altro file della coppia.",
                  file=f"{', '.join(saltati[:4])}{'...' if len(saltati) > 4 else ''}"),
                _("Se ti serve, metti nella cartella anche l'altro file (R1 con R2) e scegli di nuovo la cartella."),
                "avviso"))

    # ---------------- salvataggio ----------------
    def azione_principale(self):
        p = self.contesto.progetto
        if p is None:
            self.vai.emit("home")
            return
        if self.esempio:
            self.vai.emit("scelte")
            return
        svuota(self.errore)
        locale = self.scelta_pc.pulsante.isChecked()
        validi, _scartati = progetto.codici(self.testo_codici.toPlainText())
        if locale and self.cartella is None:
            self.errore.addWidget(riquadro(_("Manca la cartella delle read."),
                                           _("Premi Scegli la cartella... e scegli quella con i file .fastq.gz."),
                                           "errore"))
            return
        if not locale and not validi:
            self.errore.addWidget(riquadro(_("Manca il codice di almeno un campione."),
                                           _("Scrivi i codici dei campioni, uno per riga (per esempio SRR4875279)."),
                                           "errore"))
            return
        cfg = progetto.base(p.nome)
        vecchio = p.leggi()
        for chiave, valore in vecchio.items():           # le scelte già fatte restano
            if isinstance(valore, dict) and isinstance(cfg.get(chiave), dict):
                cfg[chiave] = {**cfg[chiave], **valore}
            else:
                cfg[chiave] = valore
        chiave = self.prodotto.currentData()
        scelto = self.ospite_scelto
        cfg["project_name"] = p.nome
        if scelto is None:                               # l'ospite proposto: la regola del prodotto così com'è
            cfg["hosts"] = list(regola(self.contesto.info, chiave)[0])
        else:
            cfg["hosts"] = [] if scelto == NESSUNO else [scelto]
        cfg["filter_human"] = True
        cfg.pop("ospiti_personali", None)
        if scelto is not None and scelto not in dict(OSPITI):
            try:
                voce = self._voce_progetto(scelto)
            except ValueError:                           # FASTA su un disco di rete
                voce = None
            if not voce:
                self.errore.addWidget(riquadro(_("Non riesco a usare l'ospite {nome}.", nome=scelto),
                                               _("Il suo file FASTA deve stare su un disco di questo computer. "
                                                 "Aggiungilo di nuovo con Aggiungi un ospite..."), "errore"))
                return
            cfg["ospiti_personali"] = {scelto: voce}
        cfg["data_source"] = "local" if locale else "ncbi"
        if locale:
            cfg["paths"]["local_reads_dir"] = percorso_per_motore(self.cartella)
            cfg["paths"]["srr_list"] = ""
        else:
            if not progetto.percorso_sicuro(p.codici_campioni):   # srr_list è assoluto: il motore lo rifiuterebbe
                self.errore.addWidget(riquadro(
                    _("Il nome di questa cartella ha un carattere che il motore non accetta."),
                    _("Togli dal nome della cartella (e da quelle che la contengono) i simboli come ; & ! $ e riprova.")
                    + f" ({p.cartella.parent})", "errore"))
                return
            p.scrivi_codici(validi)
            cfg["paths"]["srr_list"] = percorso_per_motore(p.codici_campioni)
            cfg["paths"]["local_reads_dir"] = ""
        cfg["app"] = {"prodotto": chiave, "cartella_read": str(self.cartella) if locale else ""}
        if scelto is not None:                           # salumi con l'ospite proposto: config.yaml come prima
            cfg["app"]["ospite"] = scelto
        p.scrivi(cfg)
        self.vai.emit("scelte")


class FinestraOspite(QDialog):
    """"Aggiungi un ospite" (R8): nome breve e genoma da NCBI (codice dell'assembly) o da un file FASTA del computer.
    Controlla mostra quanto costa costruire l'indice (tempo, memoria, disco); Aggiungi lo mette nell'elenco della
    persona (progetto.aggiungi_ospite). L'indice lo costruisce il motore alla prima analisi che usa l'ospite."""

    def __init__(self, ram_gb=None, libero_gb=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Aggiungi un ospite"))
        self.resize(760, 660)
        self.ram_gb, self.libero_gb = ram_gb, libero_gb
        self.voce = None             # pronta dopo Controlla
        self.aggiunto = None         # nome dell'ospite aggiunto
        self.fasta = None
        fuori = QVBoxLayout(self)    # come le pagine: il contenuto scorre (i testi a capo hanno l'altezza giusta)
        fuori.setContentsMargins(0, 0, 0, 16)
        contenuto = QWidget()
        scorre = QScrollArea()
        scorre.setWidgetResizable(True)
        scorre.setFrameShape(QFrame.NoFrame)
        scorre.setWidget(contenuto)
        fuori.addWidget(scorre, 1)
        s = QVBoxLayout(contenuto)
        s.setSpacing(10)
        s.setContentsMargins(24, 20, 24, 8)
        s.setAlignment(Qt.AlignTop)
        s.addWidget(etichetta(_("Se il campione contiene il DNA di un organismo che non è nell'elenco (un'altra pianta, "
                                "un altro animale), aggiungilo qui. Il programma costruisce una volta sola l'indice "
                                "per togliere il suo DNA, alla prima analisi, e poi lo riusa.")))
        s.addWidget(etichetta(_("Nome breve"), "etichetta_campo"))
        self.nome = QLineEdit()
        self.nome.setPlaceholderText(_("per esempio olivo"))
        self.nome.setAccessibleName(_("Nome breve"))
        self.nome.textChanged.connect(self._cambiato)
        s.addWidget(self.nome)
        s.addWidget(etichetta(_("Solo lettere senza accenti, numeri e trattino basso (_)."), "nota"))
        s.addWidget(etichetta(_("Da dove prendo il genoma?"), "etichetta_campo"))
        gruppo = QButtonGroup(self)
        self.scelta_ncbi = Scelta(_("Da NCBI"), _("Con il codice dell'assembly, che inizia con GCF_ o GCA_ (per "
                                                  "esempio GCF_030704535.1). Lo scarico io."), gruppo)
        self.scelta_file = Scelta(_("Da un file del mio computer"), _("Un genoma in formato FASTA: .fa, .fasta o "
                                                                      ".fna, anche compresso .gz."), gruppo)
        s.addLayout(riga_di_scelte(self.scelta_ncbi, self.scelta_file))
        self.codice = QLineEdit()
        self.codice.setPlaceholderText("GCF_000000000.1")
        self.codice.setAccessibleName(_("Codice dell'assembly NCBI"))
        self.codice.textChanged.connect(self._cambiato)
        s.addWidget(self.codice)
        self.zona_file = QFrame()
        r = QHBoxLayout(self.zona_file)
        r.setContentsMargins(0, 0, 0, 0)
        b = QPushButton(_("Scegli il file..."), objectName="secondario")
        b.clicked.connect(self.scegli_file)
        r.addWidget(b)
        self.nome_file = etichetta("")
        r.addWidget(self.nome_file, 1)
        s.addWidget(self.zona_file)
        self.esito = QVBoxLayout()
        s.addLayout(self.esito)
        riga = QHBoxLayout()
        riga.setContentsMargins(24, 0, 24, 0)
        riga.addStretch(1)
        annulla = QPushButton(_("Annulla"), objectName="secondario")
        annulla.clicked.connect(self.reject)
        self.pulsante_controlla = QPushButton(_("Controlla"), objectName="secondario")
        self.pulsante_controlla.clicked.connect(self.controlla)
        self.pulsante_aggiungi = QPushButton(_("Aggiungi l'ospite"))
        self.pulsante_aggiungi.clicked.connect(self.aggiungi)
        for w in (annulla, self.pulsante_controlla, self.pulsante_aggiungi):
            riga.addWidget(w)
        fuori.addLayout(riga)
        self.scorre = scorre
        self.scelta_ncbi.scelta.connect(self._fonte)
        self.scelta_file.scelta.connect(self._fonte)
        self.scelta_ncbi.pulsante.setChecked(True)
        self._fonte()

    def _adatta(self):
        """L'esito di Controlla è in fondo: lo si porta in vista."""
        self.scorre.ensureVisible(0, self.scorre.widget().sizeHint().height())

    def _fonte(self):
        ncbi = self.scelta_ncbi.pulsante.isChecked()
        self.codice.setVisible(ncbi)
        self.zona_file.setVisible(not ncbi)
        self._cambiato()

    def _cambiato(self):
        """Ogni modifica chiede un nuovo Controlla prima di Aggiungi."""
        self.voce = None
        self.pulsante_aggiungi.setEnabled(False)
        self.pulsante_controlla.setDefault(True)
        svuota(self.esito)

    def scegli_file(self):
        documenti = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        scelta, _filtro = QFileDialog.getOpenFileName(
            self, _("Scegli il genoma (FASTA)"), documenti,
            _("Genomi FASTA") + " (*.fa *.fasta *.fna *.fa.gz *.fasta.gz *.fna.gz)")
        if scelta:
            self.usa_file(scelta)

    def usa_file(self, percorso):
        self.fasta = Path(percorso)
        self.nome_file.setText(str(self.fasta))
        self._cambiato()

    def _errore(self, titolo, testo):
        self.esito.addWidget(riquadro(titolo, testo, "errore"))
        self._adatta()

    def controlla(self):
        """Controlla nome e genoma, poi mostra il costo dell'indice; se va tutto bene si può aggiungere."""
        svuota(self.esito)
        self.voce = None
        self.pulsante_aggiungi.setEnabled(False)
        nome = self.nome.text().strip()
        problema = progetto.errore_nome_ospite(nome)
        if problema:
            self._errore(_("Il nome non va bene."), problema)
            return
        avvisi = []
        if self.scelta_ncbi.pulsante.isChecked():
            codice = self.codice.text().strip().upper()
            if not progetto.ACCESSION.fullmatch(codice):
                self._errore(_("Il codice non va bene."),
                             _("Il codice dell'assembly inizia con GCF_ o GCA_, poi 9 cifre, un punto e la versione "
                               "(per esempio GCF_030704535.1). Lo trovi nella pagina del genoma su NCBI."))
                return
            self.pulsante_controlla.setEnabled(False)          # la domanda a NCBI può durare qualche secondo
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                trovato = progetto.dimensione_ncbi(codice)
                certificato = False
            except progetto.NcbiNonRaggiungibile as e:
                trovato, certificato = False, e.certificato
            finally:
                QApplication.restoreOverrideCursor()
                self.pulsante_controlla.setEnabled(True)
            if trovato is None:                                # B2-9a: NCBI ha risposto che non lo conosce
                self._errore(_("NCBI non conosce il codice {codice}.", codice=codice),
                             _("Controlla il codice nella pagina del genoma su NCBI (www.ncbi.nlm.nih.gov/datasets)."))
                return
            if trovato:
                basi, organismo = trovato
                titolo = _("{organismo}: circa {basi}.", organismo=organismo or codice,
                           basi=progetto.basi_in_parole(basi))
                voce = {"accession": codice, "basi": basi, **({"organismo": organismo} if organismo else {})}
            else:
                # NCBI non risponde: si può aggiungere lo stesso (il codice ha la forma giusta, il motore lo scarica e lo
                # controlla alla prima analisi e dice in parole semplici se non esiste), senza basi: la stima resta
                # quella prudente di un genoma grande come quello umano, anche nel motore
                basi = progetto.BASI_GRANDE
                titolo = (_("Non riesco a verificare il certificato del sito di NCBI.") if certificato else
                          _("Non riesco a chiedere a NCBI quanto è grande questo genoma."))
                avvisi.append(_("Controlla la data e l'ora del computer e la connessione a internet.") if certificato
                              else _("Controlla la connessione a internet."))
                avvisi.append(_("Puoi aggiungere l'ospite lo stesso: alla prima analisi scarico il genoma e controllo "
                                "il codice. La stima vale per un genoma grande come quello umano."))
                voce = {"accession": codice}
            costo = progetto.stima_indice(basi, scaricare=True)
        else:
            if self.fasta is None:
                self._errore(_("Manca il file del genoma."), _("Premi Scegli il file... e scegli il genoma in formato "
                                                               "FASTA."))
                return
            basi, problema = progetto.controlla_fasta(self.fasta)
            if problema:
                self._errore(_("Non posso usare questo file."), problema)
                return
            titolo = _("Genoma di circa {basi}.", basi=progetto.basi_in_parole(basi))
            voce = {"fasta": str(self.fasta), "basi": basi}
            costo = progetto.stima_indice(basi)
        testo = _("Costruire l'indice richiede {costo}; sul disco occupa {disco}, e durante la costruzione ne servono "
                  "{tmp} in più. Si fa una volta sola, alla prima analisi che usa questo ospite; poi si riusa.",
                  costo=stima_in_parole(costo), disco=progetto.spazio_in_parole(costo["disco_gb"]),
                  tmp=progetto.spazio_in_parole(costo["temporaneo_gb"]))
        if self.ram_gb and costo["ram_gb"] > self.ram_gb:
            avvisi.append(_("Il motore vede solo {ram} GB di memoria: la costruzione potrebbe fermarsi. Chiudi gli "
                            "altri programmi prima dell'analisi o usa un computer con più memoria.",
                            ram=numero(self.ram_gb)))
        if self.libero_gb is not None and costo["disco_gb"] + costo["temporaneo_gb"] > self.libero_gb:
            avvisi.append(_("Sul disco ci sono solo {libero} GB liberi: libera spazio prima dell'analisi.",
                            libero=numero(self.libero_gb)))
        self.esito.addWidget(riquadro(titolo, " ".join([testo, *avvisi]), "avviso" if avvisi else "info"))
        self._adatta()
        self.voce = voce
        self.pulsante_aggiungi.setEnabled(True)
        self.pulsante_aggiungi.setDefault(True)

    def aggiungi(self):
        if self.voce is None:
            return
        nome = self.nome.text().strip()
        try:
            progetto.aggiungi_ospite(nome, self.voce)
        except (ValueError, OSError) as e:
            svuota(self.esito)
            self._errore(_("Non riesco ad aggiungere l'ospite."), str(e))
            return
        self.aggiunto = nome
        self.accept()
