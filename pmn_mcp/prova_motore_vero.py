"""R1 (18/10/2026), criterio CM7: un client MCP locale (SDK ufficiale, lo stesso protocollo di Claude Code e Codex)
avvia pmn_mcp/server.py come processo figlio (stdio) e lancia `info` e `stima` sul MOTORE VERO (WSL pmn).
Uso:  pmn_mcp\\.venv\\Scripts\\python pmn_mcp\\prova_motore_vero.py [progetto]"""
import json
import os
import sys
import time
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters, stdio_client

RADICE = Path(__file__).resolve().parents[1]
PROGETTO = sys.argv[1] if len(sys.argv) > 1 else "Salame_esempio"


async def main():
    env = {k: v for k, v in os.environ.items() if k not in ("PMN_MOTORE", "PMN_FINTO_OPZIONI", "PMN_PROGETTI")}
    p = StdioServerParameters(command=sys.executable, args=[str(RADICE / "pmn_mcp" / "server.py")], env=env)
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            print("server:", init.server_info.name, "| strumenti:", sorted(t.name for t in (await s.list_tools()).tools))
            for nome, argomenti in (("progetti", {}), ("info", {}), ("stima", {"progetto": PROGETTO})):
                t0 = time.monotonic()
                avanzamenti = []

                async def avanza(pct, tot, msg):
                    avanzamenti.append((pct, msg))
                res = await s.call_tool(nome, argomenti, progress_callback=avanza)
                dati = res.structured_content or json.loads(res.content[0].text)
                print(f"\n== {nome} ({time.monotonic() - t0:.1f} s, errore={res.is_error})")
                if nome == "progetti":
                    print(json.dumps(dati, ensure_ascii=False))
                    continue
                print("esito:", dati["esito"], "| messaggio:", dati["messaggio"])
                print("eventi:", [e["tipo"] for e in dati["eventi"]])
                r_ = dati["risultato"] or {}
                if nome == "info":
                    print({k: r_.get(k) for k in ("motore", "ram_gb", "processori", "spazio_libero_gb", "modo_consigliato")})
                    print("database:", {d["nome"]: d["installato"] for d in r_.get("database", [])})
                else:
                    print({k: r_.get(k) for k in ("campioni", "nomi_campioni", "coppie_totali", "tempo_totale_s",
                                                  "spazio_gb", "spazio_libero_gb")})


anyio.run(main)
