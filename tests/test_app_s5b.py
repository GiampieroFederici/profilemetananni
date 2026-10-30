# -*- coding: utf-8 -*-
"""Pagine di S5b (I miei progetti, Campioni e prodotto, Scelte dell'analisi, Motore, Come citare) contro il finto
motore (--velocita 0). Gira con l'ambiente dell'app su Windows:
  app\\.venv\\Scripts\\python -m pytest tests/test_app_s5b.py
I progetti vanno in una cartella temporanea (mai in Documenti) e il finto motore tiene il suo stato in una
cartella temporanea sua (TEMP), così non si pesta i piedi con altre sessioni."""
import csv
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton  # noqa: E402

from app import finestra, motore, progetto  # noqa: E402
from app.pagine import crediti, scelte  # noqa: E402
from app.pagine.progetto import PRODOTTI  # noqa: E402

PAGINE_S5B = ["home", "campioni", "scelte", "motore", "crediti"]


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("PMN_MOTORE", "finto")
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("TMP", str(tmp_path / "temp"))
    (tmp_path / "temp").mkdir()
    radice = tmp_path / "Documenti" / "ProfileMetaNanni"
    monkeypatch.setattr(progetto, "cartella_progetti", lambda: radice)
    monkeypatch.setattr(finestra, "AVVIO_MIN_MS", 0)
    return radice


def scenario(monkeypatch, nome):
    monkeypatch.setenv("PMN_FINTO_OPZIONI", f"--velocita 0 --scenario {nome}")


@pytest.fixture
def f(qtbot):
    w = finestra.Finestra(movimento=False)
    qtbot.addWidget(w)
    w.show()
    w.avvia()
    qtbot.waitUntil(lambda: w.attuale == "home", timeout=30000)
    return w


def scritte(pagina):
    """Tutto il testo visibile della pagina (dopo aver tolto i widget già cancellati)."""
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QCoreApplication.processEvents()                 # i widget nuovi si mostrano al giro dopo (QLayout)
    return " ".join(e.text() for e in pagina.findChildren(QLabel) if e.isVisibleTo(pagina))


def apri(pagina):
    QCoreApplication.processEvents()
    return [b.text() for b in pagina.findChildren(QPushButton, "apri") if b.isVisibleTo(pagina)]


def principali(f):
    return [b for b in f.findChildren(QPushButton, "principale") if b.isVisible()]


def premi(f):
    """Come l'utente: un solo pulsante principale visibile (R1), lo premo."""
    b = principali(f)
    assert len(b) == 1
    assert all(p.findChildren(QPushButton, "principale") == [] for p in f.pagine.values())   # nessuna pagina ne ha uno suo
    b[0].click()


def secondario(f, testo):
    return next(b for b in f.secondari if b.text() == testo)


def aspetta_stima(qtbot, f):
    s = f.pagine["scelte"]
    qtbot.waitUntil(lambda: not s.client.in_corso() and f.aiuto.text() != "Calcolo il tempo che serve...",
                    timeout=30000)


