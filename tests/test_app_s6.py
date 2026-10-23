# -*- coding: utf-8 -*-
"""Pagine di S6 (Analisi in corso, Risultati, Sicurezza alimentare) contro il finto motore.
Gira con l'ambiente dell'app su Windows:  app\\.venv\\Scripts\\python -m pytest tests/test_app_s6.py"""
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QTabBar, QTextBrowser  # noqa: E402

from app import finestra, main, motore, progetto  # noqa: E402
from app.pagine.base import PROTOTIPO  # noqa: E402

ATTESA = 60000


@pytest.fixture(autouse=True)
def finto(monkeypatch, tmp_path):
    monkeypatch.setenv("PMN_MOTORE", "finto")
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    stato = tmp_path / "tmp"                 # lucchetto di esegui del finto motore solo per questo test (nota S5b)
    stato.mkdir()
    monkeypatch.setenv("TEMP", str(stato))
    monkeypatch.setenv("TMP", str(stato))


@pytest.fixture
def f(qtbot, qapp):
    main.prepara(qapp)
    w = finestra.Finestra(movimento=False)
    qtbot.addWidget(w)
    w.show()
    w.fuori.setCurrentIndex(1)              # dopo l'avvio con l'avatar (lo prova test_app_scheletro)
    return w


def apri(f, tmp_path, avvia=True):
    """Come la pagina Scelte (S5b): config.yaml scritto, progetto nel contesto, avvia_analisi = True."""
    p = progetto.nuovo("prova", tmp_path)
    p.scrivi({"project_name": "prova", "motore": {"metaphlan_modo": "fette", "kraken_db": "completo"}})
    f.contesto.progetto = p
    f.contesto.avvia_analisi = avvia
    return p


def un_principale(f):
    """R1: un solo pulsante principale visibile, quello della finestra."""
    principali = [b for b in f.findChildren(QPushButton, "principale") if b.isVisible()]
    assert len(principali) == 1
    return principali[0]


def scritte(w):
    return "\n".join(e.text() for e in w.findChildren(QLabel))


def riquadri(w, livello):
    QApplication.processEvents()            # Qt mostra i widget aggiunti al giro dopo del ciclo degli eventi
    return [r for r in w.findChildren(QFrame, "riquadro") if r.property("livello") == livello and r.isVisible()]


def esegui_fino_alla_fine(f, qtbot, tmp_path):
    p = apri(f, tmp_path)
    f.vai("esecuzione")
    es = f.pagine["esecuzione"]
    qtbot.waitUntil(lambda: es.stato == "ok", timeout=ATTESA)
    return p, es


# ---------------- Analisi in corso ----------------
def test_esegui_fino_a_vedi_i_risultati(f, qtbot, tmp_path):
    respiri = []
    es = f.pagine["esecuzione"]
    es.respira.connect(respiri.append)
    p, es = esegui_fino_alla_fine(f, qtbot, tmp_path)
    assert f.contesto.avvia_analisi is False                    # rimesso subito a False
    assert respiri == [True, False]                             # l'avatar respira e si ferma
    assert es.titolo_pagina.text() == "Analisi finita"
    assert all(e.text().startswith("✓") for e, _ in es.passi.values())
    assert es.barra.value() == 100 and es.pct.text() == "100 %"
    assert "Analisi finita" in es.messaggio.text()              # messaggio del motore così com'è
    assert es.registro.text().endswith("_esegui.log") and not es.registro.isVisible()
    es.dettagli.click()
    assert es.registro.isVisible()
    b = un_principale(f)
    assert b.text() == "Vedi i risultati"
    b.click()
    assert f.attuale == "risultati"
    assert (p.risultati / "risultati.json").is_file()


def test_entrare_senza_avvia_analisi_non_lancia_nulla(f, qtbot, tmp_path):
    apri(f, tmp_path, avvia=False)
    f.vai("esecuzione")
    es = f.pagine["esecuzione"]
    assert not es.client.in_corso() and es.stato == "vuota"
    assert es.invito.isVisible() and "Nessuna analisi in corso" in es.invito.text()
    assert un_principale(f).text() == "Vai alle scelte dell'analisi"
    un_principale(f).click()
    assert f.attuale == "scelte"


