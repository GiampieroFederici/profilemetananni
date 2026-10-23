# -*- coding: utf-8 -*-
"""Lingua IT/EN (sessione del 18/10/2026): con l'italiano, app, messaggi del motore e referto restano IDENTICI.

La fotografia tests/dati/lingua_it.json è stata fatta sul codice di f567f8e, prima della lingua
(python tests/lingua_foto.py --scrivi): qui si rifà e si confronta, caso per caso.
Gira con l'ambiente dell'app su Windows:  app\\.venv\\Scripts\\python -m pytest tests/test_lingua.py"""
import difflib
import re
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lingua_foto  # noqa: E402


def differenze(attesa, adesso):
    out = []
    for caso in sorted(set(attesa) | set(adesso)):
        if attesa.get(caso) != adesso.get(caso):
            out.append(f"--- {caso}")
            out += list(difflib.unified_diff(attesa.get(caso, []), adesso.get(caso, []), lineterm="", n=1))[2:40]
    return "\n".join(out)


def test_italiano_identico_a_prima(qapp):
    attesa = json.loads(lingua_foto.FOTO_IT.read_text(encoding="utf-8"))
    adesso = lingua_foto.foto()
    assert adesso == attesa, differenze(attesa, adesso)


# ---------------- inglese ----------------
from app import finestra, lingua, progetto  # noqa: E402
from app.pagine import sicurezza  # noqa: E402
from app.pagine.base import numero  # noqa: E402
import lingua_chiavi  # noqa: E402


@pytest.mark.parametrize("nome", list(lingua_chiavi.CATALOGHI))
def test_ogni_frase_ha_la_traduzione(nome):
    """Ogni testo dentro _() o N_() ha la sua traduzione, con gli stessi {campi}; nel catalogo nulla di avanzato."""
    chiavi, catalogo = lingua_chiavi.chiavi(nome), lingua_chiavi.catalogo(nome)
    assert {t: dove for t, dove in chiavi.items() if t not in catalogo} == {}
    assert [t for t in catalogo if t not in chiavi] == []
    assert [(it, en) for it, en in catalogo.items()
            if lingua_chiavi.segnaposto(it) != lingua_chiavi.segnaposto(en) or not en.strip()] == []


def test_inglese_senza_frasi_italiane(qapp):
    """App, eventi del motore (finto e vero) e referto in inglese: nessuna parola italiana dove l'utente legge."""
    restano = [(caso, lingua_foto.italiane(x), x[:160]) for caso, testi in lingua_foto.foto("en").items()
               for t in testi for x in lingua_foto.da_mostrare(t) if lingua_foto.italiane(x)]
    assert restano == []
    assert lingua.attuale() == "it"                      # la fotografia rimette l'italiano


