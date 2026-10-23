"""Pagina "Risultati" (S6, docs/interfaccia_S4.md §3.4): legge risultati/risultati.json del progetto (nessun comando).

In cima la sintesi del motore, poi il referto (HTML dentro l'app, PDF ed Excel con i programmi di Windows), poi le
schede MetaPhlAn, Kraken e "Come è stata fatta l'analisi": MetaPhlAn e Kraken MAI nella stessa tabella (R12).
In fondo sempre le citazioni (R14). Testi e numeri arrivano dal motore: qui si formattano soltanto (R11).
"""
import html
import json
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QPushButton, QTabBar, QTextBrowser,
                               QVBoxLayout, QWidget)

from app import lingua
from app.lingua import N_, _
from app.pagine.base import PROTOTIPO, Pagina, etichetta, numero, riquadro

OSPITI = {"sus_scrofa": N_("maiale (Sscrofa11.1)"), "bos_taurus": N_("bovino (ARS-UCD1.2)"),
          "ovis_aries": N_("pecora (ARS-UI_Ramb_v2.0)"), "grch38": N_("uomo (GRCh38)")}
# valori fissi del motore (contratto §5.3: chiavi, non testi): si traducono solo quando si mostrano
GRUPPI = [N_("batteri"), N_("archei"), N_("funghi"), N_("virus"), N_("altri eucarioti"), N_("altro"),
          N_("da controllare"), N_("da rifare"), N_("buono")]
TRIAGE = {"da controllare": "avviso", "da rifare": "errore"}
SCHEDE = ("QTabBar::tab { background: transparent; border: 0; border-bottom: 4px solid transparent; color: #52625D;"
          " font-weight: bold; padding: 10px 16px; margin-right: 4px; }"
          "QTabBar::tab:selected { color: #1C2B27; border-bottom-color: #1E7A4C; }"
          "QTabBar::tab:hover, QTabBar::tab:focus { background: #E6EEF4; }")