# ---------------- R4: da Nuovo progetto ad "Avvia l'analisi" col solo pulsante principale ----------------
def test_da_nuovo_progetto_ad_avvia_l_analisi(qtbot, f, ambiente, monkeypatch):
    avvio = []
    monkeypatch.setattr(f.pagine["esecuzione"], "mostrata", lambda: avvio.append(f.contesto.avvia_analisi))
    assert "Nessun progetto" in scritte(f.pagine["home"])
    premi(f)                                                     # Nuovo progetto (nome già proposto)
    assert f.attuale == "campioni" and f.contesto.progetto is not None
    f.pagine["campioni"].testo_codici.setPlainText("SRR4875279")  # i codici li scrive l'utente (R4: "a parte")
    assert "1 codice valido" in scritte(f.pagine["campioni"])
    premi(f)                                                     # Avanti: scelte dell'analisi
    assert f.attuale == "scelte"
    assert "15,6 GB di memoria, 8 processori" in scritte(f.pagine["scelte"])
    aspetta_stima(qtbot, f)
    assert f.aiuto.text() == "Tempo stimato: circa 48 minuti. Spazio: 12 GB."     # riassunto anche nella barra
    assert "1: SRR4875279 (3,2 milioni di coppie di read)" in scritte(f.pagine["scelte"])   # nomi_campioni (v0.3)
    assert "circa 48 minuti (download 2 minuti, ospite 5 minuti, MetaPhlAn 5 minuti, Kraken 34 minuti)" in scritte(f.pagine["scelte"])
    assert f.principale.text() == "Avvia l'analisi"
    premi(f)
    assert f.attuale == "esecuzione" and avvio == [True]        # passaggio a S6 (Contesto.avvia_analisi)

    p = progetto.elenco(ambiente)[0]                              # config.yaml scritto e riletto
    cfg = p.leggi()
    assert cfg["project_name"] == p.nome and cfg["data_source"] == "ncbi"
    assert cfg["hosts"] == ["sus_scrofa"] and cfg["filter_human"] is True
    assert Path(cfg["paths"]["srr_list"]).read_text(encoding="utf-8") == "SRR4875279\n"
    assert cfg["motore"] == {"metaphlan_modo": "fette", "kraken_db": "completo", "virus": False, "processori": 8}
    assert cfg["profiling"]["kraken_confidence"] == "" and cfg["profiling"]["abundance_threshold_pct"] == ""
    assert cfg["profiling"]["bracken_min_reads"] == ""                          # consigliato = vuoto (v0.3)
    assert cfg["profiling"]["metaphlan_index"] == "mpa_vJan25_CHOCOPhlAnSGB_202503"
    assert cfg["app"]["prodotto"] == "maiale" and cfg["app"]["scelte"] is True
    assert (p.cartella / "config.yaml").read_text(encoding="utf-8").startswith("language: it")


def test_r1_su_ogni_pagina(f):
    for chiave in PAGINE_S5B:
        f.vai(chiave)
        assert len(principali(f)) == 1, chiave
        assert f.principale.text(), chiave
        assert all(b.isVisible() for b, _, _ in f.passi.values())          # R3


# ---------------- I miei progetti ----------------
def test_home_nome_sbagliato_doppione_e_apri(qtbot, f, ambiente):
    h = f.pagine["home"]
    h.nome.setText("con spazio")
    premi(f)
    assert f.attuale == "home" and "Questo nome non va bene." in scritte(h)
    h.nome.setText("salame_lotto_12")
    premi(f)
    assert f.attuale == "campioni"
    f.vai("home")
    assert "salame_lotto_12" in apri(h)
    h.nome.setText("salame_lotto_12")
    premi(f)
    assert "Esiste già un progetto che si chiama salame_lotto_12." in scritte(h)
    f.contesto.progetto = None
    next(b for b in h.findChildren(QPushButton, "apri") if b.text() == "salame_lotto_12").click()
    assert f.attuale == "campioni" and f.contesto.progetto.nome == "salame_lotto_12"


def test_elenco_dal_piu_recente(qtbot, f, ambiente):
    import os
    import time
    for i, n in enumerate(("vecchio", "nuovo")):
        p = progetto.nuovo(n)
        p.scrivi(progetto.base(n))
        os.utime(p.config, (time.time() - 100 + i * 50,) * 2)
    f.vai("home")
    assert apri(f.pagine["home"]) == ["nuovo", "vecchio"]


# ---------------- Campioni e prodotto ----------------
def test_prodotti_e_ospiti_di_hosts_tsv():
    with open(RADICE / "refs" / "hosts.tsv", encoding="utf-8") as fh:
        nomi = {r[0] for r in csv.reader(fh, delimiter="\t") if r and not r[0].startswith("#")}
    assert list(PRODOTTI) == ["maiale", "bovino", "pecora", "altro"]          # D074: niente pollo
    assert {o for _, ospiti, *_ in PRODOTTI.values() for o in ospiti} <= nomi
    assert PRODOTTI["altro"][1] == [] and PRODOTTI["altro"][4] == "avviso"
    for _, _, titolo, perche, _ in PRODOTTI.values():
        assert "umano" in titolo and perche                                    # dice perché


