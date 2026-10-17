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
from PySide6.QtWidgets import QLabel, QPushButton  # noqa: E402

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
    assert f.aiuto.text() == "Tempo stimato: circa 56 minuti. Spazio: 12 GB."     # riassunto anche nella barra
    assert "circa 56 minuti (download 2 minuti, ospite 5 minuti, MetaPhlAn 6 minuti, Kraken 41 minuti)" in scritte(f.pagine["scelte"])
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
    for n in ("A_R1.fastq.gz", "A_R2.fastq.gz", "B_1.fq.gz", "B_2.fq.gz", "solo.fastq.gz", "note.txt"):
        (reads / n).write_bytes(b"")
    c.usa_cartella(reads)
    assert [n for n, _, _ in progetto.campioni_locali(reads)] == ["A_R1", "B_1", "solo"]
    assert "Ho trovato 3 campioni" in scritte(c) and "Per solo c'è un solo file" in scritte(c)
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
    assert "Ci vorrà molto tempo." in scritte(s) and "circa 9,1 ore" in scritte(s)
    secondario(f, "Passa allo screening rapido").click()
    assert s.rapido.pulsante.isChecked()
    assert f.contesto.progetto.leggi()["motore"]["kraken_db"] == "rapido"
    aspetta_stima(qtbot, f)                                  # la stima riparte con lo screening rapido
    assert [b.text() for b in f.secondari] == []             # già rapido: niente pulsante


def test_esperti_chiusi_consigliati_e_fonti(qtbot, f):
    s = vai_alle_scelte(qtbot, f)
    assert not s.esperti.isVisible()                          # R6: chiusi
    profili = scelte.profili_kraken()
    assert s.confidenza.currentData() == profili["completo"]["confidenza"] == "0"
    assert s.confidenza.currentText() == "0 (consigliato)" and s.soglia.currentText() == "0,005 % (consigliato)"
    s.apri_esperti.click()
    assert s.esperti.isVisible() and "Wright, Comeau e Langille 2023" in scritte(s) and "Edwin et al. 2024" in scritte(s)
    s.rapido.pulsante.setChecked(True)                       # segue il consigliato del nuovo database
    assert s.confidenza.currentData() == profili["rapido"]["confidenza"] == "0.1"
    assert f.contesto.progetto.leggi()["profiling"]["kraken_confidence"] == ""
    s.confidenza.setCurrentIndex(s.confidenza.findData("0.2"))
    s.lunghezza.setCurrentIndex(s.lunghezza.findData(100))
    cfg = f.contesto.progetto.leggi()["profiling"]
    assert cfg["kraken_confidence"] == 0.2 and cfg["bracken_readlen"] == 100
    s.apri_file.click()
    assert "kraken_confidence: 0.2" in s.file.toPlainText()
    f.vai("scelte")                                          # riaperta: restano le scelte dell'utente
    assert s.rapido.pulsante.isChecked() and s.confidenza.currentData() == "0.2"


def test_virus_sempre_con_riquadro_ambra(qtbot, f):
    s = vai_alle_scelte(qtbot, f)
    assert "Sperimentale, non validata." in scritte(s)        # R13
    s.virus.setChecked(True)
    assert f.contesto.progetto.leggi()["motore"]["virus"] is True


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
