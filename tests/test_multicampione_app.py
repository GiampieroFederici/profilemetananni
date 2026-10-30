# -*- coding: utf-8 -*-
"""R11 + R18 nell'app: i dati dei campioni (gruppo, soggetto, tempo, covariata) si scrivono in una tabella della pagina
Risultati, l'app salva metadati.tsv e rifà solo il referto (comando `referto`, mai l'analisi delle read).
Gira con l'ambiente dell'app su Windows (finto motore):  app\\.venv\\Scripts\\python -m pytest tests/test_multicampione_app.py"""
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QPushButton, QTableWidget  # noqa: E402

from app import progetto  # noqa: E402
from app.pagine import risultati as pagina  # noqa: E402
from test_app_s6 import f, finto, riquadri, scritte  # noqa: E402,F401  (fixture del finto motore e della finestra)
from test_multicampione import progetto_referto  # noqa: E402


def apri_risultati(f, tmp_path, metadati=False):
    p = progetto.Progetto(progetto_referto(tmp_path, metadati=metadati))
    f.contesto.progetto = p
    f.vai("risultati")
    return p, f.pagine["risultati"]


def pulsante(ris, testo):
    return [b for b in ris.findChildren(QPushButton) if b.text() == testo][0]


def test_tabella_salva_e_rifa_solo_il_referto(f, qtbot, tmp_path):
    p, ris = apri_risultati(f, tmp_path)
    t = ris.findChild(QTableWidget)
    assert [t.item(i, 0).text() for i in range(t.rowCount())] == [f"S{i}" for i in range(8)]   # già riempita
    assert [t.horizontalHeaderItem(j).text() for j in range(5)] == ["Campione", "Gruppo", "Soggetto", "Tempo",
                                                                     "Covariata"]
    assert "scrivi qui sotto il gruppo" in scritte(ris.contenuto)
    for i in range(8):
        t.item(i, 1).setText("A" if i < 4 else "B")
    t.item(0, 4).setText("lotto\t1")                          # una tabulazione non rompe il file
    comandi = []
    ris.client.avvia = (lambda vero: lambda *a: (comandi.append(a), vero(*a)))(ris.client.avvia)
    pulsante(ris, "Salva e aggiorna l'analisi").click()
    assert comandi[0][0] == "referto"                          # mai esegui: niente analisi delle read
    qtbot.waitUntil(lambda: not ris.client.in_corso(), timeout=120000)
    righe = (p.cartella / "metadati.tsv").read_text(encoding="utf-8").splitlines()
    assert righe[0] == "sample_id\tgroup\tsubject\ttimepoint\tcovariate"
    assert righe[1] == "S0\tA\t\t\tlotto 1" and righe[8] == "S7\tB\t\t\t"
    rie = json.loads((p.risultati / "multicampione" / "riepilogo.json").read_text(encoding="utf-8"))
    assert rie["metadati"]["usati"] and rie["metadati"]["problemi"] == []
    qtbot.waitUntil(lambda: "Confronti fra i gruppi scritti qui sotto" in scritte(ris.contenuto), timeout=10000)
    t = ris.findChild(QTableWidget)
    assert t.item(5, 1).text() == "B"                          # la tabella si riapre con i valori salvati


def test_errori_in_parole_semplici(f, qtbot, tmp_path):
    p, ris = apri_risultati(f, tmp_path)
    t = ris.findChild(QTableWidget)
    for i in range(8):
        t.item(i, 1).setText("" if i == 0 else "A" if i < 6 else "B")   # S0 senza gruppo, B con 2 campioni
    pulsante(ris, "Salva e aggiorna l'analisi").click()
    qtbot.waitUntil(lambda: not ris.client.in_corso(), timeout=120000)
    qtbot.waitUntil(lambda: "non hanno il gruppo" in "\n".join(scritte(r) for r in riquadri(ris, "avviso")),
                    timeout=10000)
    avvisi = "\n".join(scritte(r) for r in riquadri(ris, "avviso"))
    assert "S0. Scrivi il loro gruppo" in avvisi and "B (2). Aggiungi campioni" in avvisi


def test_file_aperto_in_excel_e_colonne_di_excel_tenute(f, qtbot, tmp_path, monkeypatch):
    p, ris = apri_risultati(f, tmp_path)
    (p.cartella / "metadati.tsv").write_text("sample_id\tgroup\tlotto\nS1\tX\tL7\n", encoding="utf-8")
    f.vai("home")
    f.vai("risultati")
    ris = f.pagine["risultati"]
    assert ris.findChild(QTableWidget).item(1, 1).text() == "X"           # letto dal file scritto con Excel
    vero = pagina.scrivi_metadati_app
    monkeypatch.setattr(pagina, "scrivi_metadati_app", lambda *a: (_ for _ in ()).throw(PermissionError("aperto")))
    pulsante(ris, "Salva e aggiorna l'analisi").click()
    errori = "\n".join(scritte(r) for r in riquadri(ris, "errore"))
    assert "aperto in un altro programma" in errori and not ris.client.in_corso()
    monkeypatch.setattr(pagina, "scrivi_metadati_app", vero)   # non undo(): toglierebbe anche il finto motore
    pulsante(ris, "Salva e aggiorna l'analisi").click()
    qtbot.waitUntil(lambda: not ris.client.in_corso(), timeout=120000)
    righe = (p.cartella / "metadati.tsv").read_text(encoding="utf-8").splitlines()
    assert righe[0] == "sample_id\tgroup\tsubject\ttimepoint\tcovariate\tlotto" and righe[2] == "S1\tX\t\t\t\tL7"


def test_un_solo_campione_niente_riquadro(f, qtbot, tmp_path):
    p, ris = apri_risultati(f, tmp_path)
    dati = json.loads((p.risultati / "risultati.json").read_text(encoding="utf-8"))
    dati["campioni"] = dati["campioni"][:1]
    (p.risultati / "risultati.json").write_text(json.dumps(dati), encoding="utf-8")
    f.vai("home")
    f.vai("risultati")
    assert f.pagine["risultati"].findChild(QTableWidget) is None