def test_ferma_e_riprendi(f, qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 60")     # download: 4 s, c'è tempo per fermare
    es = f.pagine["esecuzione"]
    chieste = []
    monkeypatch.setattr(es, "conferma", lambda: chieste.append(1) or True)
    apri(f, tmp_path)
    f.vai("esecuzione")
    qtbot.waitUntil(lambda: es.messaggio.text().startswith("Campione"), timeout=ATTESA)
    assert es.ancora.isVisible() and "usare il computer per altro" in es.ancora.text()
    b = un_principale(f)
    assert b.text() == "Ferma l'analisi" and b.property("pericolo") is True     # bianco col bordo rosso
    assert f.contesto.progetto_in_analisi is f.contesto.progetto                 # intanto niente altri progetti
    b.click()
    assert chieste == [1] and es.stato == "ferma_chiesto" and not b.isEnabled()
    qtbot.waitUntil(lambda: es.stato == "annullata", timeout=ATTESA)
    assert f.contesto.progetto_in_analisi is None and b.property("pericolo") is False
    assert es.titolo_pagina.text() == "Analisi fermata"
    assert b.isEnabled() and b.text() == "Riprendi l'analisi"
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    b.click()                                                    # esegui è riprendibile: si rilancia
    qtbot.waitUntil(lambda: es.stato == "ok", timeout=ATTESA)
    assert b.text() == "Vedi i risultati"


def test_app_chiusa_a_meta_si_riprende(f, qtbot, tmp_path, monkeypatch):
    """B2 (P11a): app chiusa o PC spento A METÀ, senza Ferma. Alla riapertura il progetto dice che l'analisi si è
    interrotta e propone Riprendi l'analisi, che riparte (esegui è riprendibile: i passi finiti non si rifanno)."""
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 60")
    es = f.pagine["esecuzione"]
    p = apri(f, tmp_path)
    f.vai("esecuzione")
    qtbot.waitUntil(lambda: es.messaggio.text().startswith("Campione"), timeout=ATTESA)
    es.client._p.kill()                                          # come il PC spento: nessun evento fine
    es.client._p.waitForFinished(5000)
    f.close()
    monkeypatch.setattr(progetto, "cartella_progetti", lambda: tmp_path)
    w = finestra.Finestra(movimento=False)                       # l'app riaperta
    qtbot.addWidget(w)
    w.show()
    w.fuori.setCurrentIndex(1)
    w.vai("home")
    assert "Analisi interrotta" in scritte(w.pagine["home"])
    w.pagine["home"].apri(progetto.Progetto(p.cartella))
    assert w.attuale == "esecuzione"
    es2 = w.pagine["esecuzione"]
    assert "si è interrotta" in es2.invito.text() and "passi già finiti sono salvati" in es2.invito.text()
    b = un_principale(w)
    assert b.text() == "Riprendi l'analisi"
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    b.click()
    qtbot.waitUntil(lambda: es2.stato == "ok", timeout=ATTESA)
    assert not p.interrotta                                      # finita: niente da riprendere
    w.vai("home")
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)   # via le righe vecchie dell'elenco
    assert "Analisi interrotta" not in scritte(w.pagine["home"]) and "Risultati pronti" in scritte(w.pagine["home"])


def test_ferma_dice_che_si_puo_spegnere(f, qtbot, tmp_path, monkeypatch):
    """B2 (P11b): chi ferma per spegnere il computer deve leggere che può farlo e come riprendere."""
    from PySide6.QtWidgets import QMessageBox
    testi = []
    monkeypatch.setattr(QMessageBox, "exec", lambda m: testi.append(m.informativeText()) or 0)
    es = f.pagine["esecuzione"]
    es.conferma()
    assert "spegnere il computer" in testi[0] and "Riprendi l'analisi" in testi[0]
    f.vai("esecuzione")
    es.stato = "annullata"
    es._mostra()
    assert "spegnere il computer" in es.aiuto


