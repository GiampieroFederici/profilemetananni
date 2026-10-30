# -*- coding: utf-8 -*-
"""R8 (incarico OSPITE, 30/10): scelta dell'ospite nella pagina Campioni e prodotto e finestra "Aggiungi un ospite",
contro il finto motore. Gira con l'ambiente dell'app su Windows:
  app\\.venv\\Scripts\\python -m pytest tests/test_ospiti_app.py
NCBI non si chiama mai: progetto.dimensione_ncbi è sostituita."""
import csv
import gzip
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtWidgets import QDialog  # noqa: E402

from app import progetto  # noqa: E402
from app.pagine import progetto as pagina  # noqa: E402
from test_app_s5b import ambiente, f, premi, scritte  # noqa: E402,F401  (stesse fixture della pagina)


def test_nomi_del_motore_come_hosts_tsv():
    """L'app impacchettata non ha refs/hosts.tsv: i nomi riservati devono coprirlo tutto."""
    with open(RADICE / "refs" / "hosts.tsv", encoding="utf-8") as fh:
        nomi = {r[0] for r in csv.reader(fh, delimiter="\t") if r and not r[0].startswith("#")}
    assert nomi <= progetto.OSPITI_DEL_MOTORE
    assert {k for k, _t in pagina.OSPITI} - {pagina.NESSUNO} <= nomi


def test_stima_come_il_motore():
    sys.path.insert(0, str(RADICE / "motore"))
    import ospiti
    for basi in (4_641_652, 494_873_210, 3_136_819_154):
        a, m = progetto.stima_indice(basi, scaricare=True), ospiti.stima(basi, scaricare=True)
        assert round(a["secondi"]) == m["secondi"] and round(a["ram_gb"], 1) == m["ram_gb"]
        assert round(a["disco_gb"], 1) == m["disco_gb"] and round(a["temporaneo_gb"], 1) == m["temporaneo_gb"]


def test_controlla_fasta(tmp_path):
    buono = tmp_path / "l'olivo" / "genoma.fna.gz"
    buono.parent.mkdir()
    with gzip.open(buono, "wt") as g:
        g.write(">chr1\n" + "ACGT" * 1000 + "\n")
    basi, problema = progetto.controlla_fasta(buono)
    assert problema is None and basi == round(buono.stat().st_size * progetto.GZ_RAPPORTO)
    (tmp_path / "testo.fa").write_text("ciao\n")
    (tmp_path / "g.txt").write_text(">x\nA\n")
    (tmp_path / "a$b").mkdir()
    (tmp_path / "a$b" / "g.fa").write_text(">x\nA\n")
    for f_, atteso in [(tmp_path / "testo.fa", "non è un genoma"), (tmp_path / "g.txt", "deve finire"),
                       (tmp_path / "manca.fa", "Non riesco a leggere"), (tmp_path / "a$b" / "g.fa", "carattere")]:
        basi, problema = progetto.controlla_fasta(f_)
        assert basi is None and atteso in problema, (f_, problema)


def test_nome_e_elenco(ambiente):
    assert progetto.errore_nome_ospite("olivo") is None
    for nome in ("o", "1olivo", "olivo-x", "olìvo", "sus_scrofa", "Grch38", ""):
        assert progetto.errore_nome_ospite(nome), nome
    progetto.aggiungi_ospite("olivo", {"accession": "GCF_000000001.1", "basi": 10})
    assert progetto.file_ospiti() == ambiente / "ospiti_personali.yaml"      # fuori dalla cartella del programma
    assert progetto.ospiti_personali()["olivo"]["accession"] == "GCF_000000001.1"
    assert "Esiste già" in progetto.errore_nome_ospite("olivo")
    with pytest.raises(ValueError):
        progetto.aggiungi_ospite("olivo", {"accession": "GCF_000000002.1"})


def test_dimensione_ncbi_non_chiama_codici_non_validi(monkeypatch):
    chiamate = []
    monkeypatch.setattr(progetto, "_chiedi", lambda *a, **k: chiamate.append(a))
    assert progetto.dimensione_ncbi("GCF_1; rm -rf /") is None and chiamate == []


