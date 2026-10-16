# -*- coding: utf-8 -*-
"""The engine-GUI contract (docs/contratto_motore.md section 4) as a check, shared by the tests of the
fake engine and of the installer: whatever speaks to the GUI must pass it."""
import json
from datetime import datetime

# fields of each event type (all have tipo, ora, messaggio)
CAMPI = {"inizio": {"comando", "corsa", "log"},
         "avanzamento": {"passo", "campione", "fatto", "totale", "percentuale", "eta_s"},
         "avviso": {"codice"}, "errore": {"codice", "cosa_fare"}, "fine": {"esito", "risultato"}}
PASSI = {"download", "controllo_qualita", "pulizia", "ospite", "metaphlan", "kraken", "riepilogo",
         "controllo", "programmi", "database", "verifica", "fine"}
CODICI = {"CONFIG_NON_VALIDA", "DB_MANCANTE", "DB_ROVINATO", "SPAZIO_INSUFFICIENTE", "RAM_INSUFFICIENTE",
          "READ_NON_TROVATE", "DOWNLOAD_FALLITO", "GIA_IN_CORSO", "TEMPO_LUNGO",
          "SISTEMA_NON_ADATTO", "PROGRAMMA_MANCANTE", "VERIFICA_ROSSA", "RETE_NON_MISURATA", "RETE_INTERROTTA",
          "ERRORE_INTERNO"}
USCITA = {"ok": 0, "annullata": 3}


def controlla(stdout, codice_uscita, comando):
    """Every line obeys the contract; returns the events."""
    righe = stdout.splitlines()
    assert righe, "no output"
    ev = [json.loads(r) for r in righe]          # every line is one JSON object
    for e in ev:
        assert e["tipo"] in CAMPI
        assert CAMPI[e["tipo"]] | {"tipo", "ora", "messaggio"} <= set(e)
        assert datetime.fromisoformat(e["ora"]).tzinfo is not None
        assert isinstance(e["messaggio"], str) and e["messaggio"]
        if e["tipo"] == "avanzamento":
            assert e["passo"] in PASSI
            assert 0 <= e["percentuale"] <= 100
            assert e["eta_s"] is None or e["eta_s"] >= 0
        if e["tipo"] in ("avviso", "errore"):
            assert e["codice"] in CODICI
    assert ev[0]["tipo"] == "inizio" and ev[0]["comando"] == comando
    fini = [e for e in ev if e["tipo"] == "fine"]
    assert len(fini) == 1 and ev[-1]["tipo"] == "fine"
    esito = fini[0]["esito"]
    assert esito in ("ok", "errore", "annullata")
    if esito == "errore":
        assert any(e["tipo"] == "errore" for e in ev)
        assert codice_uscita in (1, 2, 4)
    else:
        assert codice_uscita == USCITA[esito]
    return ev