def test_il_tempo_scende_anche_dentro_un_passo_lungo(f, monkeypatch):
    """17/10: durante Kraken (24 minuti) l'app restava ferma su "95 %, 88 minuti". Ora fra due eventi un orologio
    locale fa scendere il tempo e avanzare la barra, senza mai tornare indietro."""
    import types
    from app.pagine import esecuzione
    ora = [1000.0]
    monkeypatch.setattr(esecuzione, "time", types.SimpleNamespace(monotonic=lambda: ora[0]))
    es = f.pagine["esecuzione"]
    es.stato = "in_corso"
    avanza = {"tipo": "avanzamento", "messaggio": "Campione 1 di 1: classifico le read con Kraken e Bracken",
              "passo": "kraken", "campione": "S1", "fatto": 1, "totale": 1, "percentuale": 40, "eta_s": 1500}
    es._evento(avanza)
    assert es.orologio.isActive() and es.eta.text() == "25 minuti" and es.barra.value() == 40
    ora[0] += 750                                    # metà del tempo che mancava
    es._scorre()
    assert es.eta.text() == "12 minuti" and es.barra.value() == 70 and es.pct.text() == "70 %"
    ora[0] += 1000                                   # più lungo del previsto: niente numeri inventati
    es._scorre()
    assert es.eta.text() == "qualche minuto" and es.barra.value() == 99
    es._evento({**avanza, "passo": "riepilogo", "percentuale": 98, "eta_s": 20})
    assert es.barra.value() == 99 and es.eta.text() == "20 secondi"   # la barra non torna indietro
    es._evento({**avanza, "eta_s": None})
    assert not es.orologio.isActive()                # senza stima l'orologio si ferma


def test_un_passo_che_sfora_non_fa_avanzare_gli_altri(f, monkeypatch):
    """A1, 17/10: SF3RAt3, download previsto 3 min, durato 37 (rete lenta). Dopo 30 min l'app diceva "60 %, 20 minuti"
    ancora dentro il download. Con passo_s l'orologio scende solo dentro il passo; se il passo sfora, lo dice."""
    import types
    from app.pagine import esecuzione
    ora = [1000.0]
    monkeypatch.setattr(esecuzione, "time", types.SimpleNamespace(monotonic=lambda: ora[0]))
    es = f.pagine["esecuzione"]
    es.stato = "in_corso"
    es._evento({"tipo": "avanzamento", "messaggio": "scarico le read da NCBI", "passo": "download", "campione": None,
                "fatto": 0, "totale": 1, "percentuale": 0, "eta_s": 3025, "passo_s": 180})
    ora[0] += 90                                     # metà del download previsto
    es._scorre()
    assert es.eta.text() == "49 minuti" and es.barra.value() == 3
    ora[0] += 1800                                   # il download sfora: si ferma a quello che resta dopo il passo
    es._scorre()
    assert es.eta.text() == "47 minuti" and es.barra.value() == 6
    assert "più del previsto" in es.eta_nota.text()
    es._evento({"tipo": "avanzamento", "messaggio": "tolgo le parti di bassa qualità", "passo": "pulizia",
                "campione": "S1", "fatto": 1, "totale": 1, "percentuale": 6, "eta_s": 2846, "passo_s": 25})
    assert es.eta_nota.text() == "tempo che manca, stimato"


@pytest.mark.parametrize("scenario, passo, dove", [("DB_MANCANTE", "kraken", "motore"),
                                                   ("READ_NON_TROVATE", "download", "campioni"),
                                                   ("GIA_IN_CORSO", None, "home")])
def test_errore_porta_dove_si_risolve(f, qtbot, tmp_path, monkeypatch, scenario, passo, dove):
    monkeypatch.setenv("PMN_FINTO_OPZIONI", f"--velocita 0 --scenario {scenario}")
    apri(f, tmp_path)
    f.vai("esecuzione")
    es = f.pagine["esecuzione"]
    qtbot.waitUntil(lambda: es.stato == "errore", timeout=ATTESA)
    assert es.titolo_pagina.text() == "L'analisi si è fermata"
    rossi = riquadri(es, "errore")
    assert len(rossi) == 1 and es.errore["messaggio"] in scritte(rossi[0]) and es.errore["cosa_fare"] in scritte(rossi[0])
    segnati = [c for c, (e, _) in es.passi.items() if e.text().startswith("✗")]
    assert segnati == ([passo] if passo else [])
    un_principale(f).click()
    assert f.attuale == dove


