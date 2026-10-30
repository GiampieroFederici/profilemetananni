"""Pagina "Motore" (S5b, docs/interfaccia_S4.md §3.6): stato del motore con i dati di `info`, "Controlla il
motore" (`verifica`, VERDE o ROSSO con i controlli) e "Installa o completa" (`installa`, con la barra).
Durante un lavoro lungo l'avatar della testata respira (D046). Gli errori mostrano `messaggio` e `cosa_fare` (R8).
"""
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QProgressBar, QScrollArea, QVBoxLayout

from app.lingua import N_, _
from app.motore import MotoreClient, spazio_windows_gb
from app.pagine.base import Pagina, etichetta, numero, pannello, riquadro, svuota

NOMI_DB = {"metaphlan_fette_vJan25_v1": N_("MetaPhlAn, database in 6 parti"),
           "kraken_pluspf_20260626": N_("Kraken, database completo"),
           "kraken_pluspf_08gb_20260626": N_("Kraken, screening rapido"),
           "ospite_maiale_bovino_pecora_uomo": N_("DNA da togliere: maiale, bovino, pecora, uomo"),   # finto motore
           # P42: i nomi del motore vero (pmn_motore.elenco_database)
           "metaphlan_pkl_vJan25": N_("MetaPhlAn, database intero"),
           "ospite_sus_scrofa": N_("DNA da togliere: maiale"),
           "ospite_bos_taurus": N_("DNA da togliere: bovino"),
           "ospite_ovis_aries": N_("DNA da togliere: pecora"),
           "ospite_homo_sapiens": N_("DNA da togliere: uomo")}
NOMI_PROGRAMMI = {"metaphlan": "MetaPhlAn", "kraken2": "Kraken", "bracken": "Bracken", "bowtie2": "Bowtie 2",
                  "fastp": "fastp"}
NON_AVVIATO = N_("Il motore fa i calcoli in uno spazio Linux dentro Windows (si chiama WSL, il sottosistema Windows per "
                 "Linux). Su questo computer non lo trovo, oppure non parte. Si installa una volta sola con il programma "
                 "di installazione di ProfileMetaNanni (installa_pmn); poi torna qui e premi Controlla il motore.")
DA_INSTALLARE = {"DB_MANCANTE", "DB_ROVINATO", "VERIFICA_ROSSA", "PROGRAMMA_MANCANTE"}   # si risolve con installa (R8)
COLORI = {"verde": "#1E7A4C", "rosso": "#A8251C", "ambra": "#9A5A00"}