def test_nomi_locali_come_il_motore(tmp_path):
    """Stessi nomi di pmn_motore.campioni_locali (v0.3): l'app non deve promettere nomi diversi."""
    sys.path.insert(0, str(RADICE / "motore"))
    import pmn_motore
    for n in ("C1_R1.fastq.gz", "C1_R2.fastq.gz", "D_R1_001.fastq.gz", "D_R2_001.fastq.gz", "E_1.fq.gz", "E_2.fq.gz",
              "F.fq.gz", "G_R1.fastq.gz", "H_2.fastq.gz", "-x.fastq.gz"):
        (tmp_path / n).write_bytes(b"")
    trovati, saltati = progetto.campioni_locali(tmp_path)
    assert [n for n, _, _ in trovati] == [n for n, _ in pmn_motore.campioni_locali(tmp_path)]
    assert saltati == ["G_R1.fastq.gz", "H_2.fastq.gz"]


def test_prodotti_dal_motore(qtbot, f, monkeypatch):
    """info.prodotti (v0.3) decide frase e ospiti; la tabella dell'app resta solo come ripiego."""
    premi(f)
    c = f.pagine["campioni"]
    regole = [dict(r) for r in f.contesto.info["prodotti"]]
    regole[1] = {**regole[1], "ospiti": ["bos_taurus", "ovis_aries"], "frase": "Frase del motore."}
    monkeypatch.setitem(f.contesto.info, "prodotti", regole)
    c.prodotto.setCurrentIndex(c.prodotto.findData("bovino"))
    assert "Frase del motore." in scritte(c)
    c.testo_codici.setPlainText("SRR4875279")
    premi(f)
    assert f.contesto.progetto.leggi()["hosts"] == ["bos_taurus", "ovis_aries"]
    f.contesto.info = None                                         # motore che non ha risposto: ripiego
    f.vai("campioni")
    assert "Toglierò il DNA del bovino e quello umano." in scritte(c)


def test_codici_dei_campioni():
    validi, scartati = progetto.codici("SRR4875279\n  err123 \n\nSRR4875279\nciao\nDRR0001")
    assert validi == ["SRR4875279", "ERR123", "DRR0001"] and scartati == ["ciao"]


def test_cartella_locale_coppie_e_prodotto(qtbot, f, ambiente, tmp_path):
    premi(f)
    c = f.pagine["campioni"]
    c.scelta_pc.pulsante.setChecked(True)
    premi(f)                                                   # senza cartella: errore vicino al campo, resta qui
    assert f.attuale == "campioni" and "Manca la cartella delle read." in scritte(c)
    vuota = tmp_path / "vuota"
    vuota.mkdir()
    c.usa_cartella(vuota)
    assert "In questa cartella non ci sono read." in scritte(c)
    brutta = tmp_path / "a;b"
    brutta.mkdir()
    (brutta / "x_R1.fastq.gz").write_bytes(b"")
    c.usa_cartella(brutta)
    assert "carattere che il motore non accetta" in scritte(c) and c.cartella is None
    reads = tmp_path / "reads"
    reads.mkdir()
    for n in ("A_R1.fastq.gz", "A_R2.fastq.gz", "B_1.fq.gz", "B_2.fq.gz", "solo.fastq.gz", "note.txt",
              "orfano_R1.fastq.gz"):
        (reads / n).write_bytes(b"")
    c.usa_cartella(reads)
    trovati, saltati = progetto.campioni_locali(reads)              # stesse regole del motore (contratto §3)
    assert [n for n, _, _ in trovati] == ["A", "B", "solo"] and saltati == ["orfano_R1.fastq.gz"]
    assert "Ho trovato 3 campioni: A, B, solo." in scritte(c) and "Per solo c'è un solo file" in scritte(c)
    assert "Salto orfano_R1.fastq.gz: manca l'altro file della coppia." in scritte(c)
    c.prodotto.setCurrentIndex(c.prodotto.findData("pecora"))
    assert "Toglierò il DNA della pecora e quello umano." in scritte(c)
    premi(f)
    assert f.attuale == "scelte"
    cfg = f.contesto.progetto.leggi()
    assert cfg["data_source"] == "local" and cfg["hosts"] == ["ovis_aries"]
    assert cfg["paths"]["local_reads_dir"] == str(reads) and cfg["paths"]["srr_list"] == ""
    f.vai("campioni")                                          # riaperta: le scelte restano
    assert c.scelta_pc.pulsante.isChecked() and c.prodotto.currentData() == "pecora" and c.cartella == reads


