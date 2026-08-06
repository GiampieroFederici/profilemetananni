# Biomni — verifica documentale (spike Fase C)

**Data:** 2026-08-06

Nota:
- Questa è solo la metà documentale dello spike.
- Non è stato installato NIENTE (niente pip, niente conda, niente download).
- Sono state lette solo le fonti pubbliche su GitHub (`snap-stanford/Biomni`, branch `main`).
- Ogni verdetto riporta l'URL letto e la citazione esatta.

---

## Q1 — Provider LLM supportati

- File letto: `biomni/llm.py`, funzione `get_llm(...)`.
- Il codice definisce esplicitamente:

```python
SourceType = Literal["OpenAI", "AzureOpenAI", "Anthropic", "Ollama", "Gemini", "Bedrock", "Groq", "Custom"]
ALLOWED_SOURCES: set[str] = set(SourceType.__args__)
```

- Il codice poi fa branching `if/elif` su ognuno di questi 8 provider dentro `get_llm`:
  - `OpenAI` → `langchain_openai.ChatOpenAI`
  - `AzureOpenAI` → `langchain_openai.AzureChatOpenAI`
  - `Anthropic` → `langchain_anthropic.ChatAnthropic`
  - `Gemini` → `ChatOpenAI` puntato a `https://generativelanguage.googleapis.com/v1beta/openai/` (endpoint OpenAI-compatible di Google, non un client Gemini nativo)
  - `Groq` → `ChatOpenAI` puntato a `https://api.groq.com/openai/v1`
  - `Ollama` → `langchain_ollama.ChatOllama`
  - `Bedrock` → `langchain_aws.ChatBedrock`
  - `Custom` → `ChatOpenAI` con `base_url` obbligatorio (endpoint OpenAI-compatible generico, es. SGLang)

**VERDETTO: CONFERMATO**
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni/llm.py`
- Evidenza: riga `SourceType = Literal["OpenAI", "AzureOpenAI", "Anthropic", "Ollama", "Gemini", "Bedrock", "Groq", "Custom"]` + gli 8 blocchi `if source == "..."` nella funzione `get_llm`.

---

## Q1b — Ollama, nello specifico

- Ollama è un provider di prima classe nel `Literal`, non un hack.
- Codice esatto nel branch Ollama di `get_llm`:

```python
elif source == "Ollama":
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        raise ImportError(
            "langchain-ollama package is required for Ollama models. Install with: pip install langchain-ollama"
        )
    return ChatOllama(
        model=model,
        temperature=temperature,
    )
```

- C'è anche un auto-detect: se il nome del modello contiene `llama`, `mistral`, `qwen`, `gemma`, `phi`, `dolphin`, `orca`, `vicuna`, `deepseek`, oppure ha uno `/` dentro, o inizia con `gpt-oss`, il `source` viene impostato automaticamente su `"Ollama"` anche senza specificarlo:

```python
elif model[:7] == "gpt-oss":
    source = "Ollama"
...
elif "/" in model or any(
    name in model.lower()
    for name in ["llama", "mistral", "qwen", "gemma", "phi", "dolphin", "orca", "vicuna", "deepseek"]
):
    source = "Ollama"
```

- In più esiste una via "Custom" per qualsiasi endpoint OpenAI-compatible locale (es. SGLang), con `base_url`:

```python
elif source == "Custom":
    ...
    # Custom LLM serving such as SGLang. Must expose an openai compatible API.
    assert base_url is not None, "base_url must be provided for customly served LLMs"
    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        max_tokens=8192,
        stop_sequences=stop_sequences,
        base_url=base_url,
        api_key=api_key,
    )
```

- Nota pratica: nel conda env di default (`biomni_env/environment.yml`) il pacchetto `langchain-ollama` è **già incluso** di serie (insieme a `langchain-openai`, `langchain-anthropic`). Quindi Ollama funziona "out of the box" con l'ambiente conda ufficiale, senza installare pacchetti extra.

**VERDETTO: CONFERMATO**
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni/llm.py`
- Evidenza: blocco `elif source == "Ollama": ... return ChatOllama(model=model, temperature=temperature)` + logica di auto-detect citata sopra.
- URL secondario: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni_env/environment.yml` — riga pip `langchain-ollama` presente di default.

---

## Q2 — Firma esatta di A1

- File letto: `biomni/agent/a1.py`.

`__init__` (copiato dal sorgente, non riscritto):

```python
def __init__(
    self,
    path: str | None = None,
    llm: str | None = None,
    source: SourceType | None = None,
    use_tool_retriever: bool | None = None,
    timeout_seconds: int | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    commercial_mode: bool | None = None,
    expected_data_lake_files: list | None = None,
):
```

- Tutti i default sono `None`: i valori reali vengono presi da `default_config` (istanza di `BiomniConfig`, in `biomni/config.py`) se il parametro non è passato:
  - `path` → `default_config.path` = `"./data"`
  - `llm` → `default_config.llm` = `"claude-sonnet-4-5"`
  - `use_tool_retriever` → `default_config.use_tool_retriever` = `True`
  - `timeout_seconds` → `default_config.timeout_seconds` = `600`
  - `commercial_mode` → `default_config.commercial_mode` = `False`

- Metodo per eseguire una query — si chiama `go`, firma:

```python
def go(self, prompt):
    """Execute the agent with the given prompt.

    Args:
        prompt: The user's query
    """
    self.critic_count = 0
    self.user_task = prompt
    ...
    return self.log, message.content
