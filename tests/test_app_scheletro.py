# -*- coding: utf-8 -*-
"""Scheletro dell'app (S5a) contro il finto motore: MotoreClient, finestra, navigazione, progetto.
Gira con l'ambiente dell'app su Windows:  app\\.venv\\Scripts\\python -m pytest tests/test_app_scheletro.py"""
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QLabel, QPushButton  # noqa: E402

import contratto  # noqa: E402
from app import finestra, main, motore, progetto  # noqa: E402
from app.motore import MotoreClient  # noqa: E402
from app.pagine.base import Pagina, numero  # noqa: E402


@pytest.fixture(autouse=True)
def finto(monkeypatch):
    monkeypatch.setenv("PMN_MOTORE", "finto")
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")


def corsa(qtbot, comando, *argomenti, dopo_inizio=None):
    c = MotoreClient()
    eventi = []
    c.evento.connect(eventi.append)
    if dopo_inizio:
        c.evento.connect(lambda e: e["tipo"] == "avanzamento" and dopo_inizio(c))
    with qtbot.waitSignal(c.finito, timeout=60000) as s:
        c.avvia(comando, *argomenti)
    return c, eventi, s.args[0]


def righe(eventi):
    return "\n".join(json.dumps(e, ensure_ascii=False) for e in eventi)


# ---------------- MotoreClient ----------------
def test_info_arriva_dal_finto_motore(qtbot):
    c, eventi, uscita = corsa(qtbot, "info")
    ev = contratto.controlla(righe(eventi), uscita, "info")      # gli eventi passano intatti
    assert ev[-1]["risultato"]["ram_gb"] == 15.6
    assert c.corsa == ev[0]["corsa"]


def test_errore_con_cosa_fare_e_codice_di_uscita(qtbot, monkeypatch):
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0 --scenario DB_MANCANTE")
    _, eventi, uscita = corsa(qtbot, "verifica")
    contratto.controlla(righe(eventi), uscita, "verifica")
    errore = [e for e in eventi if e["tipo"] == "errore"][0]
    assert uscita == 2 and errore["codice"] == "DB_MANCANTE"
    assert errore["cosa_fare"] == "Apri la pagina Motore e premi Installa o completa."


