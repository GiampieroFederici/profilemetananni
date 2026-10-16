"""Pagina "Scelte dell'analisi" (S5b, docs/interfaccia_S4.md §3.2): le scelte consigliate sono già pronte (R4),
i parametri tecnici stanno chiusi con la fonte accanto (R6, D022), e prima di partire il motore stima tempo e
spazio (`stima --progetto`). "Avvia l'analisi" scrive config.yaml e passa la mano ad "Analisi in corso" (S6).

I valori consigliati di Kraken e Bracken si leggono da refs/kraken_profili.tsv (gli stessi che usa il motore).
"""
import csv

import yaml
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QPlainTextEdit, QPushButton, \
    QVBoxLayout

from app.motore import RADICE, MotoreClient, percorso_per_motore
from app.pagine.base import Pagina, etichetta, numero, riquadro
from app.pagine.progetto import STILE, Scelta, pannello, riga_di_scelte, svuota

PROFILI_KRAKEN = RADICE / "refs" / "kraken_profili.tsv"
CONFIDENZE = ["0", "0.05", "0.1", "0.2", "0.3"]
SOGLIE = ["0.001", "0.005", "0.01", "0.1"]
LUNGHEZZE = [100, 150, 250]
LUNGHEZZA_CONSIGLIATA = 150                      # config.example.yaml (bracken_readlen)
FONTE_CONFIDENZA = ("Consigliato 0 con il database completo (il valore di Kraken 2 se non si cambia nulla) e 0,1 con "
                    "lo screening rapido: per i database ridotti si consiglia fra 0,05 e 0,30 (Wright, Comeau e "
                    "Langille 2023).")
FONTE_SOGLIA = ("0,005 % è la soglia migliore trovata da Edwin et al. 2024 (campioni di suolo: da confermare sui "
                "salumi). Le specie sotto la soglia restano nel file Excel.")
FONTE_LETTURE = "Fisso nel profilo del database del motore: Bracken stima una specie solo se ha almeno queste read."
FONTE_LUNGHEZZA = ("Deve corrispondere alla lunghezza delle read del sequenziamento: 150 per la maggior parte delle "
                   "read Illumina di oggi.")
# dove si risolve un errore di stima (R8): codice -> (testo del pulsante principale, pagina o None = riprova)
RIMEDI = {"READ_NON_TROVATE": ("Correggi i campioni", "campioni"),
          "CONFIG_NON_VALIDA": ("Correggi i campioni", "campioni"),
          "MOTORE_NON_AVVIATO": ("Apri la pagina Motore", "motore"),
          "DB_MANCANTE": ("Apri la pagina Motore", "motore"),
          "ERRORE_INTERNO": ("Apri la pagina Motore", "motore")}


def profili_kraken():
    """{profilo: {"confidenza", "letture", "soglia"}} da refs/kraken_profili.tsv."""
    out = {}
    with open(PROFILI_KRAKEN, encoding="utf-8", newline="") as f:
        for r in csv.reader(f, delimiter="\t"):
            if r and not r[0].startswith("#") and len(r) >= 4:
                out[r[0]] = {"confidenza": r[1], "letture": r[2], "soglia": r[3]}
    return out


def virgola(testo):
    return str(testo).replace(".", ",")


def durata(secondi):
    """Secondi in parole: '45 secondi', '51 minuti', '9,9 ore' (R11: solo formato)."""
    if secondi < 90:
        return f"{round(secondi)} secondi"
    if secondi < 5400:
        return f"{round(secondi / 60)} minuti"
    return f"{numero(secondi / 3600, 1)} ore"