@pytest.fixture
def f(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("PMN_MOTORE", "finto")
    monkeypatch.setenv("PMN_FINTO_OPZIONI", "--velocita 0")
    (tmp_path / "temp").mkdir()
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    monkeypatch.setenv("TMP", str(tmp_path / "temp"))
    monkeypatch.setattr(progetto, "cartella_progetti", lambda: tmp_path / "progetti")
    monkeypatch.setattr(finestra, "AVVIO_MIN_MS", 0)
    salvate = []
    monkeypatch.setattr(lingua, "salva", salvate.append)   # niente registro di Windows nei test
    w = finestra.Finestra(movimento=False)
    w.salvate = salvate
    qtbot.addWidget(w)
    w.show()
    w.avvia()
    qtbot.waitUntil(lambda: w.attuale == "home", timeout=30000)
    yield w
    lingua.imposta("it")


def test_cambio_lingua_dal_vivo(f, qtbot):
    """L'interruttore in testata rifà le pagine nella nuova lingua e resta sulla stessa pagina; il motore riceve
    --lingua en solo con l'inglese; la scelta si salva; con l'italiano di nuovo tutto come prima."""
    f.vai("scelte")
    qtbot.waitUntil(lambda: not f.pagine["scelte"].client.in_corso(), timeout=30000)
    assert f.pulsante_lingua.text() == "English" and lingua.per_motore() == []
    f.pulsante_lingua.click()
    assert lingua.attuale() == "en" and f.salvate == ["en"] and lingua.per_motore() == ["--lingua", "en"]
    assert f.attuale == "scelte" and f.pulsante_lingua.text() == "Italiano"
    assert [b.text() for b in f.zona_testata.findChildren(finestra.QPushButton)][-4:-1] == [
        "My projects", "Engine", "How to cite"]
    qtbot.waitUntil(lambda: not f.occupato(), timeout=30000)        # info di nuovo, poi la stima, in inglese
    f.vai("home")
    assert f.principale.text() == "New project"
    assert "Prova" not in " ".join(b.text() for b in f.pagine["home"].findChildren(finestra.QPushButton))
    assert f.contesto.info["prodotti"][0]["frase"] == "I will remove the pig DNA and the human DNA."
    f.pulsante_lingua.click()
    assert lingua.attuale() == "it" and f.principale.text() == "Nuovo progetto" and f.salvate == ["en", "it"]


def test_lingua_ferma_mentre_il_motore_lavora(f):
    f.contesto.progetto_in_analisi = object()
    assert f.cambia_lingua("en") is False
    assert lingua.attuale() == "it" and f.salvate == []
    assert f.aiuto.text() == "Puoi cambiare lingua quando il motore ha finito il lavoro in corso."
    f.contesto.progetto_in_analisi = None


def test_numeri_nelle_due_lingue():
    assert (numero(1234.5, 1), sicurezza.leggi_numero("1.000.000"), sicurezza.leggi_numero("3,5")) == \
        ("1.234,5", 1000000.0, 3.5)
    lingua.imposta("en")
    try:
        assert (numero(1234.5, 1), sicurezza.due_cifre(30023), sicurezza.due_cifre(16.95)) == ("1,234.5", "30,000", "17")
        assert [sicurezza.leggi_numero(x) for x in ("3.5", "3,5", "1,000,000", "1,234.5", "")] == \
            [3.5, 3.5, 1000000.0, 1234.5, None]
    finally:
        lingua.imposta("it")


def _usi(funzione):
    """(chiama _(), assegna _) nel corpo di una funzione, senza entrare in funzioni, lambda e comprensioni interne
    (hanno uno spazio dei nomi loro)."""
    import ast
    chiama = assegna = False
    da_vedere = list(ast.iter_child_nodes(funzione))
    while da_vedere:
        n = da_vedere.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ListComp, ast.SetComp,
                          ast.DictComp, ast.GeneratorExp, ast.ClassDef)):
            continue
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_":
            chiama = True
        if isinstance(n, ast.Name) and n.id == "_" and isinstance(n.ctx, ast.Store):
            assegna = True
        da_vedere += list(ast.iter_child_nodes(n))
    return chiama, assegna


def test_nessuna_funzione_usa_il_trattino_basso_come_variabile():
    """Una funzione che traduce con _() non può usare _ come variabile di scarto ("k, _, v = ..."): _ diventerebbe una
    stringa e _() darebbe TypeError (successo il 18/10 in pmn_motore._risultati, trovato dalla suite del motore)."""
    import ast
    sbagliate = []
    for _nome, (_cat, file) in lingua_chiavi.CATALOGHI.items():
        for f in file:
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and all(_usi(n)):
                    sbagliate.append(f"{f.name}:{n.lineno} {n.name}")
    assert sbagliate == []


def test_inglese_taxa_mai_microbes():
    """D128 anche in inglese (R1, 18/10): nei testi tradotti "taxa"/"taxon", mai "microbe"/"microbes"
    (le citazioni con Microbiol, Microbiome, microbiology restano)."""
    parola = re.compile(r"\bmicrobes?\b", re.I)
    for nome in lingua_chiavi.CATALOGHI:
        assert [en for en in lingua_chiavi.catalogo(nome).values() if parola.search(en)] == []
