"""Server MCP di profilemetananni (D130): il motore usabile da un assistente compatibile MCP (Claude Code, Codex,
Qwen Code, GLM, altri).

Impostazione del 18/10/2026:
- espone i comandi che il motore ha già: info, stima, esegui, annulla, referto, sicurezza, con gli stessi eventi JSON
  dell'app (docs/contratto_motore.md). In più due aiuti che non toccano il motore: `progetti` (elenco dei progetti) e
  `stato` (eventi dell'analisi avviata da qui, che dura molti minuti);
- solo locale: trasporto stdio, nessuna porta di rete;
- `esegui` parte solo dopo una conferma esplicita della persona (domanda nel client, MCP "elicitation"; se il client
  non sa farla, codice di conferma a due passi con la stima davanti);
- nessuna credenziale; input validati: il progetto è un config.yaml dentro la cartella dei progetti.

Avvio: <python con mcp 2.3.0> pmn_mcp/server.py  (istruzioni per i client: pmn_mcp/LEGGIMI.md)
Variabili: PMN_MOTORE=finto (il finto motore, per le prove), PMN_FINTO_OPZIONI, PMN_PROGETTI (cartella dei progetti,
predefinita Documenti\\ProfileMetaNanni come l'app), PMN_LINGUA=en (messaggi del motore in inglese).
"""
import asyncio
import json
import os
import re
import secrets
import shlex
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path, PureWindowsPath

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

RADICE = Path(__file__).resolve().parent.parent
DISTRO, MOTORE_WSL = "pmn", "/home/pmn/.pmn/bin/pmn-motore"     # come app/motore.py
NOME = re.compile(r"(?![-.])[A-Za-z0-9._-]{1,64}")                 # nome di un progetto (validate_name di run.sh)
CORSA = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}")          # id della corsa del motore (evento inizio)
CONFERMA_S = 600                                                    # il codice di conferma vale 10 minuti
MAX_INGRESSO = 64_000                                               # byte della richiesta di sicurezza
MAX_RIGA = 64 * 1024 * 1024        # byte di una riga JSON del motore (il 'fine' porta il risultato intero)


# ---------------- motore ----------------
def finto():
    return os.environ.get("PMN_MOTORE") == "finto"


def comando(nome, *argomenti):
    """La riga di comando del motore, come la lancia l'app (app/motore.py): mai attraverso una shell."""
    if finto():
        programma = [sys.executable, str(RADICE / "installer" / "finto_motore.py")]
        opzioni = shlex.split(os.environ.get("PMN_FINTO_OPZIONI", ""))
    else:
        programma, opzioni = ["wsl.exe", "-d", DISTRO, "-u", "pmn", "-e", MOTORE_WSL], []   # -e: senza bash -c
    lingua = ["--lingua", "en"] if os.environ.get("PMN_LINGUA") == "en" else []
    return programma + [nome, *argomenti] + opzioni + lingua


def per_motore(percorso):
    """Un percorso di Windows come lo vede il motore nella WSL (C:\\a\\b -> /mnt/c/a/b); invariato per il finto."""
    if finto() or os.name != "nt":
        return str(percorso)
    p = PureWindowsPath(percorso)
    if not re.fullmatch(r"[A-Za-z]:", p.drive):
        raise ValueError("Il progetto deve stare su un disco locale di questo PC.")
    return "/mnt/" + p.drive[0].lower() + "/" + "/".join(p.parts[1:])


async def lancia(nome, *argomenti, eventi=None):
    """Lancia un comando del motore e restituisce {esito, messaggio, risultato, eventi}. `eventi` (facoltativo) è
    chiamato a ogni evento JSON, appena arriva. Su stdout del motore ci sono solo eventi (contratto §4)."""
    p = await asyncio.create_subprocess_exec(*comando(nome, *argomenti), stdin=asyncio.subprocess.DEVNULL,
                                             stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                             env={**os.environ, "WSL_UTF8": "1"}, limit=MAX_RIGA)
    return await raccogli(p, eventi)


async def raccogli(p, eventi=None, tutti=None):
    tutti = [] if tutti is None else tutti
    errori = asyncio.create_task(p.stderr.read())        # stderr: solo diagnostica, mai al client
    async for riga in p.stdout:
        try:
            e = json.loads(riga.decode("utf-8", "replace"))
        except ValueError:
            continue
        if isinstance(e, dict) and "tipo" in e:
            tutti.append(e)
            if eventi:
                await eventi(e)
    await p.wait()
    await errori
    fine = next((e for e in reversed(tutti) if e["tipo"] == "fine"), None)
    if fine is None:
        return {"esito": "errore", "messaggio": "Il motore si è chiuso senza finire il lavoro.",
                "risultato": {"codice": "ERRORE_INTERNO"}, "eventi": tutti}
    return {"esito": fine.get("esito"), "messaggio": fine.get("messaggio"), "risultato": fine.get("risultato"),
            "eventi": tutti}