def test_salame_come_prima(qtbot, f):
    """Senza toccare l'ospite: maiale proposto e consigliato, hosts come la regola del prodotto, filter_human vero."""
    premi(f)
    c = f.pagine["campioni"]
    assert c.ospite.currentData() == "sus_scrofa" and "(consigliato)" in c.ospite.currentText()
    assert "Toglierò il DNA del maiale e quello umano." in scritte(c)
    c.testo_codici.setPlainText("SRR4875279")
    premi(f)
    cfg = f.contesto.progetto.leggi()
    assert cfg["hosts"] == ["sus_scrofa"] and cfg["filter_human"] is True and "ospiti_personali" not in cfg
    assert "ospite" not in cfg["app"]                          # config.yaml dei salumi come prima


def scegli(c, chiave):
    c.ospite.setCurrentIndex(c.ospite.findData(chiave))
    c.ospite.activated.emit(c.ospite.currentIndex())


def test_cambio_ospite_vite_e_nessuno_si_rilegge(qtbot, f):
    premi(f)
    c = f.pagine["campioni"]
    c.testo_codici.setPlainText("SRR4875279")
    scegli(c, "vitis_vinifera")
    assert "Hai cambiato l'ospite proposto" in scritte(c) and "costruisco il suo indice" in scritte(c)
    premi(f)
    cfg = f.contesto.progetto.leggi()
    assert cfg["hosts"] == ["vitis_vinifera"] and cfg["app"]["ospite"] == "vitis_vinifera"
    f.vai("campioni")                                           # riaperto: la scelta resta
    assert c.ospite.currentData() == "vitis_vinifera" and c.prodotto.currentData() == "maiale"
    scegli(c, pagina.NESSUNO)
    assert "tolgo solo il DNA umano" in scritte(c)
    premi(f)
    assert f.contesto.progetto.leggi()["hosts"] == [] and f.contesto.progetto.leggi()["filter_human"] is True
    f.vai("campioni")
    c.prodotto.setCurrentIndex(c.prodotto.findData("bovino"))   # un altro prodotto riporta il suo ospite
    assert c.ospite.currentData() == "bos_taurus" and c.ospite_scelto is None


def test_ambienti_nuovi_da_info_prodotti(qtbot, f, monkeypatch):
    """Gli ambienti che AMBIENTI mette in info.prodotti (testo, sperimentale, ospiti) compaiono senza toccare l'app."""
    regole = [dict(r) for r in f.contesto.info["prodotti"]] + [
        {"prodotto": "vite_foglia", "testo": "Vite: foglia", "sperimentale": True, "ospiti": ["vitis_vinifera"],
         "genomi": ["T2T-PN40024 (ASM3070453v1)"], "frase": "Toglierò il DNA della vite e quello umano.",
         "perche": "Perché.", "livello": "info"},
        {"prodotto": "feci_umane", "testo": "Feci umane", "sperimentale": True, "ospiti": ["grch38"],
         "genomi": ["GRCh38.p14"], "frase": "Toglierò il DNA umano.", "perche": "Perché.", "livello": "info"}]
    monkeypatch.setitem(f.contesto.info, "prodotti", regole)
    premi(f)
    c = f.pagine["campioni"]
    testi = [c.prodotto.itemText(i) for i in range(c.prodotto.count())]
    assert "Vite: foglia (sperimentale)" in testi and testi[0].startswith("Salume di maiale")
    c.prodotto.setCurrentIndex(c.prodotto.findData("vite_foglia"))
    assert c.ospite.currentData() == "vitis_vinifera" and "(consigliato)" in c.ospite.currentText()
    c.prodotto.setCurrentIndex(c.prodotto.findData("feci_umane"))
    assert c.ospite.currentData() == "grch38"
    c.testo_codici.setPlainText("SRR4875279")
    premi(f)
    cfg = f.contesto.progetto.leggi()
    assert cfg["hosts"] == ["grch38"] and cfg["app"]["prodotto"] == "feci_umane"