def test_annulla_ferma_la_corsa(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 60")      # download: 4 s, c'è tempo per annullare
    (tmp_path / "temp").mkdir()                                    # lucchetto di esegui solo per questo test
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("TMP", str(tmp_path / "temp"))
    config = tmp_path / "config.yaml"
    config.write_text("project_name: prova\n", encoding="utf-8")
    chiesto = []
    _, eventi, uscita = corsa(qtbot, "esegui", "--progetto", str(config),
                              dopo_inizio=lambda c: chiesto or chiesto.append(c.annulla()))
    contratto.controlla(righe(eventi), uscita, "esegui")
    assert chiesto == [True] and uscita == 3 and eventi[-1]["esito"] == "annullata"


def test_motore_che_non_parte(qtbot, monkeypatch):
    monkeypatch.setattr(motore, "comando_motore", lambda: (["programma_che_non_esiste_pmn.exe"], []))
    _, eventi, uscita = corsa(qtbot, "info")
    assert uscita == 4
    assert [e["tipo"] for e in eventi] == ["errore", "fine"]
    assert eventi[0]["codice"] == "MOTORE_NON_AVVIATO" and eventi[0]["cosa_fare"]


def test_motore_che_si_chiude_senza_inizio(qtbot, monkeypatch):
    """Come wsl.exe quando la WSL pmn non c'è: stampa testo e si chiude (R8: porta alla pagina Motore)."""
    monkeypatch.setattr(motore, "comando_motore", lambda: ([sys.executable, "-c", "print('non json')"], []))
    c, eventi, uscita = corsa(qtbot, "info")
    assert uscita == 4 and eventi[-1]["tipo"] == "fine" and eventi[0]["codice"] == "MOTORE_NON_AVVIATO"
    assert "pagina Motore" in eventi[0]["cosa_fare"]
    assert any("non json" in d for d in c.diagnostica)          # resta nella diagnostica, mai all'utente (R2)


def test_motore_che_si_chiude_dopo_inizio_senza_fine(qtbot, monkeypatch):
    codice = ("import json\nprint(json.dumps({'tipo':'inizio','ora':'2026-10-16T10:00:00+02:00','messaggio':'via',"
              "'comando':'info','corsa':'c1','log':'x.log'}))\n")
    monkeypatch.setattr(motore, "comando_motore", lambda: ([sys.executable, "-c", codice], []))
    _, eventi, uscita = corsa(qtbot, "info")
    assert uscita == 4 and [e["tipo"] for e in eventi] == ["inizio", "errore", "fine"]
    assert eventi[1]["codice"] == "ERRORE_INTERNO"


def test_righe_spezzate_e_accenti(qtbot, monkeypatch):
    codice = ("import json,sys,time\n"
              "r=json.dumps({'tipo':'fine','ora':'2026-10-16T10:00:00+02:00','esito':'ok',"
              "'messaggio':'Già fatto: è così','risultato':{}},ensure_ascii=False).encode()+b'\\n'\n"
              "sys.stdout.buffer.write(r[:15]);sys.stdout.flush();time.sleep(0.3)\n"
              "sys.stdout.buffer.write(r[15:]);sys.stdout.flush()\n")
    monkeypatch.setattr(motore, "comando_motore", lambda: ([sys.executable, "-c", codice], []))
    _, eventi, uscita = corsa(qtbot, "info")
    assert uscita == 0 and len(eventi) == 1 and eventi[0]["messaggio"] == "Già fatto: è così"


@pytest.mark.skipif(sys.platform != "win32", reason="percorsi di Windows")
def test_percorso_per_il_motore_vero(monkeypatch):
    monkeypatch.delenv("PMN_MOTORE")
    assert motore.percorso_per_motore(r"C:\Users\Mario Rossi\Documenti\p\config.yaml") == \
        "/mnt/c/Users/Mario Rossi/Documenti/p/config.yaml"
    assert motore.comando_motore()[0][:3] == ["wsl.exe", "-d", "pmn"]


# ---------------- finestra ----------------
def pagine_finte():
    """Pagine finte al posto delle vere (S5b, S6): il test prova lo scheletro, non il contenuto delle pagine."""
    catena = {"home": "campioni", "campioni": "scelte", "scelte": "esecuzione", "esecuzione": "risultati",
              "risultati": "sicurezza", "sicurezza": "risultati", "motore": None, "crediti": "home"}
    return {k: type(f"Finta_{k}", (Pagina,), {"titolo": k, "testo_principale": f"Avanti da {k}", "destinazione": d})
            for k, d in catena.items()}


def test_finestra_avvio_e_navigazione(qtbot, qapp, monkeypatch):
    main.prepara(qapp)
    assert "Atkinson Hyperlegible" in QFontDatabase.families()
    monkeypatch.setattr(finestra, "AVVIO_MIN_MS", 0)
    monkeypatch.setattr(finestra, "PAGINE", pagine_finte())
    f = finestra.Finestra(movimento=False)
    qtbot.addWidget(f)
    f.show()
    f.avvia()
    qtbot.waitUntil(lambda: f.attuale == "home", timeout=30000)
    assert f.contesto.info["ram_gb"] == 15.6 and f.stato_motore.text() == "Motore di prova"

    visti = ["home"]
    for _ in range(6):                     # solo il pulsante principale, come l'utente (R4)
        principali = [b for b in f.findChildren(QPushButton, "principale") if b.isVisible()]
        assert len(principali) == 1                                   # R1
        assert all(b.isVisible() for b, _, _ in f.passi.values())     # R3
        assert principali[0].text() == f"Avanti da {f.attuale}"       # la barra segue la pagina
        principali[0].click()
        visti.append(f.attuale)
    assert visti == ["home", "campioni", "scelte", "esecuzione", "risultati", "sicurezza", "risultati"]

    pagina = f.pagine["motore"]                                       # barra aggiornata dalla pagina
    f.vai("motore")
    pagina.principale_attivo, pagina.aiuto, pagina.aiuto_livello = False, "Attendi", "avviso"
    pagina.secondari = [("Installa", lambda: None)]
    pagina.azioni_cambiate.emit()
    assert not f.principale.isEnabled() and f.aiuto.text() == "Attendi"
    assert [b.text() for b in f.secondari] == ["Installa"]
    f.vai("crediti")
    assert f.secondari == [] and f.principale.isEnabled()
    qapp.processEvents()                   # L1a: senza il giro "cancella più tardi" il vecchio pulsante restava
    assert [b.text() for b in f.zona_barra.findChildren(QPushButton) if b.isVisible()] == [f.principale.text()]
    f.principale.click()
    assert f.attuale == "home"


def finestra_finta(qtbot):
    w = finestra.Finestra(movimento=False)
    qtbot.addWidget(w)
    w.fuori.setCurrentIndex(1)
    return w


def segni(f):
    return {c: b.text().split()[0] for c, (b, _, _) in f.passi.items()}


def test_percorso_segue_lo_stato_del_progetto(qtbot, monkeypatch, tmp_path):
    """✓ dai passi fatti nel progetto, non dalla pagina attuale: in Sicurezza i passi 1-4 restano segnati."""
    monkeypatch.setattr(finestra, "PAGINE", pagine_finte())
    f = finestra_finta(qtbot)
    f.vai("sicurezza")
    assert segni(f) == {"campioni": "1", "scelte": "2", "esecuzione": "3", "risultati": "4", "sicurezza": "+"}
    p = progetto.nuovo("salame", tmp_path)
    p.scrivi({"project_name": "salame", "app": {"prodotto": "maiale"}})
    f.contesto.progetto = p
    f.vai("scelte")
    assert segni(f)["campioni"] == "✓" and segni(f)["scelte"] == "2"
    assert f.passi["scelte"][0].property("stato") == "attivo"
    p.scrivi({"project_name": "salame", "app": {"prodotto": "maiale", "scelte": True}})
    (p.risultati).mkdir()
    (p.risultati / "risultati.json").write_text("{}", encoding="utf-8")
    f.pagine["scelte"].azioni_cambiate.emit()          # senza cambiare pagina (per esempio analisi finita)
    assert segni(f) == {"campioni": "✓", "scelte": "✓", "esecuzione": "✓", "risultati": "✓", "sicurezza": "+"}
    f.vai("sicurezza")
    assert [segni(f)[c] for c in ("campioni", "scelte", "esecuzione", "risultati")] == ["✓"] * 4
    assert f.passi["campioni"][0].accessibleDescription() == "fatto"
    assert f.passi["sicurezza"][0].accessibleDescription() == "passo attuale"


def test_pallino_della_testata_segue_info(qtbot, monkeypatch):
    """Dopo `installa` la pagina Motore cambia contesto.info: la testata si aggiorna senza riavviare."""
    monkeypatch.setattr(finestra, "PAGINE", pagine_finte())
    f = finestra_finta(qtbot)
    f.contesto.info = None
    f.pagine["motore"].info_cambiata.emit()
    assert f.pallino.property("stato") == "rosso" and f.stato_motore.text() == "Motore da controllare"
    f.contesto.info = {"finto": False}
    f.pagine["motore"].info_cambiata.emit()
    assert f.pallino.property("stato") == "" and f.stato_motore.text() == "Motore pronto"


def test_principale_pericolo(qtbot, monkeypatch):
    monkeypatch.setattr(finestra, "PAGINE", pagine_finte())
    f = finestra_finta(qtbot)
    f.vai("esecuzione")
    assert f.principale.property("pericolo") is False
    f.pagine["esecuzione"].principale_pericolo = True
    f.pagine["esecuzione"].azioni_cambiate.emit()
    assert f.principale.property("pericolo") is True
    f.vai("risultati")
    assert f.principale.property("pericolo") is False


def test_altro_progetto_durante_un_analisi(qtbot, monkeypatch, tmp_path):
    """Mentre un'analisi gira si apre solo il suo progetto; gli altri no, e si spiega perché."""
    monkeypatch.setattr(progetto, "cartella_progetti", lambda: tmp_path)
    f = finestra.Finestra(movimento=False)
    qtbot.addWidget(f)
    f.fuori.setCurrentIndex(1)
    corsa, altro = progetto.nuovo("corsa", tmp_path), progetto.nuovo("altro", tmp_path)
    for p in (corsa, altro):
        p.scrivi({"project_name": p.nome})
    f.contesto.progetto = f.contesto.progetto_in_analisi = corsa
    home = f.pagine["home"]
    f.vai("home")
    scritte = [e.text() for e in home.findChildren(QLabel)]
    assert "Un'analisi è in corso sul progetto corsa." in scritte and "Analisi in corso" in scritte
    home.apri(progetto.Progetto(altro.cartella))
    assert f.attuale == "home" and f.contesto.progetto is corsa and home.errore_elenco.count() == 1
    home.nome.setText("nuovo")
    home.azione_principale()
    assert f.attuale == "home" and not (tmp_path / "nuovo").exists() and home.errore.count() == 1
    home.apri(progetto.Progetto(corsa.cartella))       # lo stesso progetto: si torna a seguire la corsa
    assert f.attuale == "esecuzione" and f.contesto.progetto is corsa
    f.contesto.progetto_in_analisi = None                # analisi finita: si apre tutto
    home.apri(progetto.Progetto(altro.cartella))
    assert f.contesto.progetto.nome == "altro"


def test_pagine_vere_si_creano(qtbot):
    """Le pagine vere di S5b e S6 nascono senza errori dentro la finestra (il contenuto lo provano i loro test)."""
    f = finestra.Finestra(movimento=False)
    qtbot.addWidget(f)
    assert set(f.pagine) == {"home", "campioni", "scelte", "esecuzione", "risultati", "sicurezza", "motore", "crediti"}


def test_avatar_respira_e_si_ferma(qtbot):
    f = finestra.Finestra(movimento=True)
    qtbot.addWidget(f)
    f.respira(True)
    assert f.emblema.graphicsEffect() is not None
    f.respira(False)
    assert f.emblema.graphicsEffect() is None
    f2 = finestra.Finestra(movimento=False)            # "riduci movimento": non si accende
    qtbot.addWidget(f2)
    f2.respira(True)
    assert f2.emblema.graphicsEffect() is None


def test_riduci_movimento_segue_windows(qtbot, monkeypatch):
    """R15: con "Effetti animazione" spento in Windows l'avatar non saltella e non respira; vale subito,
    anche se lo si cambia ad app aperta."""
    spento = [True]
    monkeypatch.setattr(finestra, "movimento_ridotto", lambda: spento[0])
    monkeypatch.setattr(finestra, "AVVIO_MIN_MS", 0)
    f = finestra.Finestra()
    qtbot.addWidget(f)
    f.avvia()
    assert not hasattr(f, "_salto")                     # niente salto all'avvio
    f.respira(True)
    assert f.emblema.graphicsEffect() is None
    spento[0] = False                                   # acceso ad app aperta: si muove di nuovo
    f.respira(True)
    assert f.emblema.graphicsEffect() is not None
    f.respira(False)
    qtbot.waitUntil(lambda: not f.client_info.in_corso(), timeout=30000)


def test_riduci_movimento_spegne_le_animazioni_di_qt(qapp, monkeypatch):
    effetti = (Qt.UI_AnimateMenu, Qt.UI_FadeMenu, Qt.UI_AnimateCombo, Qt.UI_AnimateTooltip, Qt.UI_FadeTooltip,
               Qt.UI_AnimateToolBox)
    prima = {e: qapp.isEffectEnabled(e) for e in effetti}
    try:
        monkeypatch.setattr(main, "movimento_ridotto", lambda: True)
        main.prepara(qapp)
        assert not any(qapp.isEffectEnabled(e) for e in effetti)
    finally:
        for e, acceso in prima.items():
            qapp.setEffectEnabled(e, acceso)


@pytest.mark.skipif(sys.platform != "win32", reason="impostazione di Windows")
def test_impostazione_di_windows_si_legge():
    assert finestra.movimento_ridotto() in (True, False)


# ---------------- progetto e formati ----------------
def test_progetto_scrive_e_legge(tmp_path):
    p = progetto.nuovo("salame_2026", tmp_path)
    dati = {"project_name": "salame_2026", "hosts": ["sus_scrofa"], "nota": "perché sì",
            "motore": {"metaphlan_modo": "fette", "kraken_db": "completo", "virus": False, "processori": 8}}
    p.scrivi(dati)
    assert p.leggi() == dati
    assert [q.nome for q in progetto.elenco(tmp_path)] == ["salame_2026"]
    assert list(tmp_path.glob("*/*.tmp")) == []
    for cattivo in ("../fuori", "", "con spazio", ".nascosto", "a" * 61):
        with pytest.raises(ValueError):
            progetto.nuovo(cattivo, tmp_path)
    with pytest.raises(FileExistsError):
        progetto.nuovo("salame_2026", tmp_path)


def test_numeri_all_italiana():
    assert numero(15.6) == "15,6"
    assert numero(643, 0) == "643"
    assert numero(1234567.891, 2) == "1.234.567,89"
