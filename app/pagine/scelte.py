"""Pagina "Scelte dell'analisi" (S5b, docs/interfaccia_S4.md §3.2): le scelte consigliate sono già pronte (R4),
i parametri tecnici stanno chiusi con la fonte accanto (R6, D022), e prima di partire il motore stima tempo e
spazio (`stima --progetto`). "Avvia l'analisi" scrive config.yaml e passa la mano ad "Analisi in corso" (S6).

I valori consigliati di Kraken e Bracken si leggono da refs/kraken_profili.tsv (gli stessi che usa il motore).
"""
import csv

import yaml
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QPlainTextEdit, QPushButton, \
    QVBoxLayout

from app import lingua
from app.lingua import N_, _
from app.motore import RADICE, MotoreClient, percorso_per_motore
from app.pagine.base import Pagina, PulsanteACapo, Scelta, etichetta, numero, pannello, riga_di_scelte, riquadro, svuota

PROFILI_KRAKEN = RADICE / "refs" / "kraken_profili.tsv"
CONFIDENZE = ["0", "0.05", "0.1", "0.2", "0.3", "0.5"]
SOGLIE = ["0.001", "0.005", "0.01", "0.1"]
LETTURE = ["0", "5", "10", "20", "50"]           # Bracken -t (profiling.bracken_min_reads, contratto v0.3)
LUNGHEZZE = [100, 150, 250]
LUNGHEZZA_CONSIGLIATA = 150                      # config.example.yaml (bracken_readlen)
FONTE_CONFIDENZA = N_("Consigliato 0,5 con il database completo (taratura K4 su comunità simulate di salume, "
                      "confermata sul campione Zymo) e 0,1 con lo screening rapido: per i database ridotti si "
                      "consiglia fra 0,05 e 0,30 (Wright, Comeau e Langille 2023).")
FONTE_SOGLIA = N_("Vale solo per Kraken: MetaPhlAn non ha soglia e mostra tutte le specie. Consigliato 0,1 % con il "
                  "database completo (taratura K4) e 0,005 % con lo screening rapido (Edwin et al. 2024, campioni "
                  "di suolo). Le specie sotto la soglia restano nel file Excel.")
FONTE_LETTURE = N_("Bracken stima una specie solo se ha almeno queste read. 10 è il valore predefinito di Bracken "
                   "(Lu et al. 2017): più alto toglie specie rare e falsi positivi, più basso ne tiene di più.")
FONTE_LUNGHEZZA = N_("Deve corrispondere alla lunghezza delle read del sequenziamento: 150 per la maggior parte delle "
                     "read Illumina di oggi.")
# dove si risolve un errore di stima (R8): codice -> (testo del pulsante principale, pagina o None = riprova)
RIMEDI = {"READ_NON_TROVATE": (N_("Correggi i campioni"), "campioni"),
          "CONFIG_NON_VALIDA": (N_("Correggi i campioni"), "campioni"),
          "MOTORE_NON_AVVIATO": (N_("Apri la pagina Motore"), "motore"),
          "DB_MANCANTE": (N_("Apri la pagina Motore"), "motore"),
          "ERRORE_INTERNO": (N_("Apri la pagina Motore"), "motore")}


def profili_kraken():
    """{profilo: {"confidenza", "letture", "soglia"}} da refs/kraken_profili.tsv."""
    out = {}
    with open(PROFILI_KRAKEN, encoding="utf-8", newline="") as f:
        for r in csv.reader(f, delimiter="\t"):
            if r and not r[0].startswith("#") and len(r) >= 4:
                out[r[0]] = {"confidenza": r[1], "letture": r[2], "soglia": r[3]}
    return out


def virgola(testo):
    return lingua.virgola(testo)


def durata(secondi):
    """Secondi in parole: '45 secondi', '51 minuti', '9,9 ore' (R11: solo formato)."""
    if secondi < 90:
        return _("{n} secondi", n=round(secondi))
    if secondi < 5400:
        return _("{n} minuti", n=round(secondi / 60))
    return _("{n} ore", n=numero(secondi / 3600, 1))