async def inoltra(ctx, e):
    """Gli eventi del motore al client MCP: avanzamento -> progress; avviso, errore -> log."""
    try:
        if e["tipo"] == "avanzamento":
            await ctx.report_progress(float(e.get("percentuale") or 0), 100, e.get("messaggio"))
        elif e["tipo"] == "avviso":
            await ctx.warning(e.get("messaggio"))
        elif e["tipo"] == "errore":
            await ctx.error(f"{e.get('messaggio')} {e.get('cosa_fare', '')}".strip())
    except Exception:   # un client che non ascolta i progressi non deve fermare il motore
        pass


# ---------------- input ----------------
def cartella_progetti():
    """Documenti\\ProfileMetaNanni, come l'app (anche con Documenti spostati, per esempio su OneDrive)."""
    if os.environ.get("PMN_PROGETTI"):
        return Path(os.environ["PMN_PROGETTI"]).resolve()
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
                return (Path(os.path.expandvars(winreg.QueryValueEx(k, "Personal")[0])) / "ProfileMetaNanni").resolve()
        except OSError:
            pass
    return (Path.home() / "Documents" / "ProfileMetaNanni").resolve()


def progetto_valido(progetto):
    """Il config.yaml di un progetto: un nome di progetto, la sua cartella o il suo config.yaml, sempre DENTRO la
    cartella dei progetti (niente "..", niente collegamenti che portano fuori, niente altri file)."""
    if not isinstance(progetto, str) or not progetto.strip() or len(progetto) > 400 or "\x00" in progetto:
        raise ValueError("Progetto non valido.")
    radice = cartella_progetti()
    p = radice / progetto if NOME.fullmatch(progetto) else Path(progetto)
    if p.is_dir():
        p = p / "config.yaml"
    try:
        p = p.resolve(strict=True)
    except OSError:
        raise ValueError(f"Non trovo il progetto {progetto!r} nella cartella dei progetti ({radice}).")
    if p.name != "config.yaml" or not p.is_file() or p.parent.parent != radice:
        raise ValueError(f"Accetto solo il config.yaml di un progetto dentro {radice}.")
    return p


def corsa_valida(corsa):
    if not isinstance(corsa, str) or not CORSA.fullmatch(corsa):
        raise ValueError("Codice della corsa non valido (forma 2026-10-18T09-30-00).")
    return corsa


# ---------------- esegui in sottofondo ----------------
class Analisi:
    """L'analisi avviata da questo server: dura molti minuti, quindi esegui risponde subito e stato la segue."""

    def __init__(self, progetto):
        self.progetto, self.eventi, self.esito, self.processo, self.compito = progetto, [], None, None, None

    @property
    def corsa(self):
        return next((e.get("corsa") for e in self.eventi if e["tipo"] == "inizio"), None)

    def in_corso(self):
        return self.esito is None


class Stato:
    analisi = None
    conferme = {}      # codice -> (progetto, scadenza): solo per i client senza elicitation


class Conferma(BaseModel):
    avvia: bool = Field(description="Sì, avvia adesso l'analisi (dura molti minuti e usa quasi tutto il PC).")


@asynccontextmanager
async def ciclo(_server):
    try:
        yield {}
    finally:   # il client si chiude: un'analisi lasciata senza chi la legge si ferma in modo pulito
        a = Stato.analisi
        if a and a.in_corso() and a.corsa:
            try:
                await asyncio.wait_for(lancia("annulla", "--corsa", a.corsa), 60)
            except Exception:
                pass


server = MCPServer("profilemetananni", lifespan=ciclo, instructions=(
    "Motore di profilemetananni: profilo dei taxa di un salume da read di metagenomica (MetaPhlAn e Kraken separati, "
    "mai sommati; Kraken e sicurezza alimentare sono prototipi, non per decisioni). Prima `progetti` e `info`, poi "
    "`stima`; `esegui` chiede sempre la conferma della persona e dura molti minuti: seguila con `stato`."))
SOLO_LETTURA = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)


