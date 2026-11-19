# -*- coding: utf-8 -*-
"""P6 (prova su un PC con Ubuntu, 12/11/2026): pagina Motore dopo una prova rossa. Il titolo diceva "ROSSO: ROSSO:",
il pallino in alto restava verde con "Motore pronto", la scheda diceva "Installato e pronto" e la prima azione
proposta era "Installa o completa" (che reinstalla) anche con programmi e database tutti al loro posto.
Gli eventi sono quelli del motore vero (motore/pmn_motore.py, verifica); il resto è il finto motore.
  app\\.venv\\Scripts\\python -m pytest tests/test_ux_ubuntu_app.py"""
import pytest

pytest.importorskip("pytestqt")
from PySide6.QtCore import QUrl  # noqa: E402

from test_app_s5b import ambiente, f, premi, scritte  # noqa: E402,F401  (fixtures and helpers of S5b)

from app.pagine import motore as pagina_motore  # noqa: E402

REGISTRO = "/home/persona/.pmn/log/pmn_2026-11-12T23-10-33_verifica.log"
ROSSA = {"tipo": "errore", "codice": "VERIFICA_ROSSA", "passo": "verifica",
         "messaggio": "ROSSO: la prova del motore non ha dato il risultato atteso.",
         "cosa_fare": f"Manda a noi il file {REGISTRO}."}


def prova_rossa(qtbot, f):  # noqa: F811
    """Il motore vero risponde ROSSO a "Controlla il motore": gli stessi eventi, nello stesso ordine."""
    m = f.pagine["motore"]
    qtbot.waitUntil(lambda: not m.client_info.in_corso(), timeout=30000)
    m.client.comando = "verifica"
    m._evento({"tipo": "inizio", "comando": "verifica", "corsa": "2026-11-12T23-10-33", "log": REGISTRO})
    m._evento(ROSSA)
    m._finito(2, {"tipo": "fine", "esito": "errore", "messaggio": "Problema durante la verifica del motore.",
                  "risultato": {"codice": "VERIFICA_ROSSA", "passo": "verifica"}})
    qtbot.waitUntil(lambda: not m.client_info.in_corso(), timeout=30000)      # info di nuovo, come dopo ogni lavoro
    return m


def test_p6_un_solo_rosso_e_tre_segnali_coerenti(qtbot, f):  # noqa: F811
    f.vai("motore")
    assert f.pagine["motore"].stato_titolo.text().startswith("Installato e pronto")
    m = prova_rossa(qtbot, f)
    testo = scritte(m)
    assert "ROSSO: la prova del motore non ha dato il risultato atteso." in testo and "ROSSO: ROSSO" not in testo
    # il pallino in alto e la scheda dicono la stessa cosa del titolo
    assert f.pallino.property("stato") == "rosso" and f.stato_motore.text() == "Motore da controllare"
    assert m.stato_titolo.text() == "Installato, ma l'ultimo controllo non è riuscito"
    assert pagina_motore.COLORI["rosso"] in m.pallino.styleSheet()
    # un controllo verde rimette tutto a posto
    premi(f)
    qtbot.waitUntil(lambda: "VERDE: il motore funziona." in scritte(m), timeout=30000)
    qtbot.waitUntil(lambda: not m.client_info.in_corso(), timeout=30000)
    assert f.pallino.property("stato") == "" and m.stato_titolo.text().startswith("Installato e pronto")
    assert pagina_motore.COLORI["verde"] in m.pallino.styleSheet()


def test_p6_tutto_installato_la_prima_azione_e_mandare_il_registro(qtbot, f, monkeypatch):  # noqa: F811
    f.vai("motore")
    m = prova_rossa(qtbot, f)
    assert not m.da_installare and f.principale.text() == "Controlla il motore"
    assert "manda a noi il file" in f.aiuto.text() and "nstalla o completa" not in f.aiuto.text()
    assert [b.text() for b in f.secondari] == ["Apri il registro", "Installa o completa"]
    aperti = []
    monkeypatch.setattr(pagina_motore.QDesktopServices, "openUrl", lambda u: aperti.append(u) or True)
    f.secondari[0].click()
    assert aperti == [QUrl.fromLocalFile(REGISTRO)]
    m.percorso_log = ""                                      # senza il percorso del registro il pulsante non c'è
    m._barra_azioni()
    assert [b.text() for b in f.secondari] == ["Installa o completa"]


def test_p6_se_manca_qualcosa_resta_installa_o_completa(qtbot, f):  # noqa: F811
    f.vai("motore")
    m = f.pagine["motore"]
    qtbot.waitUntil(lambda: not m.client_info.in_corso(), timeout=30000)
    info = f.contesto.info
    f.contesto.info = dict(info, database=[dict(info["database"][0], installato=False)] + info["database"][1:])
    m.errore_corsa = ROSSA
    m._esito("verifica", {"esito": "errore"})
    m._barra_azioni()
    assert m.da_installare and f.principale.text() == "Installa o completa"