def test_finestra_ncbi_stima_e_aggiunge(qtbot, f, monkeypatch, ambiente):
    monkeypatch.setattr(progetto, "dimensione_ncbi", lambda acc: (2_000_000_000, "Olea europaea"))
    w = pagina.FinestraOspite(ram_gb=3.0, libero_gb=100)
    qtbot.addWidget(w)
    w.nome.setText("olivo")
    w.codice.setText("gcf_1")
    w.controlla()
    assert "Il codice non va bene." in scritte(w) and not w.pulsante_aggiungi.isEnabled()
    w.codice.setText("GCF_902713115.1")
    w.controlla()
    testo = scritte(w)
    assert "Olea europaea: circa 2,0 miliardi di basi." in testo
    assert "4,8 GB di memoria" in testo and "vede solo 3,0 GB" in testo     # avviso RAM
    assert w.pulsante_aggiungi.isEnabled()
    w.codice.setText("GCF_902713115.2")                               # cambiato: va ricontrollato
    assert not w.pulsante_aggiungi.isEnabled()
    w.controlla()
    w.aggiungi()
    assert w.result() == QDialog.Accepted and w.aggiunto == "olivo"
    assert progetto.ospiti_personali()["olivo"]["accession"] == "GCF_902713115.2"


def test_finestra_codice_sconosciuto_e_rete_assente(qtbot, f, monkeypatch):
    w = pagina.FinestraOspite()
    qtbot.addWidget(w)
    w.nome.setText("olivo")
    w.codice.setText("GCF_000000009.1")
    monkeypatch.setattr(progetto, "dimensione_ncbi", lambda acc: None)
    w.controlla()
    assert "NCBI non conosce il codice GCF_000000009.1." in scritte(w) and not w.pulsante_aggiungi.isEnabled()

    def senza_rete(acc):
        raise progetto.NcbiNonRaggiungibile("rete")
    monkeypatch.setattr(progetto, "dimensione_ncbi", senza_rete)
    w.controlla()
    assert "Non riesco a chiedere a NCBI" in scritte(w) and w.pulsante_aggiungi.isEnabled()


def test_finestra_fasta_e_pagina(qtbot, f, monkeypatch, tmp_path):
    """FASTA locale: stima, aggiunta all'elenco, scelta nella pagina, config.yaml con ospiti_personali, riapertura."""
    genoma = tmp_path / "genomi" / "l'olivo.fa"
    genoma.parent.mkdir()
    genoma.write_text(">chr1\n" + "ACGT" * 1000 + "\n")
    premi(f)
    c = f.pagine["campioni"]
    c.testo_codici.setPlainText("SRR4875279")

    def esegui(finestra):
        finestra.nome.setText("olivo")
        finestra.scelta_file.pulsante.setChecked(True)
        finestra.controlla()
        assert "Manca il file del genoma." in scritte(finestra)
        finestra.usa_file(genoma)
        finestra.controlla()
        assert f"Genoma di circa {progetto.basi_in_parole(genoma.stat().st_size)}." in scritte(finestra)
        assert "4.0" in progetto.basi_in_parole(genoma.stat().st_size)          # "4.007 basi" (o 4.009 con CRLF)
        finestra.aggiungi()
        return finestra.result()
    monkeypatch.setattr(pagina.FinestraOspite, "exec", esegui)
    c.aggiungi_ospite()
    assert c.ospite.currentData() == "olivo" and "aggiunto da te" in c.ospite.currentText()
    assert "Ospite aggiunto da te." in scritte(c)
    premi(f)
    cfg = f.contesto.progetto.leggi()
    assert cfg["hosts"] == ["olivo"] and cfg["app"]["ospite"] == "olivo"
    assert cfg["ospiti_personali"] == {"olivo": {"fasta": str(genoma), "basi": genoma.stat().st_size}}
    f.vai("campioni")
    assert c.ospite.currentData() == "olivo"
    scegli(c, "sus_scrofa")                                     # tornato al consigliato: ospiti_personali via
    premi(f)
    cfg = f.contesto.progetto.leggi()
    assert cfg["hosts"] == ["sus_scrofa"] and "ospiti_personali" not in cfg and "ospite" not in cfg["app"]


def test_finestra_fasta_non_valido(qtbot, f, tmp_path):
    w = pagina.FinestraOspite()
    qtbot.addWidget(w)
    w.nome.setText("olivo")
    w.scelta_file.pulsante.setChecked(True)
    (tmp_path / "x.fa").write_text("non e' un genoma\n")
    w.usa_file(tmp_path / "x.fa")
    w.controlla()
    assert "Non posso usare questo file." in scritte(w) and not w.pulsante_aggiungi.isEnabled()
