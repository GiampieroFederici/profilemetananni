"""Pagina "Sicurezza alimentare" (S6, docs/interfaccia_S4.md §3.5): scenari di Listeria con i modelli FSSP.

Chiede i dati del prodotto, scrive la richiesta (contratto §5.4) e lancia `sicurezza --ingresso --progetto`:
il motore calcola (profilo MetaPhlAn del progetto, conta sul totale delle read, D075) e salva in
risultati/sicurezza/. Qui si mostra l'uscita così com'è: avvisi "fuori campo" prima dei numeri, una scheda per
scenario (ambra cresce, verde non cresce, grigio se non cresce ma fuori campo), grafico senza soglie di legge
(D074). "Aggiungi al referto" lancia `referto` (stesso referto, D076). L'interfaccia non calcola (R11).
"""
import html
import json
import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLineEdit, QPushButton,
                               QRadioButton, QSizePolicy, QVBoxLayout, QWidget)

from app.motore import MotoreClient, percorso_per_motore
from app.pagine.base import Pagina, etichetta, numero, pannello, riquadro
from app.pagine.risultati import leggi_risultati

ACIDI = [("lattico", "Acido lattico"), ("acetico", "Acido acetico"), ("diacetato", "Diacetato"),
         ("citrico", "Acido citrico"), ("sorbico", "Acido sorbico"), ("benzoico", "Acido benzoico")]
MODELLI = {"listeria": "Modello della Listeria", "listeria_lab": "Modello della Listeria con i batteri lattici",
           "lab": "Modello dei batteri lattici"}
BORDI = {"cresce": "6px solid #9A5A00", "ferma": "6px solid #1E7A4C", "incerto": "6px dashed #52625D"}
LISTERIA = "<i>Listeria</i>"