def test_motore_non_avviato_porta_al_motore(f, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(motore, "comando_motore", lambda: (["programma_che_non_esiste_pmn.exe"], []))
    apri(f, tmp_path)
    f.vai("esecuzione")
    es = f.pagine["esecuzione"]
    qtbot.waitUntil(lambda: es.stato == "errore", timeout=ATTESA)
    assert un_principale(f).text() == "Apri la pagina Motore"
    un_principale(f).click()
    assert f.attuale == "motore"


def test_campione_da_controllare(f, qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0 --scenario CAMPIONE_DA_CONTROLLARE")
    _, es = esegui_fino_alla_fine(f, qtbot, tmp_path)
    assert any("Campione da controllare" in scritte(r) for r in riquadri(es, "avviso"))      # R9
    un_principale(f).click()
    ris = f.pagine["risultati"]
    gialli = [r for r in riquadri(ris, "avviso") if "da controllare" in scritte(r)]
    assert len(gialli) == 1 and "poche read senza l'ospite" in scritte(gialli[0])


# ---------------- Risultati ----------------
def test_risultati_metaphlan_e_kraken_separati(f, qtbot, tmp_path, monkeypatch):
    p, _ = esegui_fino_alla_fine(f, qtbot, tmp_path)
    f.vai("risultati")
    ris = f.pagine["risultati"]
    sintesi = scritte(ris.contenuto)
    assert "Il 53,7 % delle read non è assegnato" in sintesi and "48 taxa sopra la soglia" in sintesi
    linguette = ris.findChild(QTabBar)
    assert [linguette.tabText(i) for i in range(3)] == ["Specie trovate con MetaPhlAn", "Specie trovate con Kraken",
                                                        "Come è stata fatta l'analisi"]
    assert [not w.isHidden() for w in ris.schede] == [True, False, False]       # una scheda alla volta
    linguette.setCurrentIndex(1)
    assert [not w.isHidden() for w in ris.schede] == [False, True, False]
    mpa, krk, come = (scritte(w) for w in ris.schede)
    assert "gelidum" in mpa and "Debaryomyces" not in mpa and "53,7 %" in mpa       # R12: mai fusi
    assert "Debaryomyces" in krk and "gelidum" not in krk and "Metodo diverso" in krk
    assert PROTOTIPO in krk and PROTOTIPO not in mpa and "Kraken è un prototipo" in sintesi    # D115
    assert "tarate su comunità simulate e su un campione di controllo (Zymo), non ancora su salumi veri" in krk
    assert "ancora in prova" not in krk                                          # K4 fatta (19/10)
    assert "Qui le 15 più abbondanti delle 27 specie" in mpa and "Qui i 15 più abbondanti dei 48" in krk   # v0.3
    assert "Homo sapiens" in krk and "Homo sapiens" not in mpa                         # non microbi a parte
    assert "uomo (GRCh38)" in come and "1.507.887" in come
    assert "Strumenti e database usati" in sintesi and "Blanco-Míguez" in sintesi     # R14
    assert un_principale(f).text() == "Prevedi la sicurezza alimentare"

    aperti = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda u: aperti.append(Path(u.toLocalFile())))
    [b for b in ris.findChildren(QPushButton) if b.text() == "Apri il referto in PDF"][0].click()
    ris.apri(tmp_path.parent)                                  # fuori dal progetto: non si apre
    ris.apri(p.cartella / ".." / ".." / "x.txt")
    assert aperti == [(p.risultati / "referto" / "referto.pdf").resolve()]
    [b for b in ris.findChildren(QPushButton) if b.text() == "Apri il referto"][0].click()
    assert "Referto dell'analisi" in ris.finestra_referto.findChild(QTextBrowser).toPlainText()
    ris.finestra_referto.close()


def test_apri_il_controllo_qualita(f, qtbot, tmp_path, monkeypatch):
    """v0.4 (22/10): il pulsante apre il report MultiQC di risultati/qc/ (risultati.json "qc"); spento se manca, o se
    il percorso esce dal progetto."""
    p, _ = esegui_fino_alla_fine(f, qtbot, tmp_path)
    f.vai("risultati")
    ris = f.pagine["risultati"]
    pulsante = lambda: [b for b in ris.findChildren(QPushButton) if b.text() == "Apri il controllo qualità"][0]  # noqa: E731
    assert not pulsante().isEnabled() and "il controllo qualità" in scritte(ris.contenuto)   # finto motore: niente qc
    indice = json.loads((p.risultati / "risultati.json").read_text(encoding="utf-8"))
    (p.risultati / "qc").mkdir()
    (p.risultati / "qc" / "prova_multiqc_report.html").write_text("<html></html>", encoding="utf-8")
    for percorso, acceso in (("../../fuori_multiqc_report.html", False), ("qc/prova_multiqc_report.html", True)):
        (tmp_path / "fuori_multiqc_report.html").write_text("x", encoding="utf-8")
        indice["qc"] = {"multiqc": percorso, "fastp": [], "fastqc": [], "campioni": []}
        (p.risultati / "risultati.json").write_text(json.dumps(indice), encoding="utf-8")
        f.vai("home")
        f.vai("risultati")
        assert pulsante().isEnabled() is acceso
    aperti = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda u: aperti.append(Path(u.toLocalFile())))
    pulsante().click()
    assert aperti == [(p.risultati / "qc" / "prova_multiqc_report.html").resolve()]