def test_senza_codici_non_si_va_avanti(f):
    premi(f)
    premi(f)
    assert f.attuale == "campioni" and "Manca il codice di almeno un campione." in scritte(f.pagine["campioni"])


# ---------------- Scelte dell'analisi ----------------
def vai_alle_scelte(qtbot, f):
    premi(f)
    f.pagine["campioni"].testo_codici.setPlainText("SRR4875279")
    premi(f)
    aspetta_stima(qtbot, f)
    return f.pagine["scelte"]


def test_tempo_lungo_ambra_e_screening_rapido(qtbot, f, monkeypatch):
    scenario(monkeypatch, "TEMPO_LUNGO")
    s = vai_alle_scelte(qtbot, f)
    assert s.completo.pulsante.isChecked()
    assert f.aiuto.property("livello") == "avviso" and "Ci vorrà molto" in f.aiuto.text()
    assert "Ci vorrà molto tempo." in scritte(s) and "circa 7,8 ore" in scritte(s)
    secondario(f, "Passa allo screening rapido").click()
    assert s.rapido.pulsante.isChecked()
    assert f.contesto.progetto.leggi()["motore"]["kraken_db"] == "rapido"
    aspetta_stima(qtbot, f)                                  # la stima riparte con lo screening rapido
    assert [b.text() for b in f.secondari] == []             # già rapido: niente pulsante


def test_esperti_chiusi_consigliati_e_fonti(qtbot, f):
    s = vai_alle_scelte(qtbot, f)
    assert not s.esperti.isVisible()                          # R6: chiusi
    profili = scelte.profili_kraken()
    assert s.confidenza.currentData() == profili["completo"]["confidenza"] == "0.5"          # K4 (D142)
    assert s.confidenza.currentText() == "0,5 (consigliato)" and s.soglia.currentText() == "0,1 % (consigliato)"
    s.apri_esperti.click()
    assert s.esperti.isVisible() and "Wright, Comeau e Langille 2023" in scritte(s) and "Edwin et al. 2024" in scritte(s)
    assert "K4" in scritte(s) and "Consigliato 0 con" not in scritte(s)
    s.rapido.pulsante.setChecked(True)                       # segue il consigliato del nuovo database
    assert s.confidenza.currentData() == profili["rapido"]["confidenza"] == "0.1"
    assert f.contesto.progetto.leggi()["profiling"]["kraken_confidence"] == ""
    assert s.soglia.currentText() == "0,005 % (consigliato)"                     # anche la soglia segue il database
    assert f.contesto.progetto.leggi()["profiling"]["abundance_threshold_pct"] == ""
    assert s.letture.currentText() == "10 (consigliato)" and "Lu et al. 2017" in scritte(s)   # Bracken -t (v0.3)
    s.confidenza.setCurrentIndex(s.confidenza.findData("0.2"))
    s.lunghezza.setCurrentIndex(s.lunghezza.findData(100))
    s.letture.setCurrentIndex(s.letture.findData("20"))
    cfg = f.contesto.progetto.leggi()["profiling"]
    assert cfg["kraken_confidence"] == 0.2 and cfg["bracken_readlen"] == 100 and cfg["bracken_min_reads"] == 20
    s.apri_file.click()
    assert "kraken_confidence: 0.2" in s.file.toPlainText()
    f.vai("scelte")                                          # riaperta: restano le scelte dell'utente
    assert s.rapido.pulsante.isChecked() and s.confidenza.currentData() == "0.2" and s.letture.currentData() == "20"