```

- `go` non ha altri parametri oltre a `prompt` (nessun default aggiuntivo). Ritorna una tupla `(log, ultimo_contenuto_messaggio)`.

**VERDETTO: CONFERMATO**
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni/agent/a1.py`
- URL config: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni/config.py`
- Evidenza: firma `__init__` e `go` copiate sopra verbatim dal sorgente.

---

## Q3 — Data lake

- Dimensione dichiarata nel README: **~11GB**, quote esatta:
  > "Data lake will be automatically downloaded on first run (~11GB)"
- Quando viene scaricato: al primo `A1(...)`, dentro `__init__`, SE `expected_data_lake_files` è `None` (default). Codice esatto:

```python
if expected_data_lake_files is None:
    expected_data_lake_files = list(self.data_lake_dict.keys())

    # Check and download missing data lake files
    print("Checking and downloading missing data lake files...")
    check_and_download_s3_files(
        s3_bucket_url="https://biomni-release.s3.amazonaws.com",
        local_data_lake_path=data_lake_dir,
        expected_files=expected_data_lake_files,
        folder="data_lake",
    )
    ...
else:
    print("Skipping datalake download (load_datalake=False)")
    print("Note: Some tools may require datalake files to function properly.")
```

- **Conferma diretta**: passare `expected_data_lake_files=[]` (lista vuota, NON `None`) fa saltare davvero il download — perché il controllo è `is None`, e `[]` non è `None`, quindi cade nel ramo `else` che salta tutto il blocco `check_and_download_s3_files`. Va nella console solo: `"Skipping datalake download (load_datalake=False)"`.
- Come redirigere la cartella dati:
  - Parametro costruttore: `A1(path="...")` → i file finiscono in `<path>/biomni_data/data_lake/`.
  - Variabile d'ambiente: `BIOMNI_PATH` oppure `BIOMNI_DATA_PATH` (letta in `BiomniConfig.__post_init__`, `biomni/config.py`):
    ```python
    if os.getenv("BIOMNI_PATH") or os.getenv("BIOMNI_DATA_PATH"):
        self.path = os.getenv("BIOMNI_PATH") or os.getenv("BIOMNI_DATA_PATH")
    ```
  - Non c'è, a quanto letto, un modo per scaricare SOLO alcuni file (`expected_data_lake_files` con una lista non vuota non è stato verificato in dettaglio — il codice controlla solo se è `None` o no, ma la lista popolata viene passata a `check_and_download_s3_files` come `expected_files`; il comportamento fine coi file "parziali" non è stato tracciato a fondo — NON DETERMINABILE su quel dettaglio specifico, il resto sì).

**VERDETTO: CONFERMATO**
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/README.md` (dimensione ~11GB)
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni/agent/a1.py` (logica download/skip)
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni/config.py` (env var `BIOMNI_PATH`/`BIOMNI_DATA_PATH`)

---

## Q4 — Windows

- `pyproject.toml` da solo elenca pochissime dipendenze (`pydantic`, `langchain`, `python-dotenv`) — MA l'ambiente reale e completo è in `biomni_env/` (conda), non in `pyproject.toml`. Installare solo via pip/pyproject NON dà un Biomni funzionante.
- `biomni_env/README.md`, quote esatta:
  > "Note: we have only tested this setup.sh script with Ubuntu 22.04, 64 bit."
- **Nessuna menzione di Windows in nessun file letto** (README principale, `biomni_env/README.md`, `setup.sh`, `install_cli_tools.sh`).
- `setup.sh` e `install_cli_tools.sh` sono script **bash**, richiedono conda o micromamba, e in più `install_cli_tools.sh` fa controlli OS con `uname` che distinguono solo **Darwin (macOS) vs Linux** — non esiste un ramo Windows:
  > uso di `"$(uname)"` per Darwin vs Linux, `"$(uname -m)"` per arm64/Intel su macOS.