def leggi_risultati(progetto):
    """L'indice risultati/risultati.json del progetto, o None se non c'è (analisi non ancora finita)."""
    if progetto is None:
        return None
    try:
        return json.loads((progetto.risultati / "risultati.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def dentro(progetto, percorso):
    """Il percorso risolto, solo se è un file o una cartella dentro la cartella del progetto; altrimenti None."""
    p = Path(percorso).resolve()
    if p.is_relative_to(progetto.cartella.resolve()) and p.exists():
        return p
    return None


def file_referto(progetto, d):
    """{html, pdf, xlsx, qc: percorso o None} dei file del referto nominati in risultati.json."""
    r = dict(d.get("referto") or {})
    r["qc"] = (d.get("qc") or {}).get("multiqc")   # v0.4: report MultiQC in risultati/qc/, nel browser di Windows
    # P19: solo l'estensione attesa, perché PDF, Excel e QC si aprono col programma di Windows (un .bat partirebbe).
    # Si guarda il percorso risolto, quello che si apre davvero: un collegamento simbolico referto.pdf -> x.bat no.
    attesa = {"html": ".html", "pdf": ".pdf", "xlsx": ".xlsx", "qc": ".html"}
    trovati = {k: (dentro(progetto, progetto.risultati / r[k]) if r.get(k) else None) for k in attesa}
    return {k: (p if p is not None and p.suffix.lower() == attesa[k] else None) for k, p in trovati.items()}


def corsivo(testo, nomi):
    """Testo del motore in HTML sicuro, con i nomi delle specie in corsivo."""
    testo = html.escape(testo)
    for n in sorted(set(nomi), key=len, reverse=True):
        testo = testo.replace(html.escape(n), f"<i>{html.escape(n)}</i>")
    return testo


def articolo(numero_scritto):
    """Articolo italiano davanti a una percentuale, come si legge: "Lo 0,0", "L'80,5", "Il 53,7" (stessa regola di
    motore/referto.articolo: l'app non importa il motore)."""
    if lingua.attuale() != "it":
        return ""
    intero = numero_scritto.split(",")[0].split(".")[0]
    if intero == "0":
        return "Lo "
    return "L'" if intero in ("1", "11") or intero.startswith("8") else "Il "


def separatore():
    s = QFrame(objectName="separatore")
    s.setFixedHeight(1)
    return s


class PaginaRisultati(Pagina):
    titolo = N_("Risultati")

    def __init__(self, contesto, parent=None):
        super().__init__(contesto, parent)
        self.contenuto = None
        self.dati = None
        self._chiave = None

    def mostrata(self):
        # P25: la pagina dipende solo dal progetto, da risultati.json e dai file del referto che ci sono; se nulla è
        # cambiato non si rifà (con 30 campioni costava circa 1 s) e torna solo alla prima scheda, come una nuova
        progetto = self.contesto.progetto
        dati = leggi_risultati(progetto)
        chiave = None if dati is None else (str(progetto.cartella), dati, file_referto(progetto, dati))
        if chiave is not None and chiave == self._chiave and self.contenuto is not None:
            self.linguette.setCurrentIndex(0)
            self.azioni_cambiate.emit()
            return
        self._chiave = chiave
        if self.contenuto is not None:
            self.contenuto.setParent(None)
            self.contenuto.deleteLater()
        self.dati = dati
        self.contenuto = QWidget()
        self.lista = QVBoxLayout(self.contenuto)
        self.lista.setContentsMargins(0, 0, 0, 0)
        self.lista.setSpacing(12)
        self.corpo.addWidget(self.contenuto)
        self.aiuto, self.aiuto_livello = "", ""
        if self.dati is None:
            self._vuota(progetto)
        else:
            self._pagina(progetto, self.dati)
            self.testo_principale, self.destinazione = _("Prevedi la sicurezza alimentare"), "sicurezza"
            self.aiuto = _("Passo 4 di 4")
        self.azioni_cambiate.emit()

    def _vuota(self, progetto):
        if progetto is None:
            self.lista.addWidget(etichetta(_("Nessun progetto aperto. Apri un progetto o creane uno nuovo.")))
            self.testo_principale, self.destinazione = _("Apri i miei progetti"), "home"
        else:
            self.lista.addWidget(etichetta(_("Questo progetto non ha ancora risultati. Avvia l'analisi dalle "
                                             "scelte dell'analisi (passo 2).")))
            self.testo_principale, self.destinazione = _("Vai alle scelte dell'analisi"), "scelte"

    # ---------------- la pagina con i risultati ----------------
    def _pagina(self, progetto, d):
        campioni = d.get("campioni", [])
        for c in campioni:
            s = c.get("sintesi", {})
            m, k = s.get("metaphlan", {}), s.get("kraken", {})
            nomi = [x["nome"] for x in m.get("dominanti", []) + k.get("dominanti", []) + k.get("non_microbi", [])]
            frasi = [_("Campione <b>{nome}</b>", nome=html.escape(c['nome']))] + [
                corsivo(x["frase"], nomi) for x in (m, k) if x.get("frase")]
            for frase in frasi:                      # una frase per riga: si legge meglio (R2)
                e = etichetta(frase)
                e.setTextFormat(Qt.RichText)
                self.lista.addWidget(e)
            if k.get("frase"):
                self.lista.addWidget(etichetta(_("Kraken è un prototipo: non usare i suoi numeri per decisioni."),
                                               "nota"))

        for t in d.get("triage", []):                       # ben visibile, prima del resto (R9)
            if t.get("esito") in TRIAGE:
                motivi = "; ".join(t.get("motivi", []))
                testo = (_("Motivo: {motivi}. ", motivi=motivi) if motivi else "") + _(
                    "Guardalo prima di usare questi risultati.")
                self.lista.addWidget(riquadro(_("Campione {nome}: {esito}", nome=t['campione'], esito=_(t['esito'])),
                                              testo, TRIAGE[t["esito"]]))
        for c in d.get("consigli", []):
            if c.get("codice") not in ("CAMPIONE_DA_CONTROLLARE", "CAMPIONE_DA_RIFARE"):
                self.lista.addWidget(riquadro(_("Da sapere"), c.get("messaggio", ""), "avviso"))

        self._referto(progetto, d)

        self.linguette = QTabBar()                 # una scheda per metodo: MetaPhlAn e Kraken mai insieme (R12)
        self.linguette.setStyleSheet(SCHEDE)
        self.linguette.setDrawBase(False)
        self.linguette.setExpanding(False)
        self.schede = [self._scheda_metaphlan(campioni), self._scheda_kraken(campioni), self._scheda_come(d)]
        for testo in (_("Specie trovate con MetaPhlAn"), _("Specie trovate con Kraken"),
                      _("Come è stata fatta l'analisi")):
            self.linguette.addTab(testo)
        self.linguette.currentChanged.connect(
            lambda i: [w.setVisible(j == i) for j, w in enumerate(self.schede)])
        self.lista.addWidget(self.linguette)
        self.lista.addWidget(separatore())
        for i, w in enumerate(self.schede):
            w.setVisible(i == 0)
            self.lista.addWidget(w)

        self.lista.addSpacing(8)
        self.lista.addWidget(separatore())
        self.lista.addWidget(etichetta(_("Strumenti e database usati"), "sottotitolo"))
        self.lista.addWidget(etichetta(_("Se usi questi risultati in un documento, cita queste fonti."), "nota"))
        for i, c in enumerate(d.get("citazioni", []), 1):
            self.lista.addWidget(etichetta(f"{i}. {c}", "nota"))

    def _referto(self, progetto, d):
        self.file = file_referto(progetto, d)
        riga = QHBoxLayout()
        riga.setSpacing(12)
        pulsanti = [(_("Apri il referto"), "html", self.apri_referto),
                    (_("Apri il referto in PDF"), "pdf", lambda: self.apri(self.file["pdf"])),
                    (_("Apri le tabelle in Excel"), "xlsx", lambda: self.apri(self.file["xlsx"])),
                    (_("Apri il controllo qualità"), "qc", lambda: self.apri(self.file["qc"]))]
        mancano = []
        for testo, chiave, funzione in pulsanti:
            b = QPushButton(testo, objectName="secondario")
            b.clicked.connect(funzione)
            b.setEnabled(self.file[chiave] is not None)
            if self.file[chiave] is None:
                mancano.append({"html": _("la pagina del referto"), "pdf": _("il PDF"),
                                "xlsx": _("le tabelle Excel"), "qc": _("il controllo qualità")}[chiave])
            riga.addWidget(b)
        cartella = QPushButton(_("Apri la cartella dei risultati"), objectName="link")
        cartella.clicked.connect(lambda: self.apri(dentro(progetto, progetto.risultati)))
        riga.addWidget(cartella)
        riga.addStretch(1)
        self.lista.addLayout(riga)
        if mancano:
            self.lista.addWidget(etichetta(_("Non sono stati preparati: {file}.", file=", ".join(mancano)), "nota"))

    def _barre(self, righe, colore):
        """Barre orizzontali: [(nome, percentuale)]; la lunghezza è solo disegno (la più grande = barra piena)."""
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 4, 0, 4)
        g.setHorizontalSpacing(16)
        g.setVerticalSpacing(6)
        massimo = max((v for _, v in righe), default=0) or 1
        for i, (nome, v) in enumerate(righe):
            n = etichetta(f"<i>{html.escape(nome)}</i>")
            n.setTextFormat(Qt.RichText)
            n.setWordWrap(False)
            b = QFrame()
            b.setFixedSize(max(3, round(380 * v / massimo)), 18)
            b.setStyleSheet(f"background: {colore}; border-radius: 3px;")
            x = etichetta(f"{numero(v, 2)} %")
            x.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            g.addWidget(n, i, 0)
            g.addWidget(b, i, 1, Qt.AlignLeft | Qt.AlignVCenter)
            g.addWidget(x, i, 2)
        g.setColumnMinimumWidth(1, 390)
        g.setColumnStretch(3, 1)
        return w

    def _scheda(self):
        w = QWidget()
        s = QVBoxLayout(w)
        s.setContentsMargins(0, 16, 0, 8)
        s.setSpacing(10)
        return w, s

    def _titolo_campione(self, s, c, campioni):
        if len(campioni) > 1:
            s.addWidget(etichetta(_("Campione {nome}", nome=c['nome']), "sottotitolo"))

    def _scheda_metaphlan(self, campioni):
        w, s = self._scheda()
        for c in campioni:
            m = c.get("sintesi", {}).get("metaphlan")
            self._titolo_campione(s, c, campioni)
            if not m:
                s.addWidget(etichetta(_("Profilo MetaPhlAn non disponibile per questo campione."), "nota"))
                continue
            p = numero(m['non_assegnata_pct'])
            e = etichetta(_("Percentuale sul totale delle read del campione. {art}<b>{pct} %</b> non è assegnato a "
                            "nessuna specie del database: è normale (taxa non ancora nel database e DNA "
                            "dell'ospite rimasto).", art=articolo(p), pct=p))
            e.setTextFormat(Qt.RichText)
            s.addWidget(e)
            dom = m.get("dominanti", [])
            s.addWidget(self._barre([(x["nome"], x["pct"]) for x in dom], "#1E7A4C"))
            s.addWidget(etichetta(_("Qui tutte le {n} specie trovate.", n=len(dom)) if len(dom) >= m["specie"]
                                  else _("Qui le {n} più abbondanti delle {tot} specie trovate. Tutte le altre "
                                         "sono nel referto e nelle tabelle Excel.", n=len(dom), tot=m['specie']),
                                  "nota"))
        return w

    def _scheda_kraken(self, campioni):
        w, s = self._scheda()
        s.addWidget(riquadro(_(PROTOTIPO), _("Le impostazioni di Kraken sono tarate su comunità simulate e su un "
                                             "campione di controllo (Zymo), non ancora su salumi veri. Guarda questi "
                                             "numeri come un confronto, non usarli per decidere."), "avviso"))
        s.addWidget(riquadro(_("Metodo diverso da MetaPhlAn"),
                             _("Kraken confronta ogni read con genomi interi: i suoi numeri non si sommano e non si "
                               "confrontano uno a uno con quelli di MetaPhlAn."), "info"))
        for c in campioni:
            k = c.get("sintesi", {}).get("kraken")
            self._titolo_campione(s, c, campioni)
            if not k:
                s.addWidget(etichetta(_("Profilo Kraken non disponibile per questo campione."), "nota"))
                continue
            s.addWidget(etichetta(_("Percentuale fra i soli taxa del prodotto (batteri, archei, funghi), dopo la "
                                    "ridistribuzione di Bracken (il programma che stima le abbondanze).")))
            dom = k.get("dominanti", [])
            s.addWidget(self._barre([(x["nome"], x["pct_microbi"]) for x in dom], "#2F5D7C"))
            s.addWidget(etichetta(_("Qui tutti i {n} taxa sopra la soglia.", n=len(dom)) if len(dom) >= k["microbi"]
                                  else _("Qui i {n} più abbondanti dei {tot} taxa sopra la soglia. Tutti gli altri "
                                         "sono nel referto e nelle tabelle Excel.", n=len(dom), tot=k['microbi']),
                                  "nota"))
            nm = k.get("non_microbi", [])
            if nm:
                elenco = ", ".join(f"<i>{html.escape(x['nome'])}</i> ({html.escape(_(x['gruppo']))}, "
                                   f"{numero(x['pct'], 3)} %)" for x in nm)
                r = riquadro(_("Segnalati a parte, fuori dal profilo"), "", "info")
                e = etichetta(elenco + _(". Non sono taxa del prodotto (per esempio avanzi di DNA dell'ospite) "
                                         "o sono virus."))
                e.setTextFormat(Qt.RichText)
                r.layout().addWidget(e)
                s.addWidget(r)
        return w

    def _scheda_come(self, d):
        w, s = self._scheda()
        p, v = d.get("parametri", {}), d.get("versioni", {})
        ospiti = [_(OSPITI.get(o, o)) for o in str(p.get("hosts", "")).replace(",", " ").split()]
        if str(p.get("filter_human", "")).lower() in ("yes", "true", "1"):
            ospiti.append(_(OSPITI["grch38"]))
        modo = p.get("metaphlan_mode") or p.get("metaphlan_modo")
        profilo = p.get("kraken_profile")
        righe = [(_("DNA dell'ospite tolto"), ", ".join(dict.fromkeys(ospiti))),
                 *[(_("Coppie di read rimaste ({nome})", nome=c['nome']), numero(c["coppie_dopo_ospite"], 0))
                   for c in d.get("campioni", []) if c.get("coppie_dopo_ospite") is not None],
                 ("MetaPhlAn", _("{versione}, database {database}", versione=v.get('metaphlan', ''),
                                 database=v.get('database_metaphlan', ''))
                  + {"fette": _(", in 6 parti (stesso profilo dell'analisi standard)"),
                     "standard": _(", standard")}.get(modo, "")),
                 (_("Kraken e Bracken"), _("Kraken {kraken}, Bracken {bracken}, database {database}",
                                           kraken=v.get('kraken2', ''), bracken=v.get('bracken', ''),
                                           database=v.get('database_kraken', ''))
                  + {"rapido": _(" (screening rapido)"), "completo": _(" (completo)")}.get(profilo, "")),
                 (_("Soglia di confidenza di Kraken"), lingua.virgola(p.get("kraken_confidence", ""))),
                 (_("Read minime per specie (Bracken)"), str(p.get("bracken_min_reads", ""))),
                 (_("Soglia di abbondanza di Kraken"), lingua.virgola(p.get("abundance_threshold_pct", "")) + " %")]
        tab = QWidget()
        g = QGridLayout(tab)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(24)
        for i, (nome, valore) in enumerate(r for r in righe if r[1].strip(" ,%")):
            e = etichetta(nome, "nota")
            e.setWordWrap(False)
            g.addWidget(e, i, 0, Qt.AlignTop)
            g.addWidget(etichetta(valore), i, 1)
        g.setColumnStretch(1, 1)
        s.addWidget(tab)
        s.addWidget(etichetta(_("Corsa {corsa}, motore {motore}.", corsa=d.get('corsa', ''),
                                motore=d.get('motore', '')), "nota"))
        return w

    # ---------------- referto e file ----------------
    def apri_referto(self):
        """Il referto HTML dentro l'app (D059): stesso motore di testo del PDF (QTextDocument)."""
        f = self.file.get("html")
        if f is None:
            return
        finestra = QDialog(self)
        finestra.setWindowTitle(_("Referto"))
        finestra.resize(1100, 760)
        s = QVBoxLayout(finestra)
        testo = QTextBrowser()
        testo.setOpenLinks(False)               # nessun collegamento esterno si apre da qui
        testo.anchorClicked.connect(lambda u: u.hasFragment() and not u.scheme() and testo.scrollToAnchor(u.fragment()))
        testo.setSearchPaths([str(f.parent)])
        testo.setHtml(f.read_text(encoding="utf-8"))
        s.addWidget(testo)
        chiudi = QPushButton(_("Chiudi"), objectName="secondario")
        chiudi.clicked.connect(finestra.accept)
        s.addWidget(chiudi, 0, Qt.AlignRight)
        self.finestra_referto = finestra
        finestra.open()

    def apri(self, percorso):
        """Apre un file o una cartella del progetto con il programma di Windows (mai fuori dal progetto)."""
        p = dentro(self.contesto.progetto, percorso) if percorso else None
        if p is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