def test_tempo_totale_dal_motore(qtbot, f):
    """v0.3: il totale lo dà il motore (tempo_totale_s); la pagina non somma più."""
    s = vai_alle_scelte(qtbot, f)
    s._mostra_stima({"campioni": 1, "coppie_totali": 1e6, "tempo_s": {"kraken": 600}, "tempo_totale_s": 3000,
                     "spazio_gb": 1}, "")
    assert f.aiuto.text() == "Tempo stimato: circa 50 minuti. Spazio: 1 GB."
    s._mostra_stima({"campioni": 1, "coppie_totali": 2e5, "tempo_s": {}, "tempo_totale_s": 389, "spazio_gb": 0.2}, "")
    assert f.aiuto.text() == "Tempo stimato: circa 6 minuti. Spazio: meno di 1 GB."        # campione d'esempio


def test_virus_nascosto_finche_non_arriva_al_motore(qtbot, f):
    """22/10: "Anche i virus" non arriva a bin/run.sh, quindi non si mostra; il progetto scrive false."""
    s = vai_alle_scelte(qtbot, f)
    assert not s.scheda_virus.isVisibleTo(s) and not s.virus.isVisibleTo(s)
    assert "Anche i virus" not in [b.text() for b in s.findChildren(QCheckBox) if b.isVisibleTo(s)]
    assert "Sperimentale, non validata." not in scritte(s)
    assert f.contesto.progetto.leggi()["motore"]["virus"] is False


def test_stima_con_errore_porta_dove_si_risolve(qtbot, f, monkeypatch):
    premi(f)
    f.pagine["campioni"].testo_codici.setPlainText("SRR4875279")
    premi(f)
    aspetta_stima(qtbot, f)
    f.contesto.progetto.config.unlink()                       # il motore non trova il progetto
    monkeypatch.setattr(f.pagine["scelte"], "_salva", lambda scelte=False: None)
    f.pagine["scelte"]._avvia_stima()
    qtbot.waitUntil(lambda: f.principale.text() == "Correggi i campioni", timeout=30000)
    assert "Non trovo il file del progetto." in scritte(f.pagine["scelte"])
    premi(f)
    assert f.attuale == "campioni"


# ---------------- Motore ----------------
def test_verifica_verde(qtbot, f):
    respiri = []
    f.pagine["motore"].respira.connect(respiri.append)
    f.vai("motore")
    m = f.pagine["motore"]
    assert "15,6 GB di memoria, 8 processori, 643 GB liberi" in m.stato.text()
    assert "Kraken, database completo" in scritte(m) and "118,6 GB" in scritte(m)
    assert "MetaPhlAn 4.2.4, Kraken 2.17.2, Bracken 3.1" in m.stato.text()
    premi(f)
    qtbot.waitUntil(lambda: respiri == [True, False], timeout=30000)
    assert "VERDE: il motore funziona." in scritte(m) and "✓ MD5 dei database" in scritte(m)
    assert f.principale.text() == "Controlla il motore" and f.principale.isEnabled()


def test_esito_della_verifica_in_vista_su_schermo_piccolo(qtbot, f):
    """B2 (P7): sulla VM (8 database, un consiglio, 12 controlli) il VERDE restava sotto la piega e non si vedeva."""
    from PySide6.QtCore import QPoint
    f.resize(f.minimumSize())                                          # la finestra più piccola che l'app permette
    f.vai("motore")
    m = f.pagine["motore"]
    scorre = f.pila.currentWidget()
    db = [{"nome": f"altro_{i}", "installato": i < 2, "gb": None} for i in range(8)]       # come sulla VM
    f.contesto.info = dict(f.contesto.info, database=db, consigli=[{"livello": "avviso", "messaggio": "Manca Kraken."}])
    m._disegna()
    controlli = [{"nome": f"pmn_programma_{i} = 1.{i}", "esito": "ok"} for i in range(12)]
    m._esito("verifica", {"esito": "ok", "messaggio": "VERDE: il motore funziona.", "risultato": {"controlli": controlli}})
    esito = m.zona_esito.itemAt(0).widget()
    qtbot.wait(300)                                                    # le etichette vanno a capo in più giri

    def in_vista():
        QCoreApplication.processEvents()
        y, alto = esito.mapTo(scorre.viewport(), QPoint(0, 0)).y(), scorre.viewport().height()
        return 0 <= y and y + min(esito.height(), alto) <= alto           # si vede tutto (o tutto quello che ci sta)
    assert in_vista()