- `biomni_env/environment.yml` e `biomni_env/bio_env.yml` usano i canali conda `conda-forge` + `bioconda` con pacchetti come `blast`, `samtools`, `bowtie2`, `bwa`, `bedtools`, `fastqc`, `trimmomatic`, `mafft`, `mageck`, `plannotate`, `pysam`, `cyvcf2`, `pybedtools`. Questi pacchetti bioconda sono, per prassi nota del canale bioconda, quasi tutti **solo linux-64 / osx-64**, senza build win-64. (Questo è noto per il canale bioconda in generale; non ho verificato build-per-build su anaconda.org per ciascun singolo pacchetto — lo segnalo come inferenza forte, non lettura diretta di ogni pagina pacchetto.)
- Conclusione: Biomni richiede conda a prescindere (niente installazione "senza conda" con funzionalità piena), e la sua documentazione non menziona Windows da nessuna parte, testando solo Ubuntu 22.04.

**VERDETTO: SMENTITO**
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni_env/README.md` — "we have only tested this setup.sh script with Ubuntu 22.04, 64 bit."
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni_env/install_cli_tools.sh` — controlli `uname` solo Darwin/Linux, nessun ramo Windows.
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni_env/environment.yml` e `bio_env.yml` — dipendenze bioconda.
- Parte "build win-64 assenti per bioconda" = inferenza, non lettura diretta pagina-per-pagina → la marco esplicitamente come tale sopra.

---

## Q5 — Licenza

- Licenza di Biomni stesso: **Apache 2.0**.
  - Da `pyproject.toml`: `license = "Apache-2.0"`, `license-files = ["LICENSE"]`.
  - `LICENSE` nel repo è il testo standard Apache License 2.0.
- Esiste un file dedicato `license_info.md` con l'analisi dataset-per-dataset. Quote esatte:
  > "A significant portion of the data used in Biomni requires a commercial license for any commercial application. Several datasets are explicitly licensed for non-commercial use only, which would prohibit their use in a commercial product without a separate agreement. Before proceeding with any commercial use, a thorough legal review of the licenses for each dataset you intend to use is strongly recommended."
- Esempi concreti di dataset non-commerciali/restrittivi elencati in tabella in `license_info.md`:
  - **DDInter** — CC BY-NC-SA 4.0 — "No, non-commercial use only."
  - **DisGeNET** — CC BY-NC-SA 4.0 — "No, non-commercial use only."
  - **McPAS-TCR** — CC BY-NC-SA 4.0 — "No, non-commercial use only."
  - **miRDB** — "Custom, free for non-commercial use." — "No, non-commercial use only."
  - **miRTarBase** — CC BY-NC 4.0 — "No, non-commercial use only."
  - **COSMIC**, **MSigDB**, **OMIM** — richiedono licenza commerciale a parte.
  - **BindingDB**, **Enamine** — proprietarie/licenza commerciale richiesta.
- README principale conferma lo stesso concetto in generale:
  > "Biomni itself is Apache 2.0-licensed, but certain integrated tools, databases, or software may carry more restrictive commercial licenses."
- Esiste un flag `commercial_mode=True` in `A1(...)` che, se attivato, carica `biomni/env_desc_cm.py` invece di `biomni/env_desc.py` per escludere i dataset non commerciali (confermato leggendo `__init__` di `A1`, righe con `if commercial_mode: from biomni.env_desc_cm import data_lake_dict, library_content_dict`).

**VERDETTO: CONFERMATO**
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/pyproject.toml` (Apache-2.0)
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/license_info.md` (tabella dataset + warning citato sopra)
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/README.md` (frase citata sopra)

---

## Q6 — Ricerca letteratura reale (PMID/DOI)

- File letto: `biomni/tool/literature.py` e `biomni/tool/tool_description/literature.py`.
- Esistono funzioni di ricerca REALE (non simulata):
  - `query_pubmed(query, max_papers=10, max_retries=3)` — usa la libreria `pymed.PubMed`, fa una vera chiamata all'API PubMed/Entrez.
  - `query_scholar(query)` — usa `scholarly` (Google Scholar), con proxy.
  - `query_arxiv(query, max_papers=10)` — usa la libreria `arxiv`.
- **PROBLEMA IMPORTANTE**: `query_pubmed` NON restituisce PMID né DOI. Codice esatto del return:

```python
if papers:
    results = "\n\n".join(
        [f"Title: {paper.title}\nAbstract: {paper.abstract}\nJournal: {paper.journal}" for paper in papers]
    )
    return results
```