def test_senza_progetto_si_va_ai_progetti(f):
    for chiave in ("esecuzione", "risultati", "sicurezza"):
        f.vai(chiave)
        assert un_principale(f).text() == "Apri i miei progetti"
        un_principale(f).click()
        assert f.attuale == "home"


def test_risultati_senza_progetto_invita_ad_agire(f, tmp_path):
    p = apri(f, tmp_path, avvia=False)
    f.vai("risultati")
    assert "non ha ancora risultati" in scritte(f.pagine["risultati"].contenuto)
    assert un_principale(f).text() == "Vai alle scelte dell'analisi"
    f.vai("sicurezza")
    assert "prima fai l'analisi" in f.pagine["sicurezza"].invito.text()
    assert p.risultati.exists() is False


# ---------------- Sicurezza alimentare ----------------
def scrivi(pagina, **campi):
    for nome, valore in campi.items():
        getattr(pagina, nome).setText(valore)


def calcola(sic, qtbot):
    sic.calcola.click()
    qtbot.waitUntil(lambda: not sic.client.in_corso() and sic.calcola.isEnabled(), timeout=ATTESA)


def test_sicurezza_salsiccia_cresce_e_va_nel_referto(f, qtbot, tmp_path):
    p, _ = esegui_fino_alla_fine(f, qtbot, tmp_path)
    f.vai("sicurezza")
    sic = f.pagine["sicurezza"]
    b = un_principale(f)
    assert b.text() == "Aggiungi al referto" and not b.isEnabled()     # prima si calcola
    assert "non quanti sono per grammo" in scritte(sic)

    sic.calcola.click()                                                # campi vuoti: lo dice, non lancia
    assert not sic.client.in_corso() and "Manca «Temperatura»" in scritte(sic)
    scrivi(sic, temperatura="5", giorni="21", sale="3,5", ph="6,0", nitrito="100")
    calcola(sic, qtbot)
    schede = sic.findChildren(QFrame, "scenario")
    assert [s.property("esito") for s in schede] == ["cresce", "cresce"]
    assert "10<sup>4,5</sup>" in schede[1].findChildren(QLabel)[1].text()       # numeri del motore, formattati
    assert "circa 30.000 ufc/g" in scritte(schede[1]) and "circa 17 giorni" in scritte(schede[1])
    assert [PROTOTIPO in scritte(r) for r in riquadri(sic, "avviso")] == [True]  # solo il prototipo (D115), nessun fuori campo
    assert "non trovata" in scritte(sic) and "Latilactobacillus sakei" in scritte(sic)
    assert "Food Spoilage and Safety Predictor" in scritte(sic)
    richiesta = json.loads((p.cartella / "sicurezza_richiesta.json").read_text(encoding="utf-8"))
    assert richiesta["prodotto"] == {"temperatura": 5, "sale_fase_acquosa": 3.5, "ph": 6.0, "nitrito": 100}
    assert (p.risultati / "sicurezza" / "SRR4875279.json").is_file()

    assert b.isEnabled()
    b.click()                                                          # lancia referto (D076)
    assert sic.client.comando == "referto"
    qtbot.waitUntil(lambda: f.attuale == "risultati", timeout=ATTESA)
    assert "Sicurezza alimentare" in (p.risultati / "referto" / "referto.html").read_text(encoding="utf-8")


