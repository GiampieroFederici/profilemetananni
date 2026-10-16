"""Pagina "Analisi in corso" (S6, docs/interfaccia_S4.md §3.3): lancia `esegui`, mostra barra, tempo che manca,
i 7 passi del contratto e gli avvisi; si può fermare (`annulla`) e riprendere. Mostra, non calcola (R11).

Parte solo se "Scelte" ha messo contesto.avvia_analisi = True: entrare dal percorso non lancia nulla.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget

from app.motore import MotoreClient, percorso_per_motore
from app.pagine.base import Pagina, etichetta, numero, riquadro
from app.pagine.risultati import leggi_risultati

PASSI = [("download", "Scarico le read"), ("controllo_qualita", "Controllo la qualità"),
         ("pulizia", "Pulisco le read"), ("ospite", "Tolgo il DNA dell'ospite"),
         ("metaphlan", "Profilo con MetaPhlAn"), ("kraken", "Profilo con Kraken"),
         ("riepilogo", "Preparo referto e tabelle")]
SEGNI = {"fatto": "✓", "ora": "●", "errore": "✗", "": "○"}
COLORI = {"fatto": "#1C2B27", "ora": "#1E7A4C", "errore": "#A8251C", "": "#52625D"}
# R8: il pulsante principale porta dove l'errore si risolve; gli altri errori si riprovano (esegui è riprendibile)
RIMEDI = {"DB_MANCANTE": ("Apri la pagina Motore", "motore"), "DB_ROVINATO": ("Apri la pagina Motore", "motore"),
          "MOTORE_NON_AVVIATO": ("Apri la pagina Motore", "motore"),
          "READ_NON_TROVATE": ("Correggi i campioni", "campioni"),
          "CONFIG_NON_VALIDA": ("Correggi le scelte", "scelte"), "GIA_IN_CORSO": ("Torna ai progetti", "home")}
TITOLI_AVVISO = {"TEMPO_LUNGO": "Ci vorrà molto tempo", "CAMPIONE_DA_CONTROLLARE": "Campione da controllare",
                 "CAMPIONE_DA_RIFARE": "Campione da rifare", "RETE_INTERROTTA": "La rete si è interrotta",
                 "REFERTO_PARZIALE": "Il referto non è completo"}
ANCORA = "Puoi usare il computer per altro. Se lo spegni, alla riaccensione l'analisi riparte dai passi non finiti."


def durata(secondi):
    """Formatta i secondi stimati dal motore: '45 secondi', '12 minuti', '1,5 ore'."""
    if secondi < 90:
        return f"{round(secondi)} secondi"
    if secondi < 5400:
        return f"{round(secondi / 60)} minuti"
    return f"{numero(secondi / 3600)} ore"


class PaginaEsecuzione(Pagina):
    titolo = "Analisi in corso"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.titolo_pagina = self.findChild(QLabel, "titolo")
        self.client = MotoreClient(self)
        self.client.evento.connect(self._evento)
        self.client.finito.connect(self._finito)
        self.stato = "vuota"          # vuota, in_corso, ferma_chiesto, ok, annullata, errore
        self.errore = None
        self.ultimo_passo = None
        self.progetto_corsa = None

        self.messaggio = etichetta("")
        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(26)
        self.barra.setStyleSheet("QProgressBar { background: #DDE5E1; border: 0; border-radius: 13px; }"
                                 "QProgressBar::chunk { background: #1E7A4C; border-radius: 13px; }")
        self.numeri = QWidget()
        g = QGridLayout(self.numeri)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(48)
        self.pct = etichetta("", "grande")
        self.eta = etichetta("", "grande")
        for e in (self.pct, self.eta):
            e.setStyleSheet("font-size: 40px; font-weight: bold;")
        self.eta_nota = etichetta("tempo che manca, stimato", "nota")
        fatto = etichetta("fatto", "nota")
        for e in (self.pct, self.eta, fatto, self.eta_nota):
            e.setWordWrap(False)
        g.addWidget(self.pct, 0, 0)
        g.addWidget(self.eta, 0, 1)
        g.addWidget(fatto, 1, 0)
        g.addWidget(self.eta_nota, 1, 1)
        g.setColumnStretch(2, 1)

        self.avvisi = QVBoxLayout()           # R9: sotto la barra, vicino a ciò che riguardano
        self.passi_box = QWidget()
        gp = QGridLayout(self.passi_box)
        gp.setContentsMargins(0, 8, 0, 8)
        gp.setHorizontalSpacing(40)
        gp.setVerticalSpacing(10)
        self.passi = {}
        for i, (chiave, testo) in enumerate(PASSI):
            e = etichetta("")
            e.setWordWrap(False)
            self.passi[chiave] = (e, testo)
            gp.addWidget(e, i % 4, i // 4)
        gp.setColumnStretch(2, 1)
        self.ancora = etichetta(ANCORA, "nota")

        self.dettagli = QPushButton("▸ Dettagli tecnici", objectName="link")
        self.dettagli.setCheckable(True)
        self.dettagli.toggled.connect(self._dettagli)
        self.registro = etichetta("", "nota")
        self.registro.hide()
        self.invito = etichetta("")

        for w in (self.messaggio, self.barra, self.numeri):
            self.corpo.addWidget(w)
        self.corpo.addLayout(self.avvisi)
        for w in (self.passi_box, self.ancora, self.invito):
            self.corpo.addWidget(w)
        self.corpo.addWidget(self.dettagli, 0, Qt.AlignLeft)
        self.corpo.addWidget(self.registro)
        self._mostra()

    # ---------------- avvio ----------------
    def mostrata(self):
        if not self.contesto.avvia_analisi:
            if not self.client.in_corso() and self.progetto_corsa is not self.contesto.progetto:
                self.stato = "vuota"          # un altro progetto: lo stato della corsa di prima non vale più
            if self.stato == "vuota":
                self._mostra()
            return
        self.contesto.avvia_analisi = False
        if self.client.in_corso() or self.contesto.progetto is None:
            return
        self._lancia()

    def _lancia(self):
        self.stato, self.errore, self.ultimo_passo = "in_corso", None, None
        self.progetto_corsa = self.contesto.progetto
        self.contesto.progetto_in_analisi = self.progetto_corsa      # intanto non se ne apre un altro
        self.registro.setText("")
        self._svuota_avvisi()
        self._passi(None)
        self.messaggio.setText("Avvio l'analisi...")
        self.barra.setValue(0)
        self.pct.setText("0 %")
        self.eta.setText("")
        self._mostra()
        self.respira.emit(True)
        self.client.avvia("esegui", "--progetto", percorso_per_motore(self.contesto.progetto.config))

    # ---------------- eventi del motore ----------------
    def _evento(self, e):
        tipo = e["tipo"]
        if tipo == "inizio":
            self.registro.setText(f"Registro tecnico, da mandarci se c'è un problema:\n{e.get('log', '')}")
        elif tipo == "avanzamento":
            self.messaggio.setText(e["messaggio"])
            self.barra.setValue(round(e.get("percentuale") or 0))
            self.pct.setText(f"{numero(e.get('percentuale') or 0, 0)} %")
            self.eta.setText(durata(e["eta_s"]) if e.get("eta_s") is not None else "")
            self.eta_nota.setVisible(e.get("eta_s") is not None)      # null: non lo diciamo
            self._passi(e.get("passo"))
            self.ultimo_passo = e.get("passo")
        elif tipo == "avviso":
            self.avvisi.addWidget(riquadro(TITOLI_AVVISO.get(e.get("codice"), "Da sapere"), e["messaggio"], "avviso"))
        elif tipo == "errore":
            self.errore = e
            self._svuota_avvisi(solo_errori=True)
            self.avvisi.insertWidget(0, riquadro(e["messaggio"], e.get("cosa_fare", ""), "errore"))
            self._passi(e.get("passo"), errore=True)
        elif tipo == "fine":
            self.messaggio.setText(e["messaggio"])
            if e["esito"] == "ok":
                self.barra.setValue(100)
                self.pct.setText("100 %")
                self._passi("tutti")

    def _finito(self, codice, fine):
        self.respira.emit(False)
        self.contesto.progetto_in_analisi = None
        self.stato = {"ok": "ok", "annullata": "annullata"}.get(fine.get("esito"), "errore")
        if self.stato == "annullata":         # il passo a metà si rifà quando riparte
            self._passi(self.ultimo_passo, fermo=True)
        self._mostra()

    # ---------------- disegno ----------------
    def _passi(self, attuale, errore=False, fermo=False):
        prima = attuale is not None
        for chiave, (e, testo) in self.passi.items():
            if attuale == "tutti":
                stato = "fatto"
            elif chiave == attuale:
                stato, prima = ("errore" if errore else "" if fermo else "ora"), False
            else:
                stato = "fatto" if prima else ""
            e.setText(f"{SEGNI[stato]}   {testo}")
            peso = "bold" if stato in ("ora", "errore") else "normal"
            e.setStyleSheet(f"color: {COLORI[stato]}; font-weight: {peso};")
            e.setAccessibleName(f"{testo}: {({'fatto': 'fatto', 'ora': 'in corso', 'errore': 'fermo qui'}).get(stato, 'da fare')}")

    def _svuota_avvisi(self, solo_errori=False):
        for i in reversed(range(self.avvisi.count())):
            w = self.avvisi.itemAt(i).widget()
            if w and (not solo_errori or w.property("livello") == "errore"):
                w.setParent(None)

    def _dettagli(self, aperto):
        self.dettagli.setText(("▾" if aperto else "▸") + " Dettagli tecnici")
        self.registro.setVisible(aperto and bool(self.registro.text()))

    def _mostra(self):
        s = self.stato
        lavoro = s != "vuota"
        for w in (self.messaggio, self.barra, self.numeri, self.passi_box, self.dettagli):
            w.setVisible(lavoro)
        self.ancora.setVisible(s in ("in_corso", "ferma_chiesto"))
        self.invito.setVisible(not lavoro)
        self.principale_attivo = s != "ferma_chiesto"
        self.aiuto, self.aiuto_livello, self.destinazione = "", "", None
        self.principale_pericolo = s == "in_corso"          # "Ferma l'analisi": bianco col bordo rosso
        titolo = {"vuota": "Analisi in corso", "in_corso": "Analisi in corso", "ferma_chiesto": "Analisi in corso",
                  "ok": "Analisi finita", "annullata": "Analisi fermata", "errore": "L'analisi si è fermata"}[s]
        if s == "vuota":
            progetto = self.contesto.progetto
            if progetto is None:
                self.invito.setText("Nessun progetto aperto. Apri un progetto o creane uno nuovo.")
                self.testo_principale, self.destinazione = "Apri i miei progetti", "home"
            elif leggi_risultati(progetto) is not None:
                self.invito.setText("Nessuna analisi in corso. I risultati dell'ultima analisi sono pronti.")
                self.testo_principale, self.destinazione = "Vedi i risultati", "risultati"
            else:
                self.invito.setText("Nessuna analisi in corso. Per avviarne una, apri le scelte dell'analisi "
                                    "e premi Avvia l'analisi.")
                self.testo_principale, self.destinazione = "Vai alle scelte dell'analisi", "scelte"
        elif s == "in_corso":
            self.testo_principale = "Ferma l'analisi"
            self.aiuto = "Passo 3 di 4"
        elif s == "ferma_chiesto":
            self.testo_principale = "Mi sto fermando..."
            self.aiuto = "Chiedo al motore di fermarsi: finisco di salvare e mi fermo."
        elif s == "ok":
            self.testo_principale, self.destinazione = "Vedi i risultati", "risultati"
            self.eta.setText("")
            self.eta_nota.hide()
        elif s == "annullata":
            self.testo_principale = "Riprendi l'analisi"
            self.aiuto = "I passi già finiti sono salvati: riprendo da quello a metà."
            self.eta.setText("")
            self.eta_nota.hide()
        else:
            codice = (self.errore or {}).get("codice")
            self.testo_principale, self.destinazione = RIMEDI.get(codice, ("Riprova l'analisi", None))
            self.aiuto, self.aiuto_livello = "Leggi qui sopra che cosa è successo e che cosa fare.", "avviso"
            self.eta.setText("ferma")
            self.eta_nota.hide()
        if self.titolo_pagina:
            self.titolo_pagina.setText(titolo)
        self.azioni_cambiate.emit()

    # ---------------- pulsante principale ----------------
    def azione_principale(self):
        if self.stato == "in_corso":
            if self.conferma() and self.client.annulla():
                self.stato = "ferma_chiesto"
                self._mostra()
        elif self.stato in ("annullata", "errore") and self.destinazione is None:
            self._lancia()
        else:
            super().azione_principale()

    def conferma(self):
        """Chiede se fermare davvero (i test la sostituiscono)."""
        m = QMessageBox(self)
        m.setWindowTitle("Fermare l'analisi?")
        m.setIcon(QMessageBox.Question)
        m.setText("Fermare l'analisi?")
        m.setInformativeText("I passi già finiti restano salvati. Quello a metà si rifà quando riparti.")
        si = m.addButton("Ferma l'analisi", QMessageBox.AcceptRole)
        no = m.addButton("Continua l'analisi", QMessageBox.RejectRole)
        m.setDefaultButton(no)
        m.exec()
        return m.clickedButton() is si
