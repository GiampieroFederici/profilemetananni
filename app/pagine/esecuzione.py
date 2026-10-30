"""Pagina "Analisi in corso" (S6, docs/interfaccia_S4.md §3.3): lancia `esegui`, mostra barra, tempo che manca,
i 7 passi del contratto e gli avvisi; si può fermare (`annulla`) e riprendere. Mostra, non calcola (R11).

Parte solo se "Scelte" ha messo contesto.avvia_analisi = True: entrare dal percorso non lancia nulla.
Fra due eventi un orologio locale fa scendere il tempo che manca e avanzare la barra (un passo lungo come
Kraken dura anche mezz'ora): parte dagli ultimi eta_s e percentuale del motore, non stima nulla da sé.
"""
import time
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QGridLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget

from app.lingua import N_, _
from app.motore import MotoreClient, percorso_per_motore
from app.pagine.base import Pagina, etichetta, numero, riquadro
from app.pagine.risultati import leggi_risultati

PASSI = [("download", N_("Scarico le read")), ("controllo_qualita", N_("Controllo la qualità")),
         ("pulizia", N_("Pulisco le read")), ("ospite", N_("Tolgo il DNA dell'ospite")),
         ("metaphlan", N_("Profilo con MetaPhlAn")), ("kraken", N_("Profilo con Kraken")),
         ("riepilogo", N_("Preparo referto e tabelle"))]
SEGNI = {"fatto": "✓", "ora": "●", "errore": "✗", "": "○"}
COLORI = {"fatto": "#1C2B27", "ora": "#1E7A4C", "errore": "#A8251C", "": "#52625D"}
# R8: il pulsante principale porta dove l'errore si risolve; gli altri errori si riprovano (esegui è riprendibile)
RIMEDI = {"DB_MANCANTE": (N_("Apri la pagina Motore"), "motore"),
          "DB_ROVINATO": (N_("Apri la pagina Motore"), "motore"),
          "MOTORE_NON_AVVIATO": (N_("Apri la pagina Motore"), "motore"),
          "READ_NON_TROVATE": (N_("Correggi i campioni"), "campioni"),
          "CONFIG_NON_VALIDA": (N_("Correggi le scelte"), "scelte"), "GIA_IN_CORSO": (N_("Torna ai progetti"), "home")}
TITOLI_AVVISO = {"TEMPO_LUNGO": N_("Ci vorrà molto tempo"), "CAMPIONE_DA_CONTROLLARE": N_("Campione da controllare"),
                 "CAMPIONE_DA_RIFARE": N_("Campione da rifare"), "RETE_INTERROTTA": N_("La rete si è interrotta"),
                 "REFERTO_PARZIALE": N_("Il referto non è completo")}
ANCORA = N_("Puoi usare il computer per altro. Se lo spegni, i passi già finiti restano salvati: quando riapri il "
            "progetto, premi Riprendi l'analisi.")
NOTA_ETA = N_("tempo che manca, stimato")


def durata(secondi):
    """Formatta i secondi stimati dal motore: '45 secondi', '12 minuti', '1,5 ore'."""
    if secondi < 90:
        return _("{n} secondi", n=round(secondi))
    if secondi < 5400:
        return _("{n} minuti", n=round(secondi / 60))
    return _("{n} ore", n=numero(secondi / 3600))


