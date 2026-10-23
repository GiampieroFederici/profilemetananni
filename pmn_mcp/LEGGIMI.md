# Server MCP di profilemetananni

Fa usare il motore di profilemetananni a un assistente di programmazione compatibile MCP (Model Context Protocol):
Claude Code, Codex, Qwen Code, GLM (dentro il client che lo usa), Gemini CLI, OpenCode, Cline, Kilo e gli altri.
Decisione D130 del 18/10/2026.

## Che cosa fa

| Strumento | Che cosa fa | Comando del motore |
|---|---|---|
| `progetti` | elenca i progetti in `Documenti\ProfileMetaNanni` | (nessuno, legge le cartelle) |
| `info` | com'è fatto il PC, che cosa del motore è installato | `info` |
| `stima` | tempo e spazio previsti per un progetto, con i consigli | `stima` |
| `esegui` | avvia l'analisi, **solo dopo la conferma della persona** | `esegui` |
| `stato` | come va l'analisi avviata da qui (eventi, percentuale, tempo che resta, risultato); con `dal` = il `prossimo` della chiamata prima, solo gli eventi nuovi | (legge gli eventi) |
| `annulla` | ferma l'analisi con il suo codice | `annulla` |
| `referto` | rifà il referto (HTML, PDF, Excel) di un progetto analizzato | `referto` |
| `sicurezza` | previsioni di crescita FSSP (prototipo) | `sicurezza` |

- Gli eventi sono **gli stessi dell'app** (`docs/contratto_motore.md`): ogni strumento li restituisce in `eventi`;
  l'avanzamento arriva anche come "progress" MCP.
- `progetto` = il nome del progetto (per esempio `Salame_esempio`) o il percorso del suo `config.yaml`.

## Sicurezza

| Regola | Come |
|---|---|
| Solo su questo PC | trasporto **stdio**: il client avvia il server come processo figlio; **nessuna porta di rete** |
| Conferma prima di `esegui` | se il client sa fare le domande MCP ("elicitation"), la persona risponde sì o no nel client. Se no, la prima chiamata restituisce la stima e un **codice di conferma**: l'assistente deve mostrare la stima e richiamare `esegui` con il codice **solo se la persona dice sì** (vale 10 minuti, una volta) |
| Input controllati | il progetto deve essere un `config.yaml` **dentro** `Documenti\ProfileMetaNanni` (niente `..`, niente altri file); codice della corsa con forma fissa; richiesta di sicurezza = oggetto JSON fino a 64 KB |
| Nessuna credenziale | il server non ne usa e non ne chiede; non manda nulla fuori dal PC (la stima chiede a ENA o NCBI solo le dimensioni dei codici SRR, come l'app) |
| Un'analisi alla volta | il motore ha il suo lucchetto; il server rifiuta un secondo `esegui` |

⚠️ **Limite onesto:** con un client che non sa fare le domande MCP, la conferma passa dall'assistente. Per questo:
lascia attiva nel client la **richiesta di permesso** per lo strumento `esegui` (non metterlo fra quelli approvati
in automatico).

## Installazione (una volta)

Serve Python 3.10 o più recente su Windows (qui: Python 3.11.9).

```bat
cd <cartella di profilemetananni>
python -m venv pmn_mcp\.venv
pmn_mcp\.venv\Scripts\python -m pip install -r pmn_mcp\requirements.txt
```

Nei comandi qui sotto:
- `PYTHON` = `<cartella di profilemetananni>\pmn_mcp\.venv\Scripts\python.exe`
- `SERVER` = `<cartella di profilemetananni>\pmn_mcp\server.py`

Variabili facoltative: `PMN_LINGUA=en` (messaggi del motore in inglese), `PMN_PROGETTI` (altra cartella dei
progetti), `PMN_MOTORE=finto` (il finto motore, per provare senza WSL).

## Collegarlo ai client

### Claude Code

```bat
claude mcp add -s user profilemetananni -- PYTHON SERVER
claude mcp get profilemetananni
```

`-s user` = vale in tutti i progetti; `get` deve dire `Status: ✔ Connected`.

Permesso sempre prima di un'analisi (anche in modalità automatica): in `%USERPROFILE%\.claude\settings.json`, dentro
`"permissions"`, aggiungi (o completa) il blocco:

```json
"ask": [
  "mcp__profilemetananni__esegui"
]
```

Poi riapri Claude Code: `/mcp` mostra il server e i suoi 8 strumenti. Provato su questo PC il 20/10/2026: con la regola,
una sessione senza interfaccia (`claude -p`) si ferma con "Claude requested permissions to use
mcp__profilemetananni__esegui" e il motore non parte.

### Codex (OpenAI)

In `%USERPROFILE%\.codex\config.toml`:

```toml
[mcp_servers.profilemetananni]
command = 'PYTHON'
args = ['SERVER']
tool_timeout_sec = 300
```

(`tool_timeout_sec`: la stima con i codici SRR chiede le dimensioni a ENA e NCBI e può superare il minuto.)

### Qwen Code

In `%USERPROFILE%\.qwen\settings.json`:

```json
{
  "mcpServers": {
    "profilemetananni": { "command": "PYTHON", "args": ["SERVER"], "timeout": 300000 }
  }
}
```

### GLM

GLM è un modello: si usa dentro un client (Claude Code, OpenCode, Cline, Kilo...). Collega il server **al client**
come in queste istruzioni: il modello GLM vedrà gli stessi strumenti.

### Gemini CLI

In `%USERPROFILE%\.gemini\settings.json`, stesso blocco `mcpServers` di Qwen Code.

### OpenCode

In `opencode.json`:

```json
{ "mcp": { "profilemetananni": { "type": "local", "command": ["PYTHON", "SERVER"], "enabled": true } } }
```

### Cline, Kilo Code e altri client con `mcpServers`

```json
{ "mcpServers": { "profilemetananni": { "command": "PYTHON", "args": ["SERVER"], "disabled": false, "autoApprove": ["progetti", "info", "stima", "stato"] } } }
```

`autoApprove` può contenere solo gli strumenti che leggono: **mai `esegui`**.

### Qualsiasi altro client MCP

Server **stdio**: comando `PYTHON`, argomento `SERVER`. Nessun indirizzo, nessuna porta.

## Prove

| Prova | Comando | Esito (18/10/2026) |
|---|---|---|
| Test automatici con un client MCP locale (SDK ufficiale) sul finto motore | `pmn_mcp\.venv\Scripts\python -m pytest tests/test_mcp.py` | 8 superati |
| Client MCP locale sul **motore vero**: `info` e `stima` | `pmn_mcp\.venv\Scripts\python pmn_mcp\prova_motore_vero.py Salame_esempio` | riuscita (diario R1) |