class PaginaMotore(Pagina):
    titolo = N_("Motore")
    testo_principale = N_("Controlla il motore")

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.client = MotoreClient(self)
        self.client.evento.connect(self._evento)
        self.client.finito.connect(self._finito)
        self.client_info = MotoreClient(self)       # info a parte: non blocca verifica e installa
        self.client_info.evento.connect(self._evento_info)
        self.client_info.finito.connect(self._finito_info)
        self.errore_info = None
        self.errore_corsa = None
        self.da_installare = False
        self._in_fondo = False
        self._barra_scorre = None
        self.corpo.addWidget(etichetta(_("Il motore fa i calcoli dentro Windows, in uno spazio Linux tutto suo. "
                                         "Si installa una volta e si controlla da qui.")))
        self.zona_avvisi = QVBoxLayout()
        self.corpo.addLayout(self.zona_avvisi)

        p, s = pannello()
        riga = QHBoxLayout()
        self.pallino = QLabel()
        self.pallino.setFixedSize(14, 14)
        riga.addWidget(self.pallino)
        self.stato_titolo = etichetta("", "etichetta_campo")
        riga.addWidget(self.stato_titolo, 1)
        s.addLayout(riga)
        self.griglia = QGridLayout()
        self.griglia.setHorizontalSpacing(28)
        self.griglia.setVerticalSpacing(6)
        self.griglia.setColumnStretch(3, 1)
        s.addLayout(self.griglia)
        self.stato = etichetta("", "nota")
        s.addWidget(self.stato)
        self.corpo.addWidget(p)

        self.lavoro = QVBoxLayout()               # barra e messaggio durante verifica o installa (R7)
        self.messaggio = etichetta("")
        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(12)
        self.lavoro.addWidget(self.messaggio)
        self.lavoro.addWidget(self.barra)
        self.corpo.addLayout(self.lavoro)
        self._lavoro(False)
        self.zona_esito = QVBoxLayout()
        self.corpo.addLayout(self.zona_esito)
        self._barra_azioni()

    # ---------------- stato da info ----------------
    def mostrata(self):
        self._disegna()
        self._barra_azioni()                    # un'analisi può essere partita o finita da quando la pagina è nata
        if self.contesto.info is None:
            self._aggiorna()                    # per sapere perché non risponde (per esempio MOTORE_NON_AVVIATO)

    def _aggiorna(self):
        if not self.client_info.in_corso():
            self.errore_info = None
            self.client_info.avvia("info")

    def _evento_info(self, e):
        if e["tipo"] == "errore":
            self.errore_info = e

    def _finito_info(self, codice, fine):
        self.contesto.info = fine["risultato"] if fine.get("esito") == "ok" else None
        self._disegna(self.errore_info)
        self.info_cambiata.emit()                # pallino della testata (dopo installa)

    def _disegna(self, errore=None):
        svuota(self.zona_avvisi)
        while self.griglia.count():
            self.griglia.takeAt(0).widget().deleteLater()
        i = self.contesto.info
        if i is None:
            self._pallino("rosso")
            self.stato_titolo.setText(_("Il motore non risponde"))
            self.stato.setText(_("Quando il motore risponde, qui vedi i database installati e com'è fatto questo "
                                 "computer."))
            if errore and errore.get("codice") == "MOTORE_NON_AVVIATO":
                self.zona_avvisi.addWidget(riquadro(_("Su questo computer il motore non c'è ancora, o non parte."),
                                                    _(NON_AVVIATO), "errore"))
            elif errore:
                self.zona_avvisi.addWidget(riquadro(errore.get("messaggio", ""), errore.get("cosa_fare", ""),
                                                    "errore"))
            return
        database = i.get("database", [])
        manca = [d for d in database if not d.get("installato")]
        if manca:
            self._pallino("ambra")
            self.stato_titolo.setText(_("Installato, ma manca qualcosa: premi Installa o completa"))
        else:
            self._pallino("verde")
            self.stato_titolo.setText(_("Installato e pronto") + (_(" (motore di prova)") if i.get("finto") else ""))
        for riga, d in enumerate(database):
            self.griglia.addWidget(QLabel(_(NOMI_DB[d["nome"]]) if d["nome"] in NOMI_DB else
                                          _("Altro database ({nome})", nome=d['nome'])), riga, 0)
            self.griglia.addWidget(QLabel(_("installato") if d.get("installato") else _("manca")), riga, 1)
            self.griglia.addWidget(QLabel(f"{numero(d['gb'])} GB" if d.get("gb") is not None else ""), riga, 2)
        programmi = i.get("programmi") or {}          # i dict arrivano in ordine alfabetico: quello dei passi
        ordine = [k for k in NOMI_PROGRAMMI if k in programmi] + [k for k in programmi if k not in NOMI_PROGRAMMI]
        versioni = ", ".join(f"{NOMI_PROGRAMMI.get(k, k)} {programmi[k]}" for k in ordine)
        libero = i['spazio_libero_gb']
        windows = None if i.get("finto") else spazio_windows_gb()      # B2 (P8): il disco vero sotto quello virtuale
        if windows is not None:
            libero = min(libero, windows)
        self.stato.setText(_("Questo computer: {ram} GB di memoria, {processori} processori, {libero} GB liberi. "
                             "Versioni: {versioni}.", ram=numero(i['ram_gb']), processori=i['processori'],
                             libero=numero(libero, 0), versioni=versioni))
        for c in i.get("consigli", []):
            if c.get("livello") == "avviso":
                self.zona_avvisi.addWidget(riquadro(_("Consiglio del motore"), c["messaggio"], "avviso"))

    def _pallino(self, colore):
        self.pallino.setStyleSheet(f"background: {COLORI[colore]}; border-radius: 7px;")

    # ---------------- verifica e installa ----------------
    def azione_principale(self):
        self._avvia("installa" if self.da_installare else "verifica")

    def verifica(self):
        self._avvia("verifica")

    def installa(self):
        self._avvia("installa")

    def _avvia(self, comando):
        # verifica e installa fanno girare MetaPhlAn sul mini-campione: mai insieme a un'analisi (P10, memoria)
        if self.client.in_corso() or self.contesto.progetto_in_analisi is not None:
            return
        svuota(self.zona_esito)
        self._in_fondo = False
        self.errore_corsa = None
        self.da_installare = False
        self.barra.setValue(0)
        self.messaggio.setText(_("Controllo il motore...") if comando == "verifica" else _("Preparo l'installazione..."))
        self._lavoro(True)
        self.respira.emit(True)
        # R3 (v1.1): dentro la WSL il motore vede il disco virtuale; lo spazio vero di Windows decide se tenere i pezzi
        libero = spazio_windows_gb() if comando == "installa" else None
        self.client.avvia(comando, *(["--spazio-libero", str(int(libero * 1e9))] if libero is not None else []))
        self._barra_azioni()

    def ferma(self):
        self.client.annulla()

    def _evento(self, e):
        if e["tipo"] == "avanzamento":
            self.messaggio.setText(e["messaggio"])
            if e.get("percentuale") is not None:
                self.barra.setValue(round(e["percentuale"]))
        elif e["tipo"] == "avviso":
            self.zona_esito.addWidget(riquadro(_("Attenzione"), e["messaggio"], "avviso"))
        elif e["tipo"] == "errore":
            self.errore_corsa = e

    def _finito(self, codice, fine):
        self.respira.emit(False)
        self._lavoro(False)
        self._esito(self.client.comando, fine)
        self._barra_azioni()
        self._aggiorna()                        # database e spazio aggiornati dopo il lavoro

    def _esito(self, comando, fine):
        e = self.errore_corsa
        if e:
            if e.get("codice") == "MOTORE_NON_AVVIATO":
                self.zona_esito.addWidget(riquadro(_("Su questo computer il motore non c'è ancora, o non parte."),
                                                   _(NON_AVVIATO), "errore"))
            else:
                self.da_installare = e.get("codice") in DA_INSTALLARE
                titolo = _("ROSSO: {messaggio}", messaggio=e['messaggio']) if comando == "verifica" else e["messaggio"]
                self.zona_esito.addWidget(riquadro(titolo, e.get("cosa_fare", ""), "errore"))
            return
        if fine.get("esito") == "annullata":
            self.zona_esito.addWidget(riquadro(fine.get("messaggio", ""), _("Premi Installa o completa per "
                                                                            "riprendere da dove si era fermata."),
                                               "info"))
            return
        r = fine.get("risultato") or {}
        controlli = r.get("controlli") or []
        righe = "\n".join(f"{'✓' if c.get('esito') == 'ok' else '✗'} {c.get('nome', '')}" for c in controlli)
        rosso = r.get("esito") == "rosso"
        self.da_installare = rosso
        self.zona_esito.addWidget(riquadro(fine.get("messaggio", ""), righe, "errore" if rosso else "info"))
        self._esito_in_vista()

    def _esito_in_vista(self):
        """B2 (P7): l'esito sta in fondo alla pagina; su uno schermo piccolo restava sotto la piega. Si scorre fino in
        fondo, anche quando l'impaginazione cresce dopo (le etichette vanno a capo in più giri)."""
        scorre = self.parentWidget() and self.parentWidget().parentWidget()      # viewport, poi QScrollArea (finestra.py)
        if not isinstance(scorre, QScrollArea):
            return
        b = scorre.verticalScrollBar()
        if self._barra_scorre is None:                                          # un solo collegamento
            self._barra_scorre = b
            b.rangeChanged.connect(lambda _min, massimo: self._in_fondo and b.setValue(massimo))
        self._in_fondo = True                                                   # fino al prossimo controllo
        b.setValue(b.maximum())

    def _lavoro(self, si):
        self.messaggio.setVisible(si)
        self.barra.setVisible(si)

    def _barra_azioni(self):
        lavora = self.client.in_corso() and self.client.comando in ("verifica", "installa")
        analisi = self.contesto.progetto_in_analisi is not None
        self.principale_attivo = not lavora and not analisi
        self.testo_principale = _("Installa o completa") if self.da_installare and not lavora else \
            _("Controlla il motore")
        if lavora and self.client.comando == "installa":
            self.secondari = [(_("Ferma l'installazione"), self.ferma)]
            self.aiuto = _("L'installazione può durare a lungo: puoi usare il computer per altro.")
        elif analisi:
            self.secondari = []
            self.aiuto = _("C'è un'analisi in corso: controlla o installa il motore quando è finita.")
        elif lavora:
            self.secondari = []
            self.aiuto = _("Controllo in corso: qualche minuto.")
        elif self.da_installare:
            self.secondari = [(_("Controlla il motore"), self.verifica)]
            self.aiuto = _("Per risolvere il problema scritto qui sopra installa o completa il motore.")
        else:
            self.secondari = [(_("Installa o completa"), self.installa)]
            self.aiuto = _("Il controllo prova i database e un piccolo campione (qualche minuto).")
        self.azioni_cambiate.emit()