def test_finestra_mai_piu_grande_dello_schermo():
    """B2 (P7): sulla VM la finestra (1366 x 860, minimo 1100 x 700) usciva dallo schermo e la testata era tagliata."""
    from PySide6.QtCore import QSize
    assert finestra.misure(QSize(1920, 1040)) == (QSize(1366, 860), QSize(1100, 700))      # schermo grande: come prima
    grande, minima = finestra.misure(QSize(1024, 728))                                     # 1024 x 768 meno la barra
    assert grande.width() <= 1024 and grande.height() <= 728 - 40                          # 40: barra del titolo
    assert minima.width() <= grande.width() and minima.height() <= grande.height()


def test_spazio_libero_quello_vero_di_windows(qtbot, f, monkeypatch):
    """B2 (P8): dentro la WSL si vede il disco virtuale (990 GB sulla VM); conta il disco di Windows che lo contiene."""
    from app.pagine import motore as pagina_motore
    f.vai("motore")
    m = f.pagine["motore"]
    vero = dict(f.contesto.info, finto=False)                 # come il motore vero
    monkeypatch.setattr(pagina_motore, "spazio_windows_gb", lambda: 146.4)
    f.contesto.info = vero
    m._disegna()
    assert "146 GB liberi" in m.stato.text()
    monkeypatch.setattr(pagina_motore, "spazio_windows_gb", lambda: 2000.0)   # mai più di quello della WSL
    m._disegna()
    assert "643 GB liberi" in m.stato.text()
    monkeypatch.setattr(pagina_motore, "spazio_windows_gb", lambda: None)     # WSL non trovata: il numero del motore
    m._disegna()
    assert "643 GB liberi" in m.stato.text()


def test_spazio_windows_della_wsl_pmn():
    """Su questo PC la WSL pmn c'è: lo spazio è quello del suo disco di Windows."""
    import shutil
    import winreg
    from app.motore import spazio_windows_gb
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Lxss"):
            pass
    except OSError:
        pytest.skip("nessuna WSL su questo PC")
    gb = spazio_windows_gb()
    if gb is None:
        pytest.skip("WSL pmn non installata")
    assert abs(gb - shutil.disk_usage("C:\\").free / 1e9) < 5          # sul PC di sviluppo la WSL pmn sta su C:


def test_verifica_rossa_porta_a_installa(qtbot, f, monkeypatch):
    scenario(monkeypatch, "DB_MANCANTE")
    f.vai("motore")
    premi(f)
    qtbot.waitUntil(lambda: f.principale.text() == "Installa o completa", timeout=30000)
    m = f.pagine["motore"]
    assert "ROSSO: Manca il database di Kraken." in scritte(m)
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    premi(f)                                                  # installa, con la barra
    qtbot.waitUntil(lambda: "VERDE: il motore è installato e funziona." in scritte(m), timeout=30000)
    assert m.barra.value() == 93 and f.principale.text() == "Controlla il motore"


def test_motore_non_avviato(qtbot, monkeypatch):
    monkeypatch.setattr(motore, "comando_motore", lambda: (["programma_che_non_esiste_pmn.exe"], []))
    w = finestra.Finestra(movimento=False)
    qtbot.addWidget(w)
    w.show()
    w.avvia()
    qtbot.waitUntil(lambda: w.attuale == "home", timeout=30000)
    assert "Il motore non ha risposto." in scritte(w.pagine["home"])
    w.vai("motore")
    qtbot.waitUntil(lambda: "WSL" in scritte(w.pagine["motore"]), timeout=30000)
    assert "Il motore non risponde" in scritte(w.pagine["motore"])