def gb(x):
    """Spazio in parole: '12 GB'; sotto 1 GB 'meno di 1 GB' (non '0 GB', come per il campione d'esempio)."""
    return _("meno di 1 GB") if 0 < x < 0.5 else f"{numero(x, 0)} GB"


class PaginaScelte(Pagina):
    titolo = N_("Scelte dell'analisi")
    testo_principale = N_("Avvia l'analisi")

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
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
        self.corpo.addWidget(etichetta(_("Quanto a fondo cercare le specie rare?"), "sottotitolo"))
        self.corpo.addWidget(etichetta(_("Vale per il secondo metodo di analisi, il programma Kraken. Il primo "
                                         "(MetaPhlAn) gira sempre allo stesso modo."), "nota"))
        self.gruppo_kraken = QButtonGroup(self)
        self.completo = Scelta(_("Database completo"), _("Trova anche le specie poco abbondanti. Più lento."),
                               self.gruppo_kraken, consigliato=True)
        self.rapido = Scelta(_("Screening rapido"), _("Pochi secondi a campione, ma può perdere specie fra 0,1 e 1 %, "
                                                      "anche batteri lattici. Utile per una prima occhiata."),
                             self.gruppo_kraken)
        self.corpo.addLayout(riga_di_scelte(self.completo, self.rapido))

        self.corpo.addSpacing(8)
        self.corpo.addWidget(etichetta(_("Che cosa cerco?"), "sottotitolo"))
        sempre = QFrame(objectName="scelta")
        sempre.setProperty("scelto", True)
        s = QVBoxLayout(sempre)
        s.setContentsMargins(18, 14, 18, 14)
        c = QCheckBox(_("Batteri, archei e lieviti"))
        c.setChecked(True)
        c.setEnabled(False)
        c.setStyleSheet("font-weight: bold;")
        s.addWidget(c)
        e = etichetta(_("Sempre incluso. Profilo delle specie con MetaPhlAn (in 6 parti, per stare in 16 GB) e con "
                        "Kraken."))
        e.setContentsMargins(30, 0, 0, 0)
        s.addWidget(e)
        self.corpo.addWidget(sempre)
        self.scheda_virus = QFrame(objectName="scelta")
        s = QVBoxLayout(self.scheda_virus)
        s.setContentsMargins(18, 14, 18, 14)
        self.virus = QCheckBox(_("Anche i virus"))
        self.virus.setStyleSheet("font-weight: bold;")
        s.addWidget(self.virus)
        e = etichetta(_("Opzione sperimentale: cerca anche i virus nel profilo di MetaPhlAn."))
        e.setContentsMargins(30, 0, 0, 0)
        s.addWidget(e)
        s.addWidget(riquadro(_("Sperimentale, non validata."),
                             _("Con il database diviso in parti, quando due virus quasi identici vanno bene allo stesso "
                               "modo la scelta può cambiare rispetto all'analisi standard. Il referto lo dichiara."),
                             "avviso"))                                                     # R13, D017, D033
        self.corpo.addWidget(self.scheda_virus)
        # 22/10: nascosto finché motore.virus non arriva a bin/run.sh (oggi non lo legge nessuno). Il valore
        # di un progetto già salvato resta com'è: il referto dice "richiesti, ma non ancora calcolati"
        self.scheda_virus.setVisible(False)

        # parametri per esperti: chiusi (R6), consigliato preselezionato e fonte accanto (D022)
        self.corpo.addSpacing(8)
        self.apri_esperti = PulsanteACapo(objectName="apri")
        self.apri_esperti.setCheckable(True)
        self.apri_esperti.toggled.connect(self._esperti)
        self.corpo.addWidget(self.apri_esperti)
        self.esperti, s = pannello()
        s.addWidget(etichetta(_("Ogni valore consigliato ha la fonte accanto (letteratura o taratura K4). Quello che "
                                "scegli finisce nel referto."), "nota"))
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(20)
        griglia.setVerticalSpacing(12)
        griglia.setColumnStretch(2, 1)
        self.confidenza = QComboBox()
        self.soglia = QComboBox()
        self.lunghezza = QComboBox()
        self.letture = QComboBox()
        righe = [(_("Soglia di confidenza di Kraken"), self.confidenza, _(FONTE_CONFIDENZA)),
                 (_("Soglia di abbondanza di Kraken"), self.soglia, _(FONTE_SOGLIA)),
                 (_("Read minime per specie (Bracken)"), self.letture, _(FONTE_LETTURE)),
                 (_("Lunghezza delle read (Bracken)"), self.lunghezza, _(FONTE_LUNGHEZZA))]
        for i, (nome, campo, fonte) in enumerate(righe):
            griglia.addWidget(etichetta(nome, "etichetta_campo"), i, 0)
            campo.setAccessibleName(nome)
            campo.setMinimumWidth(160)                 # B2-2b: 220 non ci stava a 830 px
            griglia.addWidget(campo, i, 1)
            griglia.addWidget(etichetta(fonte, "nota"), i, 2)
        s.addLayout(griglia)
        self.apri_file = PulsanteACapo(objectName="apri")
        self.apri_file.setCheckable(True)
        self.apri_file.toggled.connect(self._file)
        s.addWidget(self.apri_file)
        self.file = QPlainTextEdit()
        self.file.setReadOnly(True)
        self.file.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.file.setFixedHeight(260)
        self.file.setStyleSheet("font-family: Consolas, monospace; font-size: 15px;")
        self.file.setAccessibleName(_("File del progetto"))
        s.addWidget(self.file)
        self.corpo.addWidget(self.esperti)
        self._esperti(False)
        self._file(False)

        self.corpo.addSpacing(8)
        self.corpo.addWidget(etichetta(_("Prima di partire"), "sottotitolo"))
        self.stima, self.zona_stima = pannello()
        self.corpo.addWidget(self.stima)

        for l, valori, fmt in ((self.soglia, SOGLIE, lambda v: f"{virgola(v)} %"), (self.lunghezza, LUNGHEZZE, str)):
            for v in valori:
                l.addItem(fmt(v), v)
        self.completo.scelta.connect(self._kraken_cambiato)
        self.rapido.scelta.connect(self._kraken_cambiato)
        for w in (self.confidenza, self.soglia, self.letture, self.lunghezza):
            w.currentIndexChanged.connect(self._cambiato)
        self.virus.toggled.connect(self._cambiato)

    # ---------------- ingresso nella pagina ----------------
    def mostrata(self):
        svuota(self.zona_avvisi)
        info = self.contesto.info
        p = self.contesto.progetto
        if info:
            self.intro.setText(_("Ho già preparato le scelte consigliate per questo computer ({ram} GB di memoria, "
                                 "{processori} processori). Puoi partire subito.", ram=numero(info['ram_gb']),
                                 processori=info['processori']))
            for c in info.get("consigli", []):
                if c.get("livello") == "avviso":
                    self.zona_avvisi.addWidget(riquadro(_("Consiglio del motore"), c["messaggio"], "avviso"))
        else:
            self.intro.setText(_("Ho già preparato le scelte consigliate. Puoi partire subito."))
        if p is None:
            self.zona_avvisi.addWidget(riquadro(_("Nessun progetto aperto."), _("Apri un progetto o creane uno nuovo "
                                                                                "nella pagina I miei progetti."),
                                                "avviso"))
            self._barra(_("Vai ai miei progetti"), "", rimedio=(_("Vai ai miei progetti"), "home"))
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
        letture = profiling.get("bracken_min_reads")
        self._seleziona(self.letture, "" if letture in ("", None) else str(letture))
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
            self.confidenza.addItem(virgola(v) + (_(" (consigliato)") if v == consigliati["confidenza"] else ""), v)
        self.confidenza.blockSignals(False)
        for i, v in enumerate(SOGLIE):
            self.soglia.setItemText(i, f"{virgola(v)} %" + (_(" (consigliato)") if v == consigliati["soglia"] else ""))
        for i, v in enumerate(LUNGHEZZE):
            self.lunghezza.setItemText(i, str(v) + (_(" (consigliato)") if v == LUNGHEZZA_CONSIGLIATA else ""))
        prima_letture = self.letture.currentData()
        self.letture.blockSignals(True)
        self.letture.clear()
        for v in LETTURE:
            self.letture.addItem(v + (_(" (consigliato)") if v == consigliati["letture"] else ""), v)
        self.letture.blockSignals(False)
        self._seleziona(self.letture, prima_letture or "")
        self._seleziona(self.confidenza, prima or "")

    def _seleziona(self, menu, valore):
        """Seleziona un valore; vuoto (o sconosciuto) = il consigliato del database."""
        consigliati = self.profili[self._profilo()]
        if valore in ("", None):
            valore = {self.confidenza: consigliati["confidenza"], self.soglia: consigliati["soglia"],
                      self.letture: consigliati["letture"], self.lunghezza: LUNGHEZZA_CONSIGLIATA}[menu]
        i = menu.findData(valore)
        if i >= 0:
            menu.setCurrentIndex(i)

    # ---------------- scelte cambiate ----------------
    def _kraken_cambiato(self):
        if self.carico:
            return
        seguono = [m for m in (self.confidenza, self.soglia) if m.currentText().endswith(_(" (consigliato)"))]
        self.carico = True
        self._confidenze()
        for menu in seguono:                      # seguiva il consigliato: segue quello del nuovo database
            self._seleziona(menu, "")
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
        letture = self.letture.currentData()
        profiling["bracken_min_reads"] = "" if letture == consigliati["letture"] else int(letture)
        profiling["bracken_readlen"] = self.lunghezza.currentData()
        if scelte:
            cfg.setdefault("app", {})["scelte"] = True
        p.scrivi(cfg)
        self.file.setPlainText(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))

    def _esperti(self, aperto):
        self.apri_esperti.setText(("▾ " if aperto else "▸ ") + _("Parametri per esperti (di solito non servono)"))
        self.esperti.setVisible(aperto)

    def _file(self, aperto):
        self.apri_file.setText(("▾ " if aperto else "▸ ") + _("Mostra il file del progetto (per riprodurre l'analisi)"))
        self.file.setVisible(aperto)

    # ---------------- stima ----------------
    def _avvia_stima(self):
        if self.client.in_corso():
            self.ancora = True
            return
        svuota(self.zona_stima)
        self.zona_stima.addWidget(etichetta(_("Chiedo al motore quanto tempo e spazio servono...")))
        self.avvisi, self.errore_stima = [], None
        self._barra(_("Avvia l'analisi"), _("Calcolo il tempo che serve..."))
        try:
            percorso = percorso_per_motore(self.contesto.progetto.config)
        except ValueError:
            self._errore({"codice": "CONFIG_NON_VALIDA", "messaggio": _("Il progetto non sta su un disco di questo "
                                                                        "computer."),
                          "cosa_fare": _("Crea il progetto nella cartella Documenti.")})
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
                                                                 "cosa_fare": _("Riprova la stima.")})
            self.errore_stima = None
            return
        self._mostra_stima(fine["risultato"], fine.get("messaggio", ""))

    def _mostra_stima(self, r, messaggio):
        svuota(self.zona_stima)
        lungo = any(a.get("codice") == "TEMPO_LUNGO" for a in self.avvisi)
        for a in self.avvisi:                                     # gli avvisi prima dei numeri (R9)
            titolo = _("Ci vorrà molto tempo.") if a.get("codice") == "TEMPO_LUNGO" else _("Attenzione")
            self.zona_stima.addWidget(riquadro(titolo, a["messaggio"], "avviso"))
        tempi = r.get("tempo_s") or {}
        totale = r.get("tempo_totale_s") or sum(v for v in tempi.values() if v)    # v0.3: totale del motore
        nomi = {"download": _("download"), "pulizia": _("pulizia"), "ospite": _("ospite"),
                "controllo_qualita": _("controlli"), "metaphlan": "MetaPhlAn", "kraken": "Kraken",
                "riepilogo": _("tabelle"), "referto": _("referto")}
        ordine = [k for k in nomi if k in tempi] + [k for k in tempi if k not in nomi]   # i dict arrivano in ordine alfabetico
        # solo i passi da almeno un minuto: quelli brevi (controlli, tabelle, referto) sono nel totale
        dettaglio = ", ".join(f"{nomi.get(k, k)} {durata(tempi[k])}" for k in ordine if (tempi[k] or 0) >= 60)
        coppie = r.get("coppie_totali") or 0
        campioni = r.get("campioni", 0)
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(24)
        griglia.setVerticalSpacing(6)
        nomi_campioni = r.get("nomi_campioni") or []                            # v0.3: i nomi del motore
        elenco = f": {', '.join(nomi_campioni[:6])}{'...' if len(nomi_campioni) > 6 else ''}" if nomi_campioni else ""
        righe = [(_("Campioni"), _("{campioni}{elenco} ({milioni} milioni di coppie di read)", campioni=campioni,
                                   elenco=elenco, milioni=numero(coppie / 1e6, 1))),
                 (_("Tempo stimato"), _("circa {durata}", durata=durata(totale))
                  + (f" ({dettaglio})" if dettaglio else "")),
                 (_("Spazio che serve"), gb(r.get("spazio_gb", 0))
                  + (_(", ne hai {gb} liberi", gb=numero(r['spazio_libero_gb'], 0))
                     if r.get("spazio_libero_gb") is not None else ""))]
        for i, (nome, valore) in enumerate(righe):
            griglia.addWidget(etichetta(nome, "etichetta_campo"), i, 0)
            griglia.addWidget(etichetta(valore), i, 1)
        griglia.setColumnStretch(1, 1)
        self.zona_stima.addLayout(griglia)
        if messaggio:
            self.zona_stima.addWidget(etichetta(messaggio, "nota"))
        if self._profilo() == "completo" and tempi.get("kraken"):
            self.completo.spiega.setText(_("Trova anche le specie poco abbondanti. Più lento: per questo progetto "
                                           "circa {durata}.", durata=durata(tempi['kraken'])))
        aiuto = _("Tempo stimato: circa {durata}. Spazio: {gb}.", durata=durata(totale), gb=gb(r.get('spazio_gb', 0)))
        if lungo:
            aiuto += _(" Ci vorrà molto: leggi l'avviso qui sopra.")
        elif self.avvisi:
            aiuto += _(" Leggi l'avviso qui sopra.")
        secondari = [(_("Passa allo screening rapido"), self.passa_al_rapido)] \
            if lungo and self._profilo() == "completo" else []
        self._barra(_("Avvia l'analisi"), aiuto, "avviso" if self.avvisi else "", secondari)

    def _errore(self, e):
        svuota(self.zona_stima)
        self.zona_stima.addWidget(riquadro(_("Non riesco a stimare il tempo. ") + e.get("messaggio", ""),
                                           e.get("cosa_fare", ""), "errore"))
        testo, pagina = RIMEDI.get(e.get("codice"), (N_("Riprova la stima"), None))
        self._barra(_(testo), _("Prima di partire va risolto il problema scritto qui sopra."), "avviso",
                    rimedio=(_(testo), pagina))

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
            _testo, pagina = self.rimedio
            if pagina:
                self.vai.emit(pagina)
            else:
                self._avvia_stima()
            return
        self._salva(scelte=True)
        self.contesto.avvia_analisi = True       # "Analisi in corso" (S6) lancia esegui e lo rimette a False
        self.vai.emit("esecuzione")