class PaginaScelte(Pagina):
    titolo = "Scelte dell'analisi"
    testo_principale = "Avvia l'analisi"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.setStyleSheet(STILE)
        self.profili = profili_kraken()
        self.client = MotoreClient(self)
        self.client.evento.connect(self._evento)
        self.client.finito.connect(self._finito)
        self.ancora = False          # una scelta è cambiata mentre la stima girava: rifarla alla fine
        self.carico = False          # True mentre la pagina riempie i campi (niente salvataggi a metà)
        self.avvisi = []
        self.errore_stima = None
        self.rimedio = None

        self.intro = etichetta("")
        self.corpo.addWidget(self.intro)
        self.zona_avvisi = QVBoxLayout()            # consigli del motore (info) e progetto mancante, prima di tutto
        self.corpo.addLayout(self.zona_avvisi)

        self.corpo.addSpacing(8)
        self.corpo.addWidget(etichetta("Quanto a fondo cercare le specie rare?", "sottotitolo"))
        self.corpo.addWidget(etichetta("Vale per il secondo metodo di analisi, il programma Kraken. Il primo "
                                       "(MetaPhlAn) gira sempre allo stesso modo.", "nota"))
        self.gruppo_kraken = QButtonGroup(self)
        self.completo = Scelta("Database completo", "Trova anche le specie poco abbondanti. Più lento.",
                               self.gruppo_kraken, consigliato=True)
        self.rapido = Scelta("Screening rapido", "Pochi secondi a campione, ma può perdere specie fra 0,1 e 1 %, "
                             "anche batteri lattici. Utile per una prima occhiata.", self.gruppo_kraken)
        self.corpo.addLayout(riga_di_scelte(self.completo, self.rapido))

        self.corpo.addSpacing(8)
        self.corpo.addWidget(etichetta("Che cosa cerco?", "sottotitolo"))
        sempre = QFrame(objectName="scelta")
        sempre.setProperty("scelto", True)
        s = QVBoxLayout(sempre)
        s.setContentsMargins(18, 14, 18, 14)
        c = QCheckBox("Batteri, archei e lieviti")
        c.setChecked(True)
        c.setEnabled(False)
        c.setStyleSheet("font-weight: bold;")
        s.addWidget(c)
        e = etichetta("Sempre incluso. Profilo delle specie con MetaPhlAn (in 6 parti, per stare in 16 GB) e con Kraken.")
        e.setContentsMargins(30, 0, 0, 0)
        s.addWidget(e)
        self.corpo.addWidget(sempre)
        self.scheda_virus = QFrame(objectName="scelta")
        s = QVBoxLayout(self.scheda_virus)
        s.setContentsMargins(18, 14, 18, 14)
        self.virus = QCheckBox("Anche i virus")
        self.virus.setStyleSheet("font-weight: bold;")
        s.addWidget(self.virus)
        e = etichetta("Opzione sperimentale: cerca anche i virus nel profilo di MetaPhlAn.")
        e.setContentsMargins(30, 0, 0, 0)
        s.addWidget(e)
        s.addWidget(riquadro("Sperimentale, non validata.",
                             "Con il database diviso in parti, quando due virus quasi identici vanno bene allo stesso "
                             "modo la scelta può cambiare rispetto all'analisi standard. Il referto lo dichiara.",
                             "avviso"))                                                     # R13, D017, D033
        self.corpo.addWidget(self.scheda_virus)

        # parametri per esperti: chiusi (R6), consigliato preselezionato e fonte accanto (D022)
        self.corpo.addSpacing(8)
        self.apri_esperti = QPushButton(objectName="apri")
        self.apri_esperti.setCheckable(True)
        self.apri_esperti.toggled.connect(self._esperti)
        self.corpo.addWidget(self.apri_esperti)
        self.esperti, s = pannello()
        s.addWidget(etichetta("Ogni valore consigliato viene dalla letteratura; la fonte è accanto. Quello che scegli "
                              "finisce nel referto.", "nota"))
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(20)
        griglia.setVerticalSpacing(12)
        griglia.setColumnStretch(2, 1)
        self.confidenza = QComboBox()
        self.soglia = QComboBox()
        self.lunghezza = QComboBox()
        self.letture = etichetta("")
        righe = [("Soglia di confidenza di Kraken", self.confidenza, FONTE_CONFIDENZA),
                 ("Abbondanza minima mostrata", self.soglia, FONTE_SOGLIA),
                 ("Read minime per specie (Bracken)", self.letture, FONTE_LETTURE),
                 ("Lunghezza delle read (Bracken)", self.lunghezza, FONTE_LUNGHEZZA)]
        for i, (nome, campo, fonte) in enumerate(righe):
            griglia.addWidget(etichetta(nome, "etichetta_campo"), i, 0)
            campo.setAccessibleName(nome)
            campo.setMinimumWidth(220)
            griglia.addWidget(campo, i, 1)
            griglia.addWidget(etichetta(fonte, "nota"), i, 2)
        s.addLayout(griglia)
        self.apri_file = QPushButton(objectName="apri")
        self.apri_file.setCheckable(True)
        self.apri_file.toggled.connect(self._file)
        s.addWidget(self.apri_file)
        self.file = QPlainTextEdit()
        self.file.setReadOnly(True)
        self.file.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.file.setFixedHeight(260)
        self.file.setStyleSheet("font-family: Consolas, monospace; font-size: 15px;")
        self.file.setAccessibleName("File del progetto")
        s.addWidget(self.file)
        self.corpo.addWidget(self.esperti)
        self._esperti(False)
        self._file(False)

        self.corpo.addSpacing(8)
        self.corpo.addWidget(etichetta("Prima di partire", "sottotitolo"))
        self.stima, self.zona_stima = pannello()
        self.corpo.addWidget(self.stima)

        for l, valori, fmt in ((self.soglia, SOGLIE, lambda v: f"{virgola(v)} %"), (self.lunghezza, LUNGHEZZE, str)):
            for v in valori:
                l.addItem(fmt(v), v)
        self.completo.scelta.connect(self._kraken_cambiato)
        self.rapido.scelta.connect(self._kraken_cambiato)
        for w in (self.confidenza, self.soglia, self.lunghezza):
            w.currentIndexChanged.connect(self._cambiato)
        self.virus.toggled.connect(self._cambiato)

    # ---------------- ingresso nella pagina ----------------
    def mostrata(self):
        svuota(self.zona_avvisi)
        info = self.contesto.info
        p = self.contesto.progetto
        if info:
            self.intro.setText(f"Ho già preparato le scelte consigliate per questo computer ({numero(info['ram_gb'])} "
                               f"GB di memoria, {info['processori']} processori). Puoi partire subito.")
            for c in info.get("consigli", []):
                if c.get("livello") == "avviso":
                    self.zona_avvisi.addWidget(riquadro("Consiglio del motore", c["messaggio"], "avviso"))
        else:
            self.intro.setText("Ho già preparato le scelte consigliate. Puoi partire subito.")
        if p is None:
            self.zona_avvisi.addWidget(riquadro("Nessun progetto aperto.", "Apri un progetto o creane uno nuovo "
                                                "nella pagina I miei progetti.", "avviso"))
            self._barra("Vai ai miei progetti", "", rimedio=("Vai ai miei progetti", "home"))
            svuota(self.zona_stima)
            return
        self._carica(p.leggi())
        self._salva()
        self._avvia_stima()

    def _carica(self, cfg):
        """Riempie i campi: le scelte già salvate del progetto, altrimenti quelle consigliate dal motore (R4)."""
        self.carico = True
        motore = cfg.get("motore") if isinstance(cfg.get("motore"), dict) else {}
        profiling = cfg.get("profiling") if isinstance(cfg.get("profiling"), dict) else {}
        app = cfg.get("app") if isinstance(cfg.get("app"), dict) else {}
        consigliato = ((self.contesto.info or {}).get("modo_consigliato") or {}).get("kraken", "completo")
        kraken = motore.get("kraken_db") if app.get("scelte") else consigliato
        (self.rapido if kraken == "rapido" else self.completo).pulsante.setChecked(True)
        self._confidenze()
        self._seleziona(self.confidenza, str(profiling.get("kraken_confidence") or ""))
        self._seleziona(self.soglia, str(profiling.get("abundance_threshold_pct") or ""))
        self._seleziona(self.lunghezza, profiling.get("bracken_readlen") or LUNGHEZZA_CONSIGLIATA)
        self.virus.setChecked(bool(motore.get("virus", False)))
        self.carico = False

    def _profilo(self):
        return "rapido" if self.rapido.pulsante.isChecked() else "completo"

    def _confidenze(self):
        """Menu della confidenza con il consigliato del database scelto; tiene la scelta dell'utente se c'era."""
        prima = self.confidenza.currentData()
        consigliati = self.profili[self._profilo()]
        self.confidenza.blockSignals(True)
        self.confidenza.clear()
        for v in CONFIDENZE:
            self.confidenza.addItem(virgola(v) + (" (consigliato)" if v == consigliati["confidenza"] else ""), v)
        self.confidenza.blockSignals(False)
        for i, v in enumerate(SOGLIE):
            self.soglia.setItemText(i, f"{virgola(v)} %" + (" (consigliato)" if v == consigliati["soglia"] else ""))
        for i, v in enumerate(LUNGHEZZE):
            self.lunghezza.setItemText(i, str(v) + (" (consigliato)" if v == LUNGHEZZA_CONSIGLIATA else ""))
        self.letture.setText(consigliati["letture"])
        self._seleziona(self.confidenza, prima or "")

    def _seleziona(self, menu, valore):
        """Seleziona un valore; vuoto (o sconosciuto) = il consigliato del database."""
        consigliati = self.profili[self._profilo()]
        if valore in ("", None):
            valore = {self.confidenza: consigliati["confidenza"], self.soglia: consigliati["soglia"],
                      self.lunghezza: LUNGHEZZA_CONSIGLIATA}[menu]
        i = menu.findData(valore)
        if i >= 0:
            menu.setCurrentIndex(i)

    # ---------------- scelte cambiate ----------------
    def _kraken_cambiato(self):
        if self.carico:
            return
        consigliata_prima = self.confidenza.currentText().endswith("(consigliato)")
        self.carico = True
        self._confidenze()
        if consigliata_prima:                     # seguiva il consigliato: segue quello del nuovo database
            self._seleziona(self.confidenza, "")
        self.carico = False
        self._cambiato()

    def _cambiato(self, *_):
        if self.carico or self.contesto.progetto is None:
            return
        self._salva(scelte=True)
        self._avvia_stima()

    def _salva(self, scelte=False):
        """Scrive le scelte in config.yaml (tutto o niente). Consigliato = campo vuoto: decide il motore."""
        p = self.contesto.progetto
        cfg = p.leggi()
        consigliati = self.profili[self._profilo()]
        info = self.contesto.info or {}
        motore = cfg.setdefault("motore", {})
        motore["metaphlan_modo"] = (info.get("modo_consigliato") or {}).get("metaphlan", motore.get("metaphlan_modo",
                                                                                                    "fette"))
        motore["kraken_db"] = self._profilo()
        motore["virus"] = self.virus.isChecked()
        if info.get("processori"):
            motore["processori"] = info["processori"]
            cfg.setdefault("execution", {})["threads"] = info["processori"]
        profiling = cfg.setdefault("profiling", {})
        conf, soglia = self.confidenza.currentData(), self.soglia.currentData()
        profiling["kraken_confidence"] = "" if conf == consigliati["confidenza"] else float(conf)
        profiling["abundance_threshold_pct"] = "" if soglia == consigliati["soglia"] else float(soglia)
        profiling["bracken_readlen"] = self.lunghezza.currentData()
        if scelte:
            cfg.setdefault("app", {})["scelte"] = True
        p.scrivi(cfg)
        self.file.setPlainText(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))

    def _esperti(self, aperto):
        self.apri_esperti.setText(("▾ " if aperto else "▸ ") + "Parametri per esperti (di solito non servono)")
        self.esperti.setVisible(aperto)

    def _file(self, aperto):
        self.apri_file.setText(("▾ " if aperto else "▸ ") + "Mostra il file del progetto (per riprodurre l'analisi)")
        self.file.setVisible(aperto)

    # ---------------- stima ----------------
    def _avvia_stima(self):
        if self.client.in_corso():
            self.ancora = True
            return
        svuota(self.zona_stima)
        self.zona_stima.addWidget(etichetta("Chiedo al motore quanto tempo e spazio servono..."))
        self.avvisi, self.errore_stima = [], None
        self._barra("Avvia l'analisi", "Calcolo il tempo che serve...")
        try:
            percorso = percorso_per_motore(self.contesto.progetto.config)
        except ValueError:
            self._errore({"codice": "CONFIG_NON_VALIDA", "messaggio": "Il progetto non sta su un disco di questo "
                          "computer.", "cosa_fare": "Crea il progetto nella cartella Documenti."})
            return
        self.client.avvia("stima", "--progetto", percorso)

    def _evento(self, e):
        if e["tipo"] == "avviso":
            self.avvisi.append(e)
        elif e["tipo"] == "errore":
            self.errore_stima = e

    def _finito(self, codice, fine):
        if self.ancora:
            self.ancora = False
            self._avvia_stima()
            return
        if fine.get("esito") != "ok":
            self._errore(self.errore_stima or {"messaggio": fine.get("messaggio", ""),
                                                                 "cosa_fare": "Riprova la stima."})
            self.errore_stima = None
            return
        self._mostra_stima(fine["risultato"], fine.get("messaggio", ""))

    def _mostra_stima(self, r, messaggio):
        svuota(self.zona_stima)
        lungo = any(a.get("codice") == "TEMPO_LUNGO" for a in self.avvisi)
        for a in self.avvisi:                                     # gli avvisi prima dei numeri (R9)
            titolo = "Ci vorrà molto tempo." if a.get("codice") == "TEMPO_LUNGO" else "Attenzione"
            self.zona_stima.addWidget(riquadro(titolo, a["messaggio"], "avviso"))
        tempi = r.get("tempo_s") or {}
        totale = sum(v for v in tempi.values() if v)
        nomi = {"ospite": "ospite", "metaphlan": "MetaPhlAn", "kraken": "Kraken"}
        ordine = [k for k in nomi if k in tempi] + [k for k in tempi if k not in nomi]   # i dict arrivano in ordine alfabetico
        dettaglio = ", ".join(f"{nomi.get(k, k)} {durata(tempi[k])}" for k in ordine if tempi[k])
        coppie = r.get("coppie_totali") or 0
        campioni = r.get("campioni", 0)
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(24)
        griglia.setVerticalSpacing(6)
        righe = [("Campioni", f"{campioni} ({numero(coppie / 1e6, 1)} milioni di coppie di read)"),
                 ("Tempo stimato", f"circa {durata(totale)} ({dettaglio})"),
                 ("Spazio che serve", f"{numero(r.get('spazio_gb', 0), 0)} GB"
                  + (f", ne hai {numero(r['spazio_libero_gb'], 0)} liberi" if r.get("spazio_libero_gb") is not None
                     else ""))]
        for i, (nome, valore) in enumerate(righe):
            griglia.addWidget(etichetta(nome, "etichetta_campo"), i, 0)
            griglia.addWidget(etichetta(valore), i, 1)
        griglia.setColumnStretch(1, 1)
        self.zona_stima.addLayout(griglia)
        if messaggio:
            self.zona_stima.addWidget(etichetta(messaggio, "nota"))
        if self._profilo() == "completo" and tempi.get("kraken"):
            self.completo.spiega.setText("Trova anche le specie poco abbondanti. Più lento: per questo progetto "
                                         f"circa {durata(tempi['kraken'])}.")
        aiuto = f"Tempo stimato: circa {durata(totale)}. Spazio: {numero(r.get('spazio_gb', 0), 0)} GB."
        if lungo:
            aiuto += " Ci vorrà molto: leggi l'avviso qui sopra."
        elif self.avvisi:
            aiuto += " Leggi l'avviso qui sopra."
        secondari = [("Passa allo screening rapido", self.passa_al_rapido)] if lungo and self._profilo() == "completo" \
            else []
        self._barra("Avvia l'analisi", aiuto, "avviso" if self.avvisi else "", secondari)

    def _errore(self, e):
        svuota(self.zona_stima)
        self.zona_stima.addWidget(riquadro("Non riesco a stimare il tempo. " + e.get("messaggio", ""),
                                           e.get("cosa_fare", ""), "errore"))
        testo, pagina = RIMEDI.get(e.get("codice"), ("Riprova la stima", None))
        self._barra(testo, "Prima di partire va risolto il problema scritto qui sopra.", "avviso",
                    rimedio=(testo, pagina))

    def _barra(self, testo, aiuto, livello="", secondari=(), rimedio=None):
        self.testo_principale, self.aiuto, self.aiuto_livello = testo, aiuto, livello
        self.secondari = list(secondari)
        self.rimedio = rimedio
        self.azioni_cambiate.emit()

    def passa_al_rapido(self):
        self.rapido.pulsante.setChecked(True)

    # ---------------- avvio ----------------
    def azione_principale(self):
        if self.rimedio:
            _, pagina = self.rimedio
            if pagina:
                self.vai.emit(pagina)
            else:
                self._avvia_stima()
            return
        self._salva(scelte=True)
        self.contesto.avvia_analisi = True       # "Analisi in corso" (S6) lancia esegui e lo rimette a False
        self.vai.emit("esecuzione")