# ---------------- Come citare ----------------
def test_come_citare(f):
    voci = [v for _, vv in crediti.FONTI for v in vv]
    testo = " ".join(voci)
    for chiave in ("MetaPhlAn 4", "Kraken 2", "Bracken", "Bowtie 2", "fastp", "FSSP", "DTU", "Dalgaard",
                   "mpa_vJan25_CHOCOPhlAnSGB_202503", "PlusPF", "Sscrofa11.1", "GRCh38"):
        assert chiave in testo, chiave
    assert sum("DOI 10." in v for v in voci) >= 25
    f.vai("crediti")
    premi(f)
    assert f.attuale == "home"


def test_niente_trattini_lunghi():
    for nome in ("home", "progetto", "scelte", "motore", "crediti"):
        assert "—" not in (RADICE / "app" / "pagine" / f"{nome}.py").read_text(encoding="utf-8"), nome


# ---------------- campione d'esempio e avvio a freddo (A2) ----------------
def test_campione_d_esempio_a_un_clic(qtbot, f, ambiente):
    h = f.pagine["home"]
    f.vai("home")
    assert h.esempio.isVisible() and "SRR4875279" in scritte(h)
    next(b for b in h.findChildren(QPushButton) if b.text() == "Prova il campione d'esempio").click()
    assert f.attuale == "scelte" and f.contesto.progetto.nome == "esempio_SF3RAt7"
    cfg = f.contesto.progetto.leggi()
    assert cfg["data_source"] == "local" and cfg["paths"]["local_reads_dir"] == "/home/pmn/.pmn/db/prova"
    assert cfg["hosts"] == ["sus_scrofa"] and cfg["app"]["esempio"] is True
    aspetta_stima(qtbot, f)
    assert f.principale.text() == "Avvia l'analisi"
    f.vai("campioni")                                              # niente da scegliere: lo dice e va avanti
    c = f.pagine["campioni"]
    assert "Questo è il progetto d'esempio." in scritte(c) and not c.prodotto.isEnabled()
    assert not c.zona_pc.isVisible() and not c.zona_ncbi.isVisible()
    premi(f)
    assert f.attuale == "scelte" and f.contesto.progetto.leggi()["paths"]["local_reads_dir"] == "/home/pmn/.pmn/db/prova"
    f.vai("home")                                                  # di nuovo: riapre lo stesso progetto
    next(b for b in h.findChildren(QPushButton) if b.text() == "Prova il campione d'esempio").click()
    assert f.attuale == "scelte" and [p.nome for p in progetto.elenco(ambiente)] == ["esempio_SF3RAt7"]
    f.contesto.progetto = progetto.Progetto(ambiente / "altro")    # un progetto normale non è "d'esempio"
    f.vai("campioni")
    assert c.prodotto.isEnabled() and "Questo è il progetto d'esempio." not in scritte(c)


def test_senza_esempio_niente_pulsante(f, monkeypatch):
    monkeypatch.setitem(f.contesto.info, "esempio", None)           # motore senza mini-campione
    f.vai("home")
    assert not f.pagine["home"].esempio.isVisible()


def test_avvio_lento_spiegato(qtbot, monkeypatch):
    monkeypatch.setattr(finestra, "AVVIO_LENTO_MS", 50)
    monkeypatch.setattr(motore.MotoreClient, "avvia", lambda self, *a: None)    # info non arriva mai
    w = finestra.Finestra(movimento=False)
    qtbot.addWidget(w)
    w.avvia()
    assert w.messaggio_avvio.text() == "Avvio il motore..."
    qtbot.waitUntil(lambda: w.messaggio_avvio.text() == finestra.AVVIO_LENTO, timeout=5000)
    assert "fino a un minuto" in w.messaggio_avvio.text()
