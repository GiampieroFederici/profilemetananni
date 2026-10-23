# -*- coding: utf-8 -*-
"""Server MCP (D130, R1 18/10/2026; criteri CM1-CM6 del diario R1), provato con un client MCP locale dell'SDK ufficiale
sul finto motore. Gira con l'ambiente del server:  pmn_mcp\\.venv\\Scripts\\python -m pytest tests/test_mcp.py"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")
import anyio  # noqa: E402
from mcp import ClientSession, StdioServerParameters, stdio_client  # noqa: E402
from mcp import types  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "pmn_mcp" / "server.py"
STRUMENTI = {"progetti", "info", "stima", "esegui", "stato", "annulla", "referto", "sicurezza"}
COTTO = {"prodotto": {"sale_fase_acquosa": 3.0, "ph": 6.2, "nitrito": 60, "acidi": {"lattico": 7000}},
         "profilo_temperatura": [[5, 240], [10, 120]]}


@pytest.fixture
def progetti(tmp_path):
    radice = tmp_path / "ProfileMetaNanni"
    (radice / "Salame_prova").mkdir(parents=True)
    (radice / "Salame_prova" / "config.yaml").write_text("project_name: Salame_prova\n", encoding="utf-8")
    (tmp_path / "fuori").mkdir()
    (tmp_path / "fuori" / "config.yaml").write_text("project_name: fuori\n", encoding="utf-8")
    (tmp_path / "temp").mkdir()
    return radice


def ambiente(progetti, opzioni="--velocita 0"):
    return {**os.environ, "PMN_MOTORE": "finto", "PMN_FINTO_OPZIONI": opzioni, "PMN_PROGETTI": str(progetti),
            "TEMP": str(progetti.parent / "temp"), "TMP": str(progetti.parent / "temp"), "PYTHONIOENCODING": "utf-8"}


def con_client(progetti, lavoro, elicitazione=None, opzioni="--velocita 0"):
    """Avvia il server come lo avvia un client vero (processo figlio, stdio) e passa la sessione a `lavoro`."""
    async def corri():
        p = StdioServerParameters(command=sys.executable, args=[str(SERVER)], env=ambiente(progetti, opzioni))
        async with stdio_client(p) as (r, w):
            async with ClientSession(r, w, elicitation_callback=elicitazione) as s:
                await s.initialize()
                return await lavoro(s)
    return anyio.run(corri)


def dati(r):
    assert not r.is_error, r.content
    return r.structured_content if r.structured_content is not None else json.loads(r.content[0].text)


def test_cm1_solo_stdio_nessuna_porta():
    testo = SERVER.read_text(encoding="utf-8")
    codice = "\n".join(r.split("#")[0] for r in testo.splitlines())
    assert re.search(r"server\.run\(\"stdio\"\)", codice)
    for vietato in (r"\bsocket", r"\bstreamable", r"\bsse\b", r"\buvicorn", r"http\.server", r"\bhost\s*=", r"\bport\s*="):
        assert not re.search(vietato, codice), vietato
    assert "shell=True" not in codice and "create_subprocess_shell" not in codice
    assert not re.search(r"(?i)(api[_-]?key|token|password)\s*=", codice)       # CM5: nessuna credenziale


def test_cm2_strumenti_info_e_stima_con_gli_eventi_dell_app(progetti):
    async def lavoro(s):
        nomi = {t.name for t in (await s.list_tools()).tools}
        progressi = []

        async def avanzamento(p, tot, msg):
            progressi.append(p)
        i = dati(await s.call_tool("info", {}))
        st = dati(await s.call_tool("stima", {"progetto": "Salame_prova"}, progress_callback=avanzamento))
        el = dati(await s.call_tool("progetti", {}))
        return nomi, i, st, el
    nomi, i, st, el = con_client(progetti, lavoro)
    assert nomi == STRUMENTI
    assert i["esito"] == "ok" and i["risultato"]["ram_gb"] > 0 and [e["tipo"] for e in i["eventi"]][::len(i["eventi"]) - 1] \
        == ["inizio", "fine"]
    assert st["esito"] == "ok" and st["risultato"]["campioni"] == 1 and st["eventi"][-1]["tipo"] == "fine"
    assert el["progetti"] == [{"nome": "Salame_prova", "risultati": False}]


def test_cm4_progetti_fuori_dalla_cartella_rifiutati(progetti):
    fuori = progetti.parent / "fuori" / "config.yaml"
    prove = ["..", "../fuori", str(fuori), str(progetti / ".." / "fuori" / "config.yaml"),
             str(progetti / "Salame_prova" / "risultati.json"), "Salame_prova\x00", "Non_esiste", "", "a" * 500]

    async def lavoro(s):
        out = [await s.call_tool("stima", {"progetto": p}) for p in prove]
        out.append(await s.call_tool("annulla", {"corsa": "../../x"}))
        out.append(await s.call_tool("esegui", {"progetto": str(fuori)}))
        return out
    risposte = con_client(progetti, lavoro)
    assert all(r.is_error for r in risposte), [r.content for r in risposte if not r.is_error]
    assert not (progetti.parent / "fuori" / "risultati").exists()


def aspetta_fine(s):
    async def ciclo():
        for _ in range(600):
            st = dati(await s.call_tool("stato", {}))
            if not st["in_corso"]:
                return st
            await anyio.sleep(0.1)
        raise AssertionError("l'analisi non finisce")
    return ciclo()


def test_cm3_esegui_senza_elicitation_vuole_il_codice(progetti):
    async def lavoro(s):
        primo = dati(await s.call_tool("esegui", {"progetto": "Salame_prova"}))
        sbagliato = dati(await s.call_tool("esegui", {"progetto": "Salame_prova", "codice_conferma": "000000"}))
        partito_prima = (progetti / "Salame_prova" / "risultati").exists()
        avvio = dati(await s.call_tool("esegui", {"progetto": "Salame_prova",
                                                  "codice_conferma": primo["codice_conferma"]}))
        fine = await aspetta_fine(s)
        di_nuovo = dati(await s.call_tool("esegui", {"progetto": "Salame_prova",
                                                     "codice_conferma": primo["codice_conferma"]}))   # una volta sola
        return primo, sbagliato, partito_prima, avvio, fine, di_nuovo
    primo, sbagliato, partito_prima, avvio, fine, di_nuovo = con_client(progetti, lavoro)
    assert primo["avviata"] is False and primo["serve_conferma"] and "1 campione," in primo["stima"]
    assert sbagliato["avviata"] is False and not partito_prima
    assert avvio["avviata"] is True and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}", avvio["corsa"])
    assert fine["fine"]["esito"] == "ok" and fine["eventi"][0]["tipo"] == "inizio" and fine["eventi"][-1]["tipo"] == "fine"
    assert any(e["tipo"] == "avanzamento" for e in fine["eventi"])
    assert (progetti / "Salame_prova" / "risultati" / "risultati.json").is_file()
    assert di_nuovo["avviata"] is False and di_nuovo["serve_conferma"]


@pytest.mark.parametrize("risposta, parte", [("accept", True), ("decline", False)])
def test_cm3_esegui_chiede_alla_persona(progetti, risposta, parte):
    domande = []

    async def persona(context, params):
        domande.append(params.message)
        return types.ElicitResult(action=risposta, content={"avvia": True} if risposta == "accept" else None)

    async def lavoro(s):
        r = dati(await s.call_tool("esegui", {"progetto": "Salame_prova"}))
        if r["avviata"]:
            await aspetta_fine(s)
        return r
    r = con_client(progetti, lavoro, elicitazione=persona)
    assert len(domande) == 1 and "Salame_prova" in domande[0] and "minuti" in domande[0]
    assert r["avviata"] is parte
    assert (progetti / "Salame_prova" / "risultati" / "risultati.json").is_file() is parte


def test_annulla_ferma_l_analisi(progetti):
    async def persona(context, params):
        return types.ElicitResult(action="accept", content={"avvia": True})

    async def lavoro(s):
        avvio = dati(await s.call_tool("esegui", {"progetto": "Salame_prova"}))
        stop = dati(await s.call_tool("annulla", {"corsa": avvio["corsa"]}))
        return avvio, stop, await aspetta_fine(s)
    avvio, stop, fine = con_client(progetti, lavoro, elicitazione=persona, opzioni="--velocita 1")
    assert avvio["avviata"] and stop["risultato"]["annullata"] is True
    assert fine["fine"]["esito"] == "annullata"


def test_referto_e_sicurezza(progetti):
    async def persona(context, params):
        return types.ElicitResult(action="accept", content={"avvia": True})

    async def lavoro(s):
        await s.call_tool("esegui", {"progetto": "Salame_prova"})
        await aspetta_fine(s)
        ref = dati(await s.call_tool("referto", {"progetto": "Salame_prova"}))
        sic = dati(await s.call_tool("sicurezza", {"ingresso": COTTO}))
        rotta = await s.call_tool("sicurezza", {"ingresso": {"prodotto": "x" * 70_000}})
        return ref, sic, rotta
    ref, sic, rotta = con_client(progetti, lavoro, elicitazione=persona)
    assert ref["esito"] == "ok" and ref["risultato"]["referto"]["html"] == "referto/referto.html"
    assert sic["esito"] == "ok" and sic["risultato"]["previsioni"]
    assert rotta.is_error