- Ritorna solo `Title`, `Abstract`, `Journal` come stringa formattata. Nessun identificatore (`paper.pubmed_id` non viene mai letto/usato, pur essendo tipicamente disponibile sull'oggetto `Article` di `pymed`).
- Confermato anche guardando la tool description (quella che l'LLM vede per capire cosa fa il tool): nessuna menzione di `PMID` o `PubMed ID` in tutto il file `tool_description/literature.py`. L'unica menzione di `DOI` nel file è nella descrizione di una funzione diversa, `fetch_supplementary_info_from_doi` (che prende un DOI in input, non lo restituisce come output di una ricerca).
- `query_scholar` restituisce solo il **primo** risultato (`next(search_query, None)`), formattato come `Title/Year/Venue/Abstract` — anche qui nessun DOI/ID.

**VERDETTO: SMENTITO**
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni/tool/literature.py` — corpo di `query_pubmed` citato sopra (nessun `pubmed_id` nel return).
- URL: `https://raw.githubusercontent.com/snap-stanford/Biomni/main/biomni/tool/tool_description/literature.py` — nessuna occorrenza di "PMID"/"PubMed ID"; "DOI" appare solo per `fetch_supplementary_info_from_doi`.
- Nota: la ricerca REALE su PubMed esiste (quindi non è tutto da buttare), ma **non produce l'identificatore verificabile** che il piano richiede.

---

## Conseguenze per il piano

- **Ollama**: la promessa di un'opzione locale gratuita PUÒ restare — è supportata nativamente (`ChatOllama`), è già nel conda env di default, e c'è pure auto-detect per nomi modello locali comuni. Nessuna riscrittura necessaria su questo punto.
- **Opzione "Custom / SGLang"**: si può aggiungere come alternativa locale ulteriore (endpoint OpenAI-compatible con `base_url`), utile se in futuro si vuole servire un modello via SGLang invece di Ollama.
- **Citazioni verificate (PMID/DOI)**: il piano NON può fidarsi del tool `query_pubmed` di Biomni così com'è — restituisce solo testo (Title/Abstract/Journal), non l'identificatore. O si patcha/wrappa `query_pubmed` per esporre `paper.pubmed_id` (è un campo disponibile in `pymed`, va solo aggiunto al return), oppure il layer di dossier-per-taxon deve fare la propria chiamata NCBI/PubMed separata per ottenere i PMID veri, invece di fidarsi del testo generato dall'agente A1. Questo è un blocco reale da risolvere prima di promettere "citazioni sempre con PMID verificato".
- **Windows**: il piano non può promettere "gira anche su Windows nativo". Va scritto chiaramente che serve WSL (Ubuntu) o un ambiente Linux/macOS — la documentazione ufficiale testa solo Ubuntu 22.04, gli script sono bash, e le dipendenze bioconda (samtools, bowtie2, bwa, bedtools, ecc.) tipicamente non hanno build Windows. Se il server target del progetto (profilemetananni gira su server_analisis con cluster HPC Linux) è già Linux, questo potrebbe non essere un problema pratico — ma va detto esplicitamente nel design invece di essere un'assunzione implicita.
- **Data lake ~11GB**: il piano deve prevedere esplicitamente il tempo/spazio per il primo download (11GB) O usare `expected_data_lake_files=[]` per saltarlo del tutto se il dossier-generator non userà i tool che dipendono da quei dati (es. se si usa Biomni SOLO per il tool literature, molti dei file del data lake — genomica, drug repurposing, ecc. — non servono). Va anche documentato che si può ridirigere la cartella dati via `BIOMNI_PATH`/`BIOMNI_DATA_PATH` o parametro `path=`, utile per non riempire il disco di sistema sul server.
- **Licenza dataset**: se il progetto ha QUALSIASI ambizione commerciale (anche solo "vendere" un report a terzi, non solo uso interno accademico), il piano deve attivare `commercial_mode=True` fin da subito e documentare che alcuni dataset (DDInter, DisGeNET, McPAS-TCR, miRDB, miRTarBase, COSMIC, MSigDB, OMIM, BindingDB, Enamine) non sono utilizzabili commercialmente senza licenza separata. Per uso puramente accademico/interno nel laboratorio, questo non blocca nulla.
- **A1 API**: il piano di integrazione deve usare `A1(path=..., llm=..., source=..., expected_data_lake_files=...)` seguito da `.go(prompt)` che ritorna `(log, contenuto_finale)` — non un dict strutturato. Se il piano assumeva un output JSON strutturato da Biomni, questa assunzione è SBAGLIATA: bisogna fare parsing testuale del `content` finale o istruire il prompt a produrre un formato parsabile.
