"""Pagina "Campioni e prodotto" (S5b, docs/interfaccia_S4.md §3.1): da dove vengono le read e che prodotto è.

Il prodotto decide l'ospite da togliere: la regola la dà il motore (`info.prodotti`, System One v0, contratto
v0.3); la tabella PRODOTTI qui sotto dà i testi del menu e fa da ripiego se il motore non ha risposto. Salva in config.yaml con Progetto.scrivi; i percorsi vanno scritti come li vede il
motore (percorso_per_motore), perché il motore li legge così come sono.
"""
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QFrame, QHBoxLayout, QPlainTextEdit,
                               QPushButton, QVBoxLayout)

from app import progetto
from app.lingua import N_, _
from app.motore import percorso_per_motore
from app.pagine.base import Pagina, Scelta, etichetta, riga_di_scelte, riquadro, svuota

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


def regola(info, chiave):
    """(ospiti, frase, perché, livello) del prodotto: da info.prodotti del motore, altrimenti da PRODOTTI."""
    for r in (info or {}).get("prodotti") or []:
        if r.get("prodotto") == chiave:
            return list(r["ospiti"]), r["frase"], r["perche"], r["livello"]
    ospiti, frase, perche, livello = PRODOTTI[chiave][1:]
    return ospiti, _(frase), _(perche), livello


def prodotto_da_ospiti(ospiti):
    """Il prodotto che corrisponde agli ospiti già scritti nel progetto (per riaprirlo)."""
    for chiave, (_, o, *_resto) in PRODOTTI.items():
        if list(ospiti or []) == o:
            return chiave
    return "altro"


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
        self.prodotto.setAccessibleName(_("Prodotto"))
        for chiave, (testo, *_resto) in PRODOTTI.items():
            self.prodotto.addItem(_(testo), chiave)
        self.prodotto.currentIndexChanged.connect(self._ospite)
        self.corpo.addWidget(self.prodotto)
        self.zona_ospite = QVBoxLayout()
        self.corpo.addLayout(self.zona_ospite)

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
        self._ospite()                                   # info.prodotti può essere arrivato dopo la costruzione
        cfg = p.leggi() if p else {}
        app = cfg.get("app") if isinstance(cfg.get("app"), dict) else {}
        self.esempio = bool(app.get("esempio"))
        self.avviso_esempio.setVisible(self.esempio)
        for w in (self.scelta_pc, self.scelta_ncbi, self.prodotto):
            w.setEnabled(not self.esempio)
        if p is None:
            return
        self.prodotto.setCurrentIndex(max(0, self.prodotto.findData(app.get("prodotto")
                                                                    or prodotto_da_ospiti(cfg.get("hosts", [])))))
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

    def _ospite(self):
        _, titolo, perche, livello = regola(self.contesto.info, self.prodotto.currentData())
        svuota(self.zona_ospite)
        self.zona_ospite.addWidget(riquadro(titolo, perche, livello))

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
        cfg["project_name"] = p.nome
        cfg["hosts"] = list(regola(self.contesto.info, chiave)[0])
        cfg["filter_human"] = True
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
        p.scrivi(cfg)
        self.vai.emit("scelte")