class PaginaEsecuzione(Pagina):
    titolo = N_("Analisi in corso")

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
        self.orologio = QTimer(self)                 # fra due eventi: il tempo che manca scende da solo
        self.orologio.setInterval(1000)
        self.orologio.timeout.connect(self._scorre)
        self.ultimo = None                           # (istante, percentuale, eta_s) dell'ultimo avanzamento

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
        self.eta_nota = etichetta(_(NOTA_ETA), "nota")
        fatto = etichetta(_("fatto"), "nota")
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
            self.passi[chiave] = (e, _(testo))
            gp.addWidget(e, i % 4, i // 4)
        gp.setColumnStretch(2, 1)
        self.ancora = etichetta(_(ANCORA), "nota")

        self.dettagli = QPushButton("▸ " + _("Dettagli tecnici"), objectName="link")
        self.dettagli.setCheckable(True)
        self.dettagli.toggled.connect(self._dettagli)
        self.registro = etichetta("", "nota")
        self.registro.hide()
        self.percorso_log = ""                    # B2-13: il registro si apre con un clic, senza copiare percorsi
        self.apri_registro = QPushButton(_("Apri il registro"), objectName="secondario")
        self.apri_registro.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.percorso_log)))
        self.apri_registro.hide()
        self.invito = etichetta("")

        for w in (self.messaggio, self.barra, self.numeri):
            self.corpo.addWidget(w)
        self.corpo.addLayout(self.avvisi)
        for w in (self.passi_box, self.ancora, self.invito):
            self.corpo.addWidget(w)
        self.corpo.addWidget(self.dettagli, 0, Qt.AlignLeft)
        self.corpo.addWidget(self.registro)
        self.corpo.addWidget(self.apri_registro, 0, Qt.AlignLeft)
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
        self.progetto_corsa.segno_analisi.write_text(f"{datetime.now():%d/%m/%Y %H:%M}\n", encoding="utf-8")   # P11
        self.registro.setText("")
        self.percorso_log = ""
        self._svuota_avvisi()
        self._passi(None)
        self.messaggio.setText(_("Avvio l'analisi..."))
        self.barra.setValue(0)
        self.pct.setText("0 %")
        self.ultimo = None
        self.eta.setText("")
        self._mostra()
        self.respira.emit(True)
        self.client.avvia("esegui", "--progetto", percorso_per_motore(self.contesto.progetto.config))

    # ---------------- eventi del motore ----------------
    def _evento(self, e):
        tipo = e["tipo"]
        if tipo == "inizio":
            self.registro.setText(_("Registro tecnico, da mandarci se c'è un problema:") + f"\n{e.get('log', '')}")
            self.percorso_log = e.get("log", "")
        elif tipo == "avanzamento":
            self.messaggio.setText(e["messaggio"])
            pct = max(e.get("percentuale") or 0, self.barra.value())   # la barra non torna indietro
            self.barra.setValue(round(pct))
            self.pct.setText(f"{numero(pct, 0)} %")
            self.eta.setText(durata(e["eta_s"]) if e.get("eta_s") is not None else "")
            self.eta_nota.setVisible(e.get("eta_s") is not None)      # null: non lo diciamo
            self._passi(e.get("passo"))
            self.ultimo_passo = e.get("passo")
            self.eta_nota.setText(_(NOTA_ETA))
            # passo_s (17/10): quanto dura questo passo; senza, l'orologio può scendere fino alla fine
            self.ultimo = (time.monotonic(), pct, e["eta_s"], e.get("passo_s")) if e.get("eta_s") else None
            if self.ultimo:
                self.orologio.start()
            else:
                self.orologio.stop()
        elif tipo == "avviso":
            self.avvisi.addWidget(riquadro(_(TITOLI_AVVISO.get(e.get("codice"), N_("Da sapere"))), e["messaggio"],
                                           "avviso"))
        elif tipo == "errore":
            self.errore = e
            self._svuota_avvisi(solo_errori=True)
            self.avvisi.insertWidget(0, riquadro(e["messaggio"], e.get("cosa_fare", ""), "errore"))
            self._passi(e.get("passo"), errore=True)
        elif tipo == "fine":
            self.orologio.stop()
            self.messaggio.setText(e["messaggio"])
            if e["esito"] == "ok":
                self.barra.setValue(100)
                self.pct.setText("100 %")
                self._passi("tutti")

    def _scorre(self):
        """Ogni secondo: tempo che manca = eta_s meno il tempo passato, ma solo dentro il passo in corso (passo_s);
        la barra va verso 100 allo stesso passo. Se il passo dura più del previsto, il tempo e la barra si fermano a
        quello che resta dopo il passo e la nota lo dice; se era l'ultimo, "qualche minuto"."""
        if not self.ultimo or self.stato != "in_corso":
            self.orologio.stop()
            return
        t0, pct0, eta0, passo_s = self.ultimo
        passati = time.monotonic() - t0
        dentro = min(passati, eta0 if passo_s is None else passo_s)
        resto = eta0 - dentro
        self.eta.setText(durata(resto) if resto >= 1 else _("qualche minuto"))
        if passo_s is not None and passati > passo_s and resto >= 1:
            self.eta_nota.setText(_("tempo che manca dopo questo passo, che sta durando più del previsto"))
        pct = min(99, pct0 + (100 - pct0) * dentro / eta0)
        if round(pct) > self.barra.value():
            self.barra.setValue(round(pct))
            self.pct.setText(f"{numero(pct, 0)} %")

    def _finito(self, codice, fine):
        self.orologio.stop()
        self.respira.emit(False)
        self.contesto.progetto_in_analisi = None
        self.stato = {"ok": "ok", "annullata": "annullata"}.get(fine.get("esito"), "errore")
        if self.stato == "ok" and self.progetto_corsa is not None:
            self.progetto_corsa.segno_analisi.unlink(missing_ok=True)   # P11: finita, niente da riprendere
        if self.stato == "annullata":         # il passo a metà si rifà quando riparte
            self._passi(self.ultimo_passo, fermo=True)
        self._mostra()
        self.analisi_finita.emit()

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
            e.setAccessibleName(f"{testo}: {({'fatto': _('fatto'), 'ora': _('in corso'), 'errore': _('fermo qui')}).get(stato, _('da fare'))}")

    def _svuota_avvisi(self, solo_errori=False):
        for i in reversed(range(self.avvisi.count())):
            w = self.avvisi.itemAt(i).widget()
            if w and (not solo_errori or w.property("livello") == "errore"):
                w.setParent(None)

    def _dettagli(self, aperto):
        self.dettagli.setText(("▾" if aperto else "▸") + " " + _("Dettagli tecnici"))
        self.registro.setVisible(aperto and bool(self.registro.text()))
        self.apri_registro.setVisible(aperto and bool(self.percorso_log))

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
        titolo = {"vuota": _("Analisi in corso"), "in_corso": _("Analisi in corso"),
                  "ferma_chiesto": _("Analisi in corso"), "ok": _("Analisi finita"), "annullata": _("Analisi fermata"),
                  "errore": _("L'analisi si è fermata")}[s]
        if s == "vuota":
            progetto = self.contesto.progetto
            if progetto is None:
                self.invito.setText(_("Nessun progetto aperto. Apri un progetto o creane uno nuovo."))
                self.testo_principale, self.destinazione = _("Apri i miei progetti"), "home"
            elif progetto.interrotta:            # B2 (P11): app chiusa o computer spento a metà
                self.invito.setText(_("L'analisi di questo progetto si è interrotta (programma chiuso o computer "
                                      "spento). I passi già finiti sono salvati: riprendo da quello a metà."))
                self.testo_principale = _("Riprendi l'analisi")
            elif leggi_risultati(progetto) is not None:
                self.invito.setText(_("Nessuna analisi in corso. I risultati dell'ultima analisi sono pronti."))
                self.testo_principale, self.destinazione = _("Vedi i risultati"), "risultati"
            else:
                self.invito.setText(_("Nessuna analisi in corso. Per avviarne una, apri le scelte dell'analisi "
                                      "e premi Avvia l'analisi."))
                self.testo_principale, self.destinazione = _("Vai alle scelte dell'analisi"), "scelte"
        elif s == "in_corso":
            self.testo_principale = _("Ferma l'analisi")
            self.aiuto = _("Passo 3 di 4")
        elif s == "ferma_chiesto":
            self.testo_principale = _("Mi sto fermando...")
            self.aiuto = _("Chiedo al motore di fermarsi: finisco di salvare e mi fermo.")
        elif s == "ok":
            self.testo_principale, self.destinazione = _("Vedi i risultati"), "risultati"
            self.eta.setText("")
            self.eta_nota.hide()
        elif s == "annullata":
            self.testo_principale = _("Riprendi l'analisi")
            self.aiuto = _("I passi già finiti sono salvati: riprendo da quello a metà. Puoi anche spegnere il "
                           "computer e riprendere dopo.")
            self.eta.setText("")
            self.eta_nota.hide()
        else:
            codice = (self.errore or {}).get("codice")
            testo, self.destinazione = RIMEDI.get(codice, (N_("Riprova l'analisi"), None))
            self.testo_principale = _(testo)
            self.aiuto, self.aiuto_livello = _("Leggi qui sopra che cosa è successo e che cosa fare."), "avviso"
            self.eta.setText(_("ferma"))
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
        elif self.stato == "vuota" and self.contesto.progetto is not None and self.contesto.progetto.interrotta:
            self._lancia()
        else:
            super().azione_principale()

    def conferma(self):
        """Chiede se fermare davvero (i test la sostituiscono)."""
        m = QMessageBox(self)
        m.setWindowTitle(_("Fermare l'analisi?"))
        m.setIcon(QMessageBox.Question)
        m.setText(_("Fermare l'analisi?"))
        m.setInformativeText(_("I passi già finiti restano salvati. Quello a metà si rifà quando riparti. Puoi anche "
                               "chiudere il programma e spegnere il computer: quando riapri il progetto, premi "
                               "Riprendi l'analisi."))
        si = m.addButton(_("Ferma l'analisi"), QMessageBox.AcceptRole)
        no = m.addButton(_("Continua l'analisi"), QMessageBox.RejectRole)
        m.setDefaultButton(no)
        m.exec()
        return m.clickedButton() is si
