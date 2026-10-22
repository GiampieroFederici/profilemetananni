# -*- coding: utf-8 -*-
"""Revisione del 22/10, gruppo "GB-pagine": P40, P10, P19, P25, P42 (pagine Sicurezza, Motore, Risultati).
Gira con l'ambiente dell'app su Windows:  app\\.venv\\Scripts\\python -m pytest tests/test_revisione_gb.py"""
import json
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE))

from app import finestra, main, progetto  # noqa: E402

ATTESA = 60000
FINTO = RADICE / "installer" / "finto"


@pytest.fixture(autouse=True)
def finto(monkeypatch, tmp_path):
    monkeypatch.setenv("PMN_MOTORE", "finto")
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    stato = tmp_path / "tmp"                 # lucchetto di esegui del finto motore solo per questo test
    stato.mkdir()
    monkeypatch.setenv("TEMP", str(stato))
    monkeypatch.setenv("TMP", str(stato))


@pytest.fixture
def f(qtbot, qapp):
    main.prepara(qapp)
    w = finestra.Finestra(movimento=False)
    qtbot.addWidget(w)
    w.show()
    w.fuori.setCurrentIndex(1)
    return w


def progetto_con_campioni(tmp_path, nomi):
    """Progetto con risultati/risultati.json e un profilo MetaPhlAn (quello del finto) per ogni campione."""
    p = progetto.nuovo("prova", tmp_path)
    p.scrivi({"project_name": "prova", "motore": {"metaphlan_modo": "fette", "kraken_db": "completo"}})
    (p.risultati / "metaphlan").mkdir(parents=True)
    indice = json.loads((FINTO / "risultati.json").read_text(encoding="utf-8"))
    modello = indice["campioni"][0]
    indice["campioni"] = []
    for n in nomi:
        shutil.copy(FINTO / "SRR4875279_profile.txt", p.risultati / "metaphlan" / f"{n}_profile.txt")
        indice["campioni"].append(dict(modello, nome=n, file={"metaphlan": f"metaphlan/{n}_profile.txt"}))
    (p.risultati / "risultati.json").write_text(json.dumps(indice), encoding="utf-8")
    return p


def scrivi_prodotto(sic):
    for nome, valore in dict(temperatura="5", giorni="21", sale="3,5", ph="6,0").items():
        getattr(sic, nome).setText(valore)


# ---------------- P40: Sicurezza con più campioni ----------------
def test_p40_sicurezza_con_piu_campioni_sceglie_il_campione(f, qtbot, tmp_path):
    """Contratto §5.4: con più campioni la richiesta porta "campione"; prima il motore rifiutava sempre
    (INGRESSO_NON_VALIDO) e nella pagina non c'era nulla da correggere."""
    f.contesto.progetto = progetto_con_campioni(tmp_path, ["A", "B"])
    f.vai("sicurezza")
    sic = f.pagine["sicurezza"]
    assert not sic.campione.isHidden()
    assert [sic.campione.itemText(i) for i in range(sic.campione.count())] == ["A", "B"]
    sic.campione.setCurrentIndex(1)
    scrivi_prodotto(sic)
    assert sic.richiesta()["campione"] == "B"
    sic.calcola.click()                                    # finto motore: calcolo vero di motore/sicurezza.py
    qtbot.waitUntil(lambda: not sic.client.in_corso() and sic.calcola.isEnabled(), timeout=ATTESA)
    assert sic.risultato is not None and sic.risultato["campione"] == "B"


def test_p40_un_solo_campione_richiesta_come_prima(f, tmp_path):
    f.contesto.progetto = progetto_con_campioni(tmp_path, ["A"])
    f.vai("sicurezza")
    sic = f.pagine["sicurezza"]
    assert sic.campione.isHidden()
    scrivi_prodotto(sic)
    assert "campione" not in sic.richiesta()


# ---------------- P10: Motore fermo durante un'analisi ----------------
def test_p10_motore_non_si_controlla_durante_un_analisi(qtbot, monkeypatch):
    """verifica e installa fanno girare MetaPhlAn sul mini-campione: durante esegui sarebbe un secondo MetaPhlAn
    (oltre i 16 GB). Durante l'analisi la pagina non li lancia; finita l'analisi tornano."""
    from app.motore import MotoreClient
    from app.pagine.base import Contesto
    from app.pagine.motore import PaginaMotore
    lanciati = []
    monkeypatch.setattr(MotoreClient, "avvia", lambda self, comando, *a, **k: lanciati.append(comando))
    monkeypatch.setattr(MotoreClient, "in_corso", lambda self: False)
    c = Contesto()
    c.info = {"database": [], "programmi": {}, "spazio_libero_gb": 100, "ram_gb": 16, "processori": 8,
              "finto": True}
    p = PaginaMotore(c)
    qtbot.addWidget(p)
    c.progetto_in_analisi = "progetto_X"
    p.mostrata()
    assert not p.principale_attivo
    assert all(funzione not in (p.verifica, p.installa) for _testo, funzione in p.secondari)
    p.azione_principale()
    p.verifica()
    p.installa()
    assert lanciati == []
    c.progetto_in_analisi = None                          # analisi finita: si controlla di nuovo
    p.mostrata()
    assert p.principale_attivo
    p.verifica()
    assert lanciati == ["verifica"]