def test_sicurezza_salame_fuori_campo_grigio(f, qtbot, tmp_path):
    esegui_fino_alla_fine(f, qtbot, tmp_path)
    f.vai("sicurezza")
    sic = f.pagine["sicurezza"]
    sic.con_aw.setChecked(True)
    scrivi(sic, temperatura="15", giorni="60", sale="0,90", ph="5,2", nitrito="100")
    calcola(sic, qtbot)
    schede = sic.findChildren(QFrame, "scenario")
    assert [s.property("esito") for s in schede] == ["incerto", "incerto"]     # mai verde su un'estrapolazione
    assert "non è una garanzia" in scritte(schede[0])
    primo = sic.uscita.itemAt(0).widget()                                       # avvisi PRIMA dei numeri (R9)
    assert primo.property("livello") == "avviso" and "pH = 5,2" in scritte(primo)
    assert un_principale(f).isEnabled()


def test_sicurezza_rimostra_l_ultima_previsione(f, qtbot, tmp_path, qapp):
    p, _ = esegui_fino_alla_fine(f, qtbot, tmp_path)
    f.vai("sicurezza")
    sic = f.pagine["sicurezza"]
    scrivi(sic, temperatura="5", giorni="21", sale="3,5", ph="6,0", lab="1000000")
    calcola(sic, qtbot)
    f2 = finestra.Finestra(movimento=False)                     # app riaperta sullo stesso progetto
    qtbot.addWidget(f2)
    f2.fuori.setCurrentIndex(1)
    f2.contesto.progetto = p
    f2.vai("sicurezza")
    s2 = f2.pagine["sicurezza"]
    assert s2.lab.text() == "1000000" and s2.sale.text() == "3,5"
    assert len(s2.findChildren(QFrame, "scenario")) == 2 and s2.principale_attivo


def test_sicurezza_usa_le_ufc_del_motore(f):
    """v0.3 (D088): il valore finale in ufc/g lo arrotonda il motore; l'app non fa più 10 alla x."""
    sic = f.pagine["sicurezza"]
    p = {"scenario": "Listeria 1 ufc/g (e se)", "modello": "listeria", "listeria_puo_crescere": True,
         "n0_listeria_ufc_g": 1, "finale_listeria_ufc_g": 12000, "curva": {"giorni": [0, 21], "log_listeria": [0, 4.48]}}
    assert "circa 12.000 ufc/g" in scritte(sic._scheda(p, False))
    del p["finale_listeria_ufc_g"]                                               # motore v0.2: ripiego
    assert "circa 30.000 ufc/g" in scritte(sic._scheda(p, False))


def test_poche_specie_tutte_mostrate(f):
    """Mini-campione d'esempio: 6 specie, tutte nelle barre: non "le 6 più abbondanti delle 6"."""
    ris = f.pagine["risultati"]
    dom = [{"nome": "Latilactobacillus sakei", "pct": 24.5, "pct_microbi": 40.4}]
    c = [{"nome": "mini", "sintesi": {"metaphlan": {"non_assegnata_pct": 56.2, "specie": 1, "dominanti": dom},
                                      "kraken": {"microbi": 1, "dominanti": dom}}}]
    assert "Qui tutte le 1 specie trovate." in scritte(ris._scheda_metaphlan(c))
    assert "Qui tutti i 1 taxa sopra la soglia." in scritte(ris._scheda_kraken(c))