@server.tool(annotations=SOLO_LETTURA)
async def progetti() -> dict:
    """Elenca i progetti di profilemetananni (cartelle con config.yaml) e dice se hanno già i risultati."""
    radice = cartella_progetti()
    out = [{"nome": d.name, "risultati": (d / "risultati" / "risultati.json").is_file()}
           for d in sorted(radice.iterdir()) if (d / "config.yaml").is_file()] if radice.is_dir() else []
    return {"cartella": str(radice), "progetti": out}


@server.tool(annotations=SOLO_LETTURA)
async def info(ctx: Context) -> dict:
    """Com'è fatto questo PC (memoria, processori, spazio) e che cosa del motore è installato (programmi, database,
    campione d'esempio). Comando `info` del motore."""
    return await lancia("info", eventi=lambda e: inoltra(ctx, e))


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True))
async def stima(progetto: str, ctx: Context) -> dict:
    """Tempo e spazio previsti per analizzare un progetto, con i consigli. Non avvia nulla. Per i codici SRR chiede
    le dimensioni a ENA o NCBI. `progetto`: nome del progetto (vedi `progetti`) o percorso del suo config.yaml."""
    return await lancia("stima", "--progetto", per_motore(progetto_valido(progetto)), eventi=lambda e: inoltra(ctx, e))


def riassunto(s):
    r = s.get("risultato") or {}
    if s.get("esito") != "ok":
        return f"Stima non riuscita: {s.get('messaggio')}"
    def it(x):   # la frase è sempre in italiano: virgola per i decimali
        return str(x).replace(".", ",")
    n, minuti = r.get("campioni"), round((r.get("tempo_totale_s") or 0) / 60)
    return (f"{n} {'campione' if n == 1 else 'campioni'}, circa {minuti} {'minuto' if minuti == 1 else 'minuti'}, "
            f"{it(r.get('spazio_gb'))} GB di spazio (liberi {it(r.get('spazio_libero_gb'))} GB).")


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False,
                                         openWorldHint=True))
async def esegui(progetto: str, ctx: Context, codice_conferma: str | None = None) -> dict:
    """Avvia l'analisi di un progetto (dura molti minuti e usa quasi tutto il PC; un'analisi alla volta). Parte SOLO
    con la conferma esplicita della persona: il client gliela chiede; se il client non sa farlo, la prima chiamata
    restituisce la stima e un codice: mostra la stima alla persona e richiama con `codice_conferma` solo se dice sì.
    Poi segui l'analisi con `stato`."""
    cfg = progetto_valido(progetto)
    if Stato.analisi and Stato.analisi.in_corso():
        raise ValueError("C'è già un'analisi avviata da qui: seguila con stato, oppure fermala con annulla.")
    caps = ctx.client_capabilities
    if caps is not None and caps.elicitation is not None:
        s = await lancia("stima", "--progetto", per_motore(cfg))
        try:
            r = await ctx.elicit(f"Avvio l'analisi del progetto {cfg.parent.name}? {riassunto(s)}", schema=Conferma)
        except Exception as ex:
            return {"avviata": False, "motivo": f"Non sono riuscito a chiedere la conferma alla persona: {ex}"}
        if r.action != "accept" or not r.data.avvia:
            return {"avviata": False, "motivo": "La persona non ha confermato: l'analisi non parte."}
    else:
        adesso = time.monotonic()
        Stato.conferme = {c: v for c, v in Stato.conferme.items() if v[1] > adesso}
        if not (codice_conferma and Stato.conferme.get(codice_conferma, (None,))[0] == cfg):
            s = await lancia("stima", "--progetto", per_motore(cfg))
            codice = secrets.token_hex(3)
            Stato.conferme[codice] = (cfg, adesso + CONFERMA_S)
            return {"avviata": False, "serve_conferma": True, "stima": riassunto(s), "codice_conferma": codice,
                    "istruzioni": "Mostra questa stima alla persona e chiedile se vuole avviare l'analisi. Solo se "
                                  "risponde sì, richiama esegui con questo codice_conferma (vale 10 minuti, una volta)."}
        del Stato.conferme[codice_conferma]
    a = Analisi(cfg)
    a.processo = await asyncio.create_subprocess_exec(*comando("esegui", "--progetto", per_motore(cfg)),
                                                      stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                                                      stderr=asyncio.subprocess.PIPE, env={**os.environ, "WSL_UTF8": "1"},
                                                      limit=MAX_RIGA)

    async def segui():   # un'eccezione qualsiasi non deve lasciare l'analisi "in corso" per sempre
        try:
            a.esito = await raccogli(a.processo, tutti=a.eventi)
        except Exception as ex:
            a.esito = {"esito": "errore", "messaggio": f"Non riesco a leggere il motore: {ex}",
                       "risultato": {"codice": "ERRORE_INTERNO"}, "eventi": a.eventi}
    a.compito = asyncio.create_task(segui())
    Stato.analisi = a
    fine = time.monotonic() + 30
    while a.corsa is None and a.in_corso() and time.monotonic() < fine:   # aspetta l'evento inizio (il codice)
        await asyncio.sleep(0.1)
    fine = time.monotonic() + 3   # rifiuti del motore (GIA_IN_CORSO, DB_MANCANTE, config): subito dopo inizio
    while a.in_corso() and time.monotonic() < fine:
        await asyncio.sleep(0.1)
    if not a.in_corso() and a.esito.get("esito") != "ok":
        return {"avviata": False, "corsa": a.corsa, "progetto": cfg.parent.name,
                "codice": (a.esito.get("risultato") or {}).get("codice"), "motivo": a.esito.get("messaggio")}
    return {"avviata": True, "corsa": a.corsa, "progetto": cfg.parent.name,
            "messaggio": "Analisi avviata. Seguila con stato; per fermarla usa annulla con questo codice."}