def leggi_numero(testo):
    """'3,5' o '3.5' -> 3.5; '1.000.000' -> 1000000.0; vuoto -> None. ValueError se non è un numero."""
    t = testo.strip().replace(" ", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    v = float(t)
    if not math.isfinite(v):
        raise ValueError(testo)
    return v


def due_cifre(x):
    """Formatta con 2 cifre significative (R11: solo arrotondamento): 16,95 -> '17'; 30023 -> '30.000'; 1.0 -> '1'."""
    if not x:
        return "0"
    cifre = 1 - math.floor(math.log10(abs(x)))
    testo = numero(round(x, cifre), max(0, cifre))
    return testo.rstrip("0").rstrip(",") if "," in testo else testo


def maiuscola(nome):
    return nome[:1].upper() + nome[1:]


class Grafico(QWidget):
    """log ufc/g nel tempo, dalle curve del motore. Nessuna soglia di legge (D074)."""
    COLORI = ["#D08A1E", "#9A5A00", "#7A4A10"]

    def __init__(self):
        super().__init__()
        self.serie = []
        self.setMinimumSize(400, 324)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName("Grafico: crescita prevista nel tempo")

    def imposta(self, previsioni):
        self.serie = []
        for i, p in enumerate(previsioni):
            c = p["curva"]
            self.serie.append((f"Listeria da {due_cifre(p['n0_listeria_ufc_g'])} ufc/g", self.COLORI[i % 3],
                               c["giorni"], c["log_listeria"]))
        if previsioni and previsioni[0]["curva"].get("log_lab"):
            c = previsioni[0]["curva"]
            self.serie.append(("batteri lattici", "#1E7A4C", c["giorni"], c["log_lab"]))
        self.update()

    def paintEvent(self, evento):
        if not self.serie:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        sx, dx, su, giu = 64, 16, 12, 102
        W, H = self.width() - sx - dx, self.height() - su - giu
        valori = [v for s in self.serie for v in s[3]]
        ymin, ymax = min(0, math.floor(min(valori))), math.ceil(max(valori) + 0.5)
        gmax = max(s[2][-1] for s in self.serie) or 1
        X = lambda g: sx + W * g / gmax                      # noqa: E731 (solo disegno)
        Y = lambda v: su + H - H * (v - ymin) / ((ymax - ymin) or 1)   # noqa: E731
        testo, piccolo = QFont(self.font()), QFont(self.font())
        testo.setPixelSize(15)
        piccolo.setPixelSize(11)
        passo = 2 if ymax - ymin > 6 else 1
        for v in range(ymin, ymax + 1, passo):
            p.setPen(QPen(QColor("#E2E8E5"), 1))
            p.drawLine(QPointF(sx, Y(v)), QPointF(sx + W, Y(v)))
            p.setPen(QColor("#52625D"))
            p.setFont(testo)
            dieci = p.fontMetrics().horizontalAdvance("10")
            p.drawText(QPointF(sx - 36, Y(v) + 5), "10")
            p.setFont(piccolo)
            p.drawText(QPointF(sx - 35 + dieci, Y(v) - 4), str(v))
        p.setFont(testo)
        tacca = 10 if gmax > 40 else 5 if gmax > 8 else 1
        for g in range(0, int(gmax) + 1, tacca):
            p.drawText(QPointF(X(g) - 8, su + H + 20), str(g))
        p.drawText(QPointF(sx + W / 2 - 20, su + H + 40), "giorni")
        for nome, colore, giorni, y in self.serie:
            p.setPen(QPen(QColor(colore), 3))
            p.drawPolyline(QPolygonF([QPointF(X(g), Y(v)) for g, v in zip(giorni, y)]))
        x, riga = sx, su + H + 58
        for nome, colore, _, _ in self.serie:            # legenda: va a capo se non ci sta
            largo = 24 + p.fontMetrics().horizontalAdvance(nome) + 28
            if x > sx and x + largo > self.width():
                x, riga = sx, riga + 24
            p.fillRect(int(x), riga, 18, 4, QColor(colore))
            p.setPen(QColor("#1C2B27"))
            p.drawText(QPointF(x + 24, riga + 6), nome)
            x += largo
        p.end()


class PaginaSicurezza(Pagina):
    titolo = "Sicurezza alimentare"

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.client = MotoreClient(self)
        self.client.evento.connect(self._evento)
        self.client.finito.connect(self._finito)
        self.risultato = None
        self.progetto_visto = None
        self.messaggi = []

        domanda = etichetta(f"Che cosa succederebbe alla <i>Listeria monocytogenes</i>, se ci fosse, durante la "
                            "conservazione del prodotto? Calcolo con i modelli di FSSP (DTU Food) partendo dalle "
                            "caratteristiche del prodotto e dalle specie trovate con MetaPhlAn.")
        domanda.setTextFormat(Qt.RichText)
        fisso = riquadro("Il profilo dice chi c'è, non quanti sono per grammo.", "", "info")
        e = etichetta(f"Per questo provo degli scenari: 1 e 100 ufc/g (cellule vive per grammo) di {LISTERIA} "
                      "all'inizio. Se hai una conta dei batteri lattici in piastra, mettila: rende la previsione "
                      "più realistica.")
        e.setTextFormat(Qt.RichText)
        fisso.layout().addWidget(e)
        self.invito = etichetta("")
        self.zona = QWidget()
        due = QHBoxLayout(self.zona)
        due.setContentsMargins(0, 8, 0, 0)
        due.setSpacing(24)
        due.addWidget(self._modulo(), 0, Qt.AlignTop)
        self.uscita = QVBoxLayout()
        self.uscita.setSpacing(12)
        destra = QWidget()
        destra.setLayout(self.uscita)
        destra.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        due.addWidget(destra, 1, Qt.AlignTop)
        for w in (domanda, fisso, self.invito, self.zona):
            self.corpo.addWidget(w)

    # ---------------- ingressi ----------------
    def _campo(self, colonna, testo, suggerimento=""):
        """Etichetta sopra, campo sotto (si legge dall'alto in basso)."""
        c = QLineEdit()
        c.setPlaceholderText(suggerimento)
        c.setAccessibleName(testo)
        colonna.addWidget(etichetta(testo))
        colonna.addWidget(c)
        colonna.addSpacing(4)
        return c

    def _modulo(self):
        f, s = pannello("Il tuo prodotto")
        f.setFixedWidth(360)
        form = QVBoxLayout()
        form.setSpacing(4)
        self.temperatura = self._campo(form, "Temperatura di conservazione (°C)", "per esempio 5")
        self.giorni = self._campo(form, "Per quanti giorni", "per esempio 21")
        scelta = QWidget()
        r = QHBoxLayout(scelta)
        r.setContentsMargins(0, 0, 0, 0)
        self.con_sale = QRadioButton("Sale (%)")
        self.con_aw = QRadioButton("aw (acqua libera)")
        self.con_sale.setChecked(True)
        self.gruppo_sale = QButtonGroup(self)
        for b in (self.con_sale, self.con_aw):
            self.gruppo_sale.addButton(b)
            r.addWidget(b)
        form.addWidget(etichetta("Che cosa conosci: il sale nella parte acquosa oppure l'aw?"))
        form.addWidget(scelta)
        self.sale = QLineEdit()
        self.sale.setAccessibleName("Sale nella parte acquosa oppure aw")
        form.addWidget(self.sale)
        form.addSpacing(4)
        self.con_sale.toggled.connect(lambda si: self.sale.setPlaceholderText(
            "per esempio 3,5" if si else "per esempio 0,90"))
        self.con_sale.toggled.emit(True)
        self.ph = self._campo(form, "pH", "per esempio 6,0")
        self.nitrito = self._campo(form, "Nitrito aggiunto (mg/kg)", "vuoto se non c'è")
        self.lab = self._campo(form, "Conta dei batteri lattici (ufc/g), facoltativa", "per esempio 1000000")
        s.addLayout(form)

        self.altro = QPushButton("▸ Altri ingredienti e opzioni", objectName="link")
        self.altro.setCheckable(True)
        s.addWidget(self.altro, 0, Qt.AlignLeft)
        self.altro_box = QWidget()
        a = QVBoxLayout(self.altro_box)
        a.setContentsMargins(0, 0, 0, 0)
        a.setSpacing(4)
        a.addWidget(etichetta("Acidi organici in ppm (mg per kg della parte acquosa); vuoto se non ci sono.", "nota"))
        self.acidi = {k: self._campo(a, t) for k, t in ACIDI}
        self.co2 = self._campo(a, "CO2 nella confezione (%)", "vuoto se non c'è")
        self.fenoli = self._campo(a, "Fenoli del fumo (ppm)", "vuoto se non affumicato")
        self.lag = QCheckBox("Ritardo iniziale (lag) prima della crescita")
        a.addWidget(self.lag)
        a.addWidget(etichetta("Modo di calcolo", "nota"))
        self.migliorata = QRadioButton("Migliorato (consigliato)")
        self.come_fssp = QRadioButton("Come FSSP, identico al programma originale")
        self.migliorata.setChecked(True)
        self.gruppo_modo = QButtonGroup(self)
        for b in (self.migliorata, self.come_fssp):
            self.gruppo_modo.addButton(b)
            a.addWidget(b)
        self.altro_box.hide()
        self.altro.toggled.connect(lambda aperto: (self.altro_box.setVisible(aperto), self.altro.setText(
            ("▾" if aperto else "▸") + " Altri ingredienti e opzioni")))
        s.addWidget(self.altro_box)

        self.calcola = QPushButton("Calcola la previsione", objectName="secondario")
        self.calcola.clicked.connect(self.avvia_calcolo)
        s.addSpacing(6)
        s.addWidget(self.calcola)
        self.problema = QVBoxLayout()
        s.addLayout(self.problema)
        return f

    def richiesta(self):
        """La richiesta per il motore (contratto §5.4). Controlla solo che i numeri siano numeri: i limiti li
        controlla il motore (INGRESSO_NON_VALIDO)."""
        def valore(campo, nome, obbligatorio=False):
            try:
                v = leggi_numero(campo.text())
            except ValueError:
                raise ValueError(f"«{nome}» non è un numero: scrivi per esempio 3,5.")
            if v is None and obbligatorio:
                raise ValueError(f"Manca «{nome}».")
            return v

        prodotto = {"temperatura": valore(self.temperatura, "Temperatura", True)}
        giorni = valore(self.giorni, "Per quanti giorni", True)
        prodotto["aw" if self.con_aw.isChecked() else "sale_fase_acquosa"] = valore(
            self.sale, "aw" if self.con_aw.isChecked() else "Sale nella parte acquosa", True)
        prodotto["ph"] = valore(self.ph, "pH", True)
        for chiave, campo, nome in (("nitrito", self.nitrito, "Nitrito"), ("co2", self.co2, "CO2"),
                                    ("fenoli", self.fenoli, "Fenoli")):
            v = valore(campo, nome)
            if v is not None:
                prodotto[chiave] = v
        acidi = {k: valore(self.acidi[k], t) for k, t in ACIDI}
        acidi = {k: v for k, v in acidi.items() if v is not None}
        if acidi:
            prodotto["acidi"] = acidi
        r = {"modalita": "fssp" if self.come_fssp.isChecked() else "migliorata", "prodotto": prodotto, "giorni": giorni}
        lab = valore(self.lab, "Conta dei batteri lattici")
        if lab is not None:
            r["conte"] = {"lab_ufc_g": lab}
        if self.lag.isChecked():
            r["lag"] = True
        return r

    def _compila(self, r):
        """Rimette nel modulo i dati di una richiesta già fatta."""
        def scrivi(campo, v):
            campo.setText("" if v is None else numero(v, 6).rstrip("0").rstrip(",").replace(".", ""))
        pr = r.get("prodotto", {})
        scrivi(self.temperatura, pr.get("temperatura"))
        scrivi(self.giorni, r.get("giorni"))
        (self.con_aw if "aw" in pr else self.con_sale).setChecked(True)
        scrivi(self.sale, pr.get("aw", pr.get("sale_fase_acquosa")))
        for chiave, campo in (("ph", self.ph), ("nitrito", self.nitrito), ("co2", self.co2), ("fenoli", self.fenoli)):
            scrivi(campo, pr.get(chiave))
        for k, campo in self.acidi.items():
            scrivi(campo, pr.get("acidi", {}).get(k))
        scrivi(self.lab, r.get("conte", {}).get("lab_ufc_g"))
        self.lag.setChecked(bool(r.get("lag")))
        (self.come_fssp if r.get("modalita") == "fssp" else self.migliorata).setChecked(True)

    # ---------------- comandi ----------------
    def mostrata(self):
        progetto = self.contesto.progetto
        dati = leggi_risultati(progetto)
        self.zona.setVisible(dati is not None)
        self.invito.setVisible(dati is None)
        if progetto is not self.progetto_visto:
            self.progetto_visto = progetto
            self.risultato = None
            self._pulisci(self.uscita)
            self._pulisci(self.problema)
            if dati is not None:
                self._ultima_salvata(progetto)
            if self.risultato is None:
                self.uscita.addWidget(etichetta("Qui compariranno le previsioni: scrivi i dati del prodotto e "
                                                "premi «Calcola la previsione».", "nota"))
        if dati is None:
            self.invito.setText("Nessun progetto aperto. Apri un progetto o creane uno nuovo."
                                if progetto is None else
                                "Per la previsione servono le specie trovate: prima fai l'analisi di questo progetto.")
        self._azioni()

    def _ultima_salvata(self, progetto):
        """Se il progetto ha già una previsione (risultati/sicurezza/), la rimostra con i suoi dati."""
        salvate = sorted((progetto.risultati / "sicurezza").glob("*.json"), key=lambda f: f.stat().st_mtime)
        try:
            r = json.loads(salvate[-1].read_text(encoding="utf-8")) if salvate else None
        except (OSError, ValueError):
            r = None
        if r and r.get("previsioni"):
            self._compila(r.get("richiesta", {}))
            self.risultato = r
            self._mostra_uscita(r)

    def avvia_calcolo(self):
        self._pulisci(self.problema)
        if self.client.in_corso():
            return
        try:
            r = self.richiesta()
        except ValueError as e:
            self.problema.addWidget(riquadro("Controlla i dati del prodotto", str(e), "errore"))
            return
        progetto = self.contesto.progetto
        file = progetto.cartella / "sicurezza_richiesta.json"
        with open(file, "w", encoding="utf-8") as f:
            json.dump(r, f, ensure_ascii=False, indent=1)
        self.messaggi = []
        self.calcola.setEnabled(False)
        self.calcola.setText("Calcolo...")
        self.client.avvia("sicurezza", "--ingresso", percorso_per_motore(file),
                          "--progetto", percorso_per_motore(progetto.config))
        self._azioni()

    def azione_principale(self):
        progetto = self.contesto.progetto
        if leggi_risultati(progetto) is None:
            super().azione_principale()
        elif self.risultato is not None and not self.client.in_corso():
            self.respira.emit(True)
            self.client.avvia("referto", "--progetto", percorso_per_motore(progetto.config))
            self._azioni()

    def _evento(self, e):
        if e["tipo"] == "avviso" and e.get("codice") != "FUORI_CAMPO":    # FUORI_CAMPO: dal risultato, prima dei numeri
            self.messaggi.append(("Da sapere", e["messaggio"], "avviso"))
        elif e["tipo"] == "errore":
            self.messaggi.append((e["messaggio"], e.get("cosa_fare", ""), "errore"))

    def _finito(self, codice, fine):
        comando = self.client.comando
        self.respira.emit(False)
        self.calcola.setEnabled(True)
        self.calcola.setText("Calcola la previsione")
        self._pulisci(self.problema)
        for titolo, testo, livello in self.messaggi:      # vicino a ciò che riguardano (R9)
            if comando == "sicurezza":
                self.problema.addWidget(riquadro(titolo, testo, livello))
            else:
                self.uscita.insertWidget(0, riquadro(titolo, testo, livello))
        self.messaggi = []
        if comando == "sicurezza" and fine.get("esito") == "ok":
            self.risultato = fine["risultato"]
            self._mostra_uscita(self.risultato)
        elif comando == "referto" and fine.get("esito") == "ok":
            self.vai.emit("risultati")
        self._azioni()

    def _azioni(self):
        progetto = self.contesto.progetto
        self.aiuto, self.aiuto_livello = "", ""
        self.principale_attivo = True
        if leggi_risultati(progetto) is None:
            self.testo_principale, self.destinazione = (("Apri i miei progetti", "home") if progetto is None
                                                        else ("Vai alle scelte dell'analisi", "scelte"))
        else:
            self.testo_principale, self.destinazione = "Aggiungi al referto", None
            occupato = self.client.in_corso()
            self.principale_attivo = self.risultato is not None and not occupato
            if occupato and self.client.comando == "referto":
                self.aiuto = "Preparo il referto con la previsione..."
            elif self.risultato is None:
                self.aiuto = "Prima scrivi i dati del prodotto e premi Calcola la previsione."
            else:
                self.aiuto = "Previsione con FSSP (DTU Food): va nello stesso referto dei risultati."
        self.azioni_cambiate.emit()

    # ---------------- uscita del motore ----------------
    @staticmethod
    def _pulisci(layout):
        for i in reversed(range(layout.count())):
            w = layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _mostra_uscita(self, r):
        self._pulisci(self.uscita)
        avvisi = [a for a in r.get("avvisi", []) if a.get("codice") == "FUORI_CAMPO"]
        if avvisi:                                     # R9: prima dei numeri, in ambra
            testo = "<br>".join(f"• {html.escape(MODELLI.get(a.get('modello'), 'Modello'))}: {html.escape(a['messaggio'])}"
                                for a in avvisi)
            box = riquadro("Fuori dal campo dei modelli: è un'estrapolazione, usala con cautela.", "", "avviso")
            e = etichetta(testo)
            e.setTextFormat(Qt.RichText)
            box.layout().addWidget(e)
            self.uscita.addWidget(box)
        for p in r.get("previsioni", []):
            self.uscita.addWidget(self._scheda(p, bool(avvisi)))
        f, s = pannello("Come cresce nel tempo")
        self.grafico = Grafico()
        self.grafico.imposta(r.get("previsioni", []))
        s.addWidget(self.grafico)
        s.addWidget(etichetta("ufc/g su scala logaritmica: ogni riga è dieci volte la precedente.", "nota"))
        self.uscita.addWidget(f)
        self.uscita.addWidget(self._ponte(r))
        if r.get("note") or r.get("citazione"):
            f, s = pannello("Note del calcolo")
            for n in r.get("note", []):
                s.addWidget(etichetta(f"• {n}", "nota"))
            if r.get("citazione"):
                s.addWidget(etichetta(f"Modelli: {r['citazione']}", "nota"))
            self.uscita.addWidget(f)

    def _scheda(self, p, fuori_campo):
        """Una scheda per scenario: ambra se cresce, verde se non cresce, grigio se non cresce ma fuori campo."""
        curva = p["curva"]
        giorni, finale = curva["giorni"][-1], curva["log_listeria"][-1]
        if p["listeria_puo_crescere"]:
            classe = "cresce"
            frase = (f"Dopo {numero(giorni, 0)} giorni arriverebbe a <b>10<sup>{numero(finale)}</sup> ufc/g</b> "
                     f"(circa {due_cifre(10 ** finale)} ufc/g).")
            if p.get("cento_volte_listeria_giorni"):
                frase += f" Si moltiplica per 100 in circa {due_cifre(p['cento_volte_listeria_giorni'])} giorni."
            if p.get("modello") == "listeria_lab":
                frase += " I batteri lattici la frenano."
        elif fuori_campo:
            classe = "incerto"
            frase = (f"Secondo il modello la {LISTERIA} non cresce, ma qui il modello lavora fuori dal suo campo: "
                     "<b>non è una garanzia</b>.")
        else:
            classe = "ferma"
            frase = f"In queste condizioni la {LISTERIA} <b>non cresce</b>."
        f = QFrame(objectName="scenario")
        f.setProperty("esito", classe)
        f.setStyleSheet(f"QFrame#scenario {{ background: #FFFFFF; border: 1px solid #CBD5D1; border-radius: 12px;"
                        f" border-left: {BORDI[classe]}; }} QFrame#scenario QLabel {{ background: transparent; }}")
        s = QVBoxLayout(f)
        s.setContentsMargins(20, 14, 20, 14)
        t = etichetta(f"Se all'inizio ci fosse {due_cifre(p['n0_listeria_ufc_g'])} ufc/g di {LISTERIA}")
        t.setTextFormat(Qt.RichText)
        t.setStyleSheet("font-weight: bold; font-size: 20px;")
        e = etichetta(frase)
        e.setTextFormat(Qt.RichText)
        s.addWidget(t)
        s.addWidget(e)
        return f

    def _ponte(self, r):
        f, s = pannello("Che cosa ho usato del profilo")
        pn = r.get("ponte", {})
        righe = []
        if r.get("profilo_usato"):
            righe.append(f"Profilo: {html.escape(r['profilo_usato'])}.")
        righe.append("<i>Listeria monocytogenes</i>: " + (
            "<b>trovata</b> nel profilo." if pn.get("listeria_trovata") else
            "non trovata. Non vuol dire che manchi: sotto la soglia di rilevamento può esserci."))
        lab = ", ".join(f"<i>{html.escape(maiuscola(x))}</i>" for x in pn.get("lab_trovati", []))
        righe.append(f"Batteri lattici del modello trovati: {lab or 'nessuno'}.")
        nc = pn.get("specie_non_coperte", [])
        if nc:
            righe.append(f"{len(nc)} specie del profilo non hanno un modello in FSSP: la loro crescita non si prevede.")
        for testo in righe:
            e = etichetta(f"• {testo}")
            e.setTextFormat(Qt.RichText)
            s.addWidget(e)
        return f