@server.tool(annotations=SOLO_LETTURA)
async def stato(dal: int = 0) -> dict:
    """Come va l'analisi avviata da qui con esegui: ultimo avanzamento, tempo che resta, e alla fine il risultato
    (in `fine`). `eventi`: gli eventi del motore (gli stessi che vede l'app) dalla posizione `dal` in poi, senza il
    risultato; passa `prossimo` come `dal` alla chiamata dopo per ricevere solo quelli nuovi."""
    a = Stato.analisi
    if a is None:
        return {"analisi": None, "messaggio": "Nessuna analisi avviata da questo server."}
    ultimo = next((e for e in reversed(a.eventi) if e["tipo"] == "avanzamento"), {})
    return {"corsa": a.corsa, "progetto": a.progetto.parent.name, "in_corso": a.in_corso(),
            "percentuale": ultimo.get("percentuale"), "messaggio": ultimo.get("messaggio"), "eta_s": ultimo.get("eta_s"),
            "fine": None if a.in_corso() else {k: a.esito[k] for k in ("esito", "messaggio", "risultato")},
            "eventi": [{k: v for k, v in e.items() if k != "risultato"} for e in a.eventi[max(dal, 0):]],
            "prossimo": len(a.eventi)}


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
async def annulla(corsa: str, ctx: Context) -> dict:
    """Ferma l'analisi con questo codice (evento inizio di esegui). I passi finiti restano, quelli a metà si rifanno."""
    risposta = await lancia("annulla", "--corsa", corsa_valida(corsa), eventi=lambda e: inoltra(ctx, e))
    a = Stato.analisi
    if a and a.corsa == corsa and a.compito:
        try:
            await asyncio.wait_for(asyncio.shield(a.compito), 60)
        except asyncio.TimeoutError:
            pass
    return risposta


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
async def referto(progetto: str, ctx: Context) -> dict:
    """Rifà il referto (HTML, PDF, Excel) di un progetto già analizzato, per esempio dopo un calcolo di sicurezza."""
    return await lancia("referto", "--progetto", per_motore(progetto_valido(progetto)), eventi=lambda e: inoltra(ctx, e))


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
async def sicurezza(ingresso: dict, ctx: Context, progetto: str | None = None) -> dict:
    """Previsioni di crescita (FSSP, prototipo: non dicono se un prodotto è sicuro). `ingresso` = la richiesta del
    contratto (prodotto, temperature, conte, modalità); con `progetto` usa le specie trovate e salva nel progetto."""
    testo = json.dumps(ingresso, ensure_ascii=False) if isinstance(ingresso, dict) else ""
    if not testo or len(testo.encode("utf-8")) > MAX_INGRESSO:
        raise ValueError("La richiesta di sicurezza deve essere un oggetto JSON di al massimo 64 KB.")
    argomenti = ["--progetto", per_motore(progetto_valido(progetto))] if progetto else []
    with tempfile.TemporaryDirectory(prefix="pmn_mcp_") as d:
        f = Path(d) / "ingresso.json"
        f.write_text(testo, encoding="utf-8")
        return await lancia("sicurezza", "--ingresso", per_motore(f), *argomenti, eventi=lambda e: inoltra(ctx, e))


if __name__ == "__main__":
    server.run("stdio")   # solo stdio: nessuna porta di rete (D130)
