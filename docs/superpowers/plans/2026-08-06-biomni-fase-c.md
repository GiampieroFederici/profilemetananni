# Fase C — dossier dei taxa con Biomni · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere a profilemetananni una Fase C opzionale che, partendo dalla lista di specie prodotta dalla Fase B, produce un dossier per taxon (ruolo in letteratura + funzioni attese) con citazioni verificate contro NCBI.

**Architecture:** Tutta la logica verificabile vive in due moduli puri (`steps/_biomni_core.py`, `steps/_biomni_consent.py`) che non importano Biomni e si testano con un client finto a costo zero. Un solo file (`steps/50_biomni_dossier.py`) fa da CLI e contiene l'unico adattatore che parla davvero con Biomni. `bin/run.sh` guadagna un flag `--phase c` e salta sempre la Fase C sotto PBS.

**Tech Stack:** Python 3 (stdlib + pandas via `_profiling_io`), pytest, bash, conda (`pmn_reports_py` per i test, nuovo env `pmn_biomni` per l'esecuzione reale), Biomni A1, NCBI E-utilities.

**Spec di riferimento:** `docs/superpowers/specs/2026-08-06-biomni-fase-c-design.md`

## Global Constraints

- La Fase C è **spenta di default**: `analysis.biomni.enabled: false` in `config.example.yaml`.
- Fuori dalla macchina escono **solo i nomi normalizzati delle specie**. Mai campioni, SRR, path, abbondanze, metadati, reads.
- `max_taxa`: default **5** in `config.example.yaml`, minimo 1, massimo **500**.
- Il consenso è **una sola chiave** (`enabled`) più una domanda interattiva; il sì si registra in `<work_dir>/.biomni_consent.json`.
- Cambiando **modello o fornitore** il consenso registrato non vale più.
- Senza terminale interattivo e senza consenso registrato il passo **si ferma**; il flag per l'automazione è `--yes-send-taxa`.
- `--dry-run` non invia nulla e **non** richiede consenso.
- **Il modello non sceglie le fonti.** È profilemetananni a interrogare NCBI (`esearch` + `esummary`) e a passargli un **elenco numerato**; il modello cita **per numero**, mai per PMID o DOI. Un numero fuori intervallo non è una prova. *(Regola riscritta dopo lo spike: `query_pubmed` di Biomni non restituisce il PMID.)*
- **Ambiente:** la Fase C gira in **WSL Ubuntu**, non su Windows nativo — Biomni è documentato e testato solo su Ubuntu e il suo installer non ha un ramo Windows.
- **Licenze:** Biomni è Apache 2.0 ma include dataset non commerciali; quando `commercial_mode` è attivo vanno esclusi. Da documentare in `README.md`.
- Etichette ammesse: `noto`, `assente`, `atteso`, `ipotesi`. `noto` e `assente` richiedono almeno una citazione verificata, altrimenti **declassamento automatico a `ipotesi`**.
- Categorie ammesse: `ruolo`, `batteriocine`, `ammine_biogene`, `cazymes`, `resistoma`, `virulenza`.
- La chiave API si legge **solo** dall'ambiente o da `~/.pmn/credentials`; mai da `config.yaml`, mai stampata in log, errori o output.
- Su POSIX `~/.pmn/credentials` deve avere permessi `0600`, altrimenti il file viene **rifiutato**. Su Windows i permessi POSIX non sono applicabili: il tool avvisa e consiglia la variabile d'ambiente.
- Se la variabile d'ambiente è già valorizzata, **l'ambiente vince** sul file delle credenziali.
- La Fase C **non viene mai sottomessa a PBS**: sotto `scheduler: pbs` viene saltata con messaggio esplicito.
- Stile del repository, da rispettare: `argparse`, messaggi di errore su `stderr` con prefisso `[FAIL]`, `main()` che ritorna un `int`, moduli condivisi con prefisso `_`, messaggi utente bilingui via `say "EN" "IT"` in bash.
- **Comando dei test su questa macchina.** Il piano scrive `conda run -n pmn_reports_py python -m pytest …` perché è così che va nell'ambiente di produzione. Ma **su questa macchina conda non è installato**: pytest 9.1.1 è stato installato direttamente nel Python 3.11.9 di sistema, quindi il comando da eseguire davvero è `python -m pytest tests/… -v`. Il conteggio dei test atteso resta quello scritto nei task.

---

## File Structure

| File | Responsabilità |
|---|---|
| `steps/_biomni_core.py` | **nuovo** · tipi, selezione dei taxa, filtro citazioni, verifica NCBI, etichettatura, rendering. Nessun import di Biomni. |
| `steps/_biomni_consent.py` | **nuovo** · riconoscimento fornitore, cancello di consenso, gestione credenziali. Nessun import di Biomni. |
| `steps/50_biomni_dossier.py` | **nuovo** · CLI, orchestrazione, unico adattatore che parla con Biomni. |
| `tests/test_biomni_core.py` | **nuovo** · test della logica pura. |
| `tests/test_biomni_consent.py` | **nuovo** · test di consenso e credenziali. |
| `tests/test_biomni_cli.py` | **nuovo** · test end-to-end del passo con client finto. |
| `steps/_profiling_io.py` | riuso, **nessuna modifica**. |
| `bin/lib/parse_config.py` | legge il blocco `analysis.biomni`. |
| `bin/lib/validate.sh` | valida il blocco `analysis.biomni`. |
| `bin/lib/requirements.sh` | definisce l'env `pmn_biomni`; aggiunge `pytest` a `pmn_reports_py`. |
| `bin/preflight.sh` | controlla `pmn_biomni` solo quando serve. |
| `bin/run.sh` | flag `--phase`, blocco Fase C, salto sotto PBS. |
| `config.example.yaml` · `SPEC.md` · `SECURITY.md` · `README.md` · `.gitignore` | documentazione e configurazione. |

### Interfacce pubbliche (contratto fra i task)

`steps/_biomni_core.py`

```python
LABELS = ("noto", "assente", "atteso", "ipotesi")
CATEGORIES = ("ruolo", "batteriocine", "ammine_biogene", "cazymes", "resistoma", "virulenza")

@dataclass(frozen=True)
class Citation:    pmid: str; title: str; year: str
@dataclass(frozen=True)
class Claim:       category: str; statement: str; label: str; refs: tuple   # 1-based indices
@dataclass(frozen=True)
class RawDossier:  taxon: str; detected_by: str; claims: tuple; references: tuple  # Citation
@dataclass(frozen=True)
class Dossier:     taxon: str; detected_by: str; claims: tuple; references: tuple; dropped_refs: int

select_taxa(metaphlan_path: str, kraken_path: str, threshold_pct: float, max_taxa: int) -> list[tuple[str, str]]
resolve_citations(raw: RawDossier) -> tuple[RawDossier, int]
verify_pmids(pmids: set, fetch) -> tuple[dict, list]      # used by the client, at retrieval time
apply_labels(claims: tuple) -> tuple
build_dossier(raw: RawDossier) -> Dossier
render_markdown(dossiers: list, meta: dict) -> str
render_tsv(dossiers: list) -> str
```

`steps/_biomni_client.py` (Task 8, network boundary)

```python
pubmed_search(taxon: str, retmax: int = 12) -> list[str]   # PMIDs from esearch
ncbi_fetch(pmid: str) -> Citation | None                   # esummary
build_references(taxon: str) -> tuple                      # search + verify -> ordered Citations
class BiomniClient:  __init__(llm: str, data_path: str = "");  ask(taxon, detected_by) -> RawDossier
```

`steps/_biomni_consent.py`

```python
@dataclass(frozen=True)
class Provider: key: str; label: str; env_var: str; console_url: str; local: bool

provider_for(llm: str) -> Provider
credentials_path() -> pathlib.Path
read_credentials(path) -> dict
store_credential(path, env_var: str, value: str) -> None
resolve_api_key(provider: Provider, environ: dict, path) -> str | None
translate_provider_error(status: int | None) -> str
consent_record_path(work_dir: str) -> pathlib.Path
consent_is_valid(record: dict | None, llm: str, provider: Provider) -> bool
save_consent(path, llm: str, provider: Provider, n_taxa: int) -> None
```

---

## Task 0: Spike — chiudere le cinque incognite

Non si scrive codice finché non si sa cosa Biomni fa davvero. Questo task produce **fatti**, non implementazione.

**Files:**
- Create: `docs/superpowers/specs/2026-08-06-biomni-fase-c-FINDINGS.md`

**Interfaces:**
- Consumes: niente.
- Produces: i fatti che il Task 8 usa per scrivere l'adattatore, e le eventuali correzioni allo spec.

- [ ] **Step 1: Installare Biomni in un ambiente isolato**

```bash
conda create -y -n pmn_biomni_spike python=3.11
conda run -n pmn_biomni_spike pip install biomni
conda run -n pmn_biomni_spike python -c "import biomni; print(biomni.__version__)"
```

Se fallisce su Windows nativo, ripetere dentro WSL e annotare **quale delle due funziona**.

- [ ] **Step 2: Elencare i fornitori LLM realmente accettati**

```bash
conda run -n pmn_biomni_spike python -c "import inspect, biomni.llm as m; print(inspect.getsource(m))" > llm_source.txt
```

Cercare nel sorgente i nomi dei fornitori e in particolare la stringa `ollama`. Annotare l'elenco **esatto** e se Ollama compare o no.

- [ ] **Step 3: Verificare il data lake e come spostarlo**

```bash
conda run -n pmn_biomni_spike python -c "from biomni.agent import A1; import inspect; print(inspect.signature(A1.__init__))"
df -h .
```

Annotare: dimensione reale del data lake, se `path=` o `BIOMNI_DATA_PATH` lo redirige, se `expected_data_lake_files=[]` evita davvero il download.

- [ ] **Step 4: Controllare le licenze**

```bash
conda run -n pmn_biomni_spike pip show biomni | grep -i license
```

Annotare la licenza di Biomni e se la documentazione segnala tool integrati con licenze più restrittive.

- [ ] **Step 5: Scrivere i findings e correggere lo spec se serve**

Il file `2026-08-06-biomni-fase-c-FINDINGS.md` deve contenere una riga per ognuna delle cinque incognite dello spec §13, con esito `CONFERMATO` / `SMENTITO` / `NON DETERMINABILE` e la prova (comando + output).

⚠️ **Gate:** se Ollama risulta non supportato, correggere la tabella "gratuite e locali" in §6.1 dello spec **prima** di scrivere qualsiasi testo pubblico nel README.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-08-06-biomni-fase-c-FINDINGS.md docs/superpowers/specs/2026-08-06-biomni-fase-c-design.md
git commit -m "spike: verify Biomni provider support, install path, data lake and licences"
```

---

## Task 1: Selezione dei taxa (e nascita della cartella dei test)

**Files:**
- Create: `steps/_biomni_core.py`
- Create: `tests/test_biomni_core.py`
- Modify: `bin/lib/requirements.sh` (aggiungere `pytest` a `pmn_reports_py`)

**Interfaces:**
- Consumes: `steps/_profiling_io.load_metaphlan_species`, `load_kraken_matrix` (entrambe restituiscono `{specie_normalizzata: abbondanza_max}`).
- Produces: `select_taxa(metaphlan_path, kraken_path, threshold_pct, max_taxa) -> list[tuple[str, str]]`, dove il secondo elemento è `"metaphlan"`, `"kraken"` o `"metaphlan+kraken"`.

- [ ] **Step 1: Aggiungere pytest all'env dei test**

In `bin/lib/requirements.sh`, riga della mappa `PMN_ENV_PKGS`, sostituire:

```bash
  [pmn_reports_py]="python pandas numpy scipy matplotlib seaborn openpyxl pyyaml"
```

con:

```bash
  [pmn_reports_py]="python pandas numpy scipy matplotlib seaborn openpyxl pyyaml pytest"
```

e nella mappa `PMN_ENV_PROBE` sostituire:

```bash
  [pmn_reports_py]="python -c 'import pandas,numpy,scipy,matplotlib,seaborn,openpyxl,yaml'"
```

con:

```bash
  [pmn_reports_py]="python -c 'import pandas,numpy,scipy,matplotlib,seaborn,openpyxl,yaml,pytest'"
```

- [ ] **Step 2: Scrivere il test che fallisce**

Creare `tests/test_biomni_core.py`:

```python
# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "steps"))
import _biomni_core as core  # noqa: E402


MPA = """#mpa_vJan21
clade_name\tS1\tS2
k__Bacteria|s__Latilactobacillus_sakei\t40.0\t10.0
k__Bacteria|s__Staphylococcus_xylosus\t5.0\t0.0
k__Bacteria|s__Rare_bug\t0.0005\t0.0
"""

KRK = """taxon\tS1\tS2
Latilactobacillus sakei\t35.0\t12.0
Brochothrix thermosphacta\t2.0\t1.0
"""


@pytest.fixture()
def tables(tmp_path):
    m = tmp_path / "merged.txt"
    k = tmp_path / "kraken.tsv"
    m.write_text(MPA, encoding="utf-8")
    k.write_text(KRK, encoding="utf-8")
    return str(m), str(k)


def test_metaphlan_only(tables):
    m, _ = tables
    got = core.select_taxa(m, "", threshold_pct=0.001, max_taxa=50)
    assert ("Latilactobacillus sakei", "metaphlan") in got
    assert all(src == "metaphlan" for _, src in got)


def test_union_marks_shared_taxa(tables):
    m, k = tables
    got = dict(core.select_taxa(m, k, threshold_pct=0.001, max_taxa=50))
    assert got["Latilactobacillus sakei"] == "metaphlan+kraken"
    assert got["Staphylococcus xylosus"] == "metaphlan"
    assert got["Brochothrix thermosphacta"] == "kraken"


def test_threshold_drops_rare_taxa(tables):
    m, _ = tables
    got = dict(core.select_taxa(m, "", threshold_pct=0.001, max_taxa=50))
    assert "Rare bug" not in got


def test_max_taxa_is_a_hard_cap(tables):
    m, k = tables
    got = core.select_taxa(m, k, threshold_pct=0.001, max_taxa=2)
    assert len(got) == 2


def test_no_tables_returns_empty():
    assert core.select_taxa("", "", threshold_pct=0.001, max_taxa=5) == []
```

- [ ] **Step 3: Eseguire i test e verificare che falliscano**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_core.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named '_biomni_core'`

- [ ] **Step 4: Scrivere l'implementazione minima**

Creare `steps/_biomni_core.py`:

```python
# -*- coding: utf-8 -*-
# steps/_biomni_core.py - pure logic for Phase C (taxa dossier). No Biomni import here,
# so the whole module is testable offline and at zero cost.
# Conda env: pmn_reports_py (pandas, via _profiling_io). Not meant to be run directly.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _profiling_io import load_metaphlan_species, load_kraken_matrix  # noqa: E402

LABELS = ("noto", "assente", "atteso", "ipotesi")
CATEGORIES = ("ruolo", "batteriocine", "ammine_biogene", "cazymes", "resistoma", "virulenza")


def _display(normalized: str) -> str:
    """Turn a normalized name ('latilactobacillus sakei') into a display name."""
    return normalized[:1].upper() + normalized[1:] if normalized else normalized


def select_taxa(metaphlan_path: str, kraken_path: str, threshold_pct: float, max_taxa: int):
    """Return [(display_name, detected_by)] above threshold, capped at max_taxa.

    detected_by is 'metaphlan', 'kraken' or 'metaphlan+kraken'. Ordering is by descending
    max abundance across the tools, then alphabetical, so the cap keeps the most abundant.
    """
    mpa = load_metaphlan_species(metaphlan_path, threshold_pct) if metaphlan_path else {}
    krk = load_kraken_matrix(kraken_path, threshold_pct) if kraken_path else {}
    rows = []
    for name in set(mpa) | set(krk):
        if name in mpa and name in krk:
            src = "metaphlan+kraken"
        elif name in mpa:
            src = "metaphlan"
        else:
            src = "kraken"
        rows.append((_display(name), src, max(mpa.get(name, 0.0), krk.get(name, 0.0))))
    rows.sort(key=lambda r: (-r[2], r[0]))
    return [(name, src) for name, src, _ in rows[:max_taxa]]
```

- [ ] **Step 5: Eseguire i test e verificare che passino**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_core.py -v`
Expected: PASS, 5 test

- [ ] **Step 6: Commit**

```bash
git add steps/_biomni_core.py tests/test_biomni_core.py bin/lib/requirements.sh
git commit -m "feat(phase-c): select taxa above threshold from MetaPhlAn and Kraken tables"
```

---

## Task 2: Tipi e citazioni per numero (regola anti-invenzione 1, riscritta)

> 🔄 **RISCRITTO il 2026-08-06 dopo lo spike (Task 0).** Il disegno originale filtrava i PMID
> che il modello citava, tenendo solo quelli tornati da una ricerca. **Non è realizzabile con
> Biomni:** `query_pubmed` restituisce solo `Title / Abstract / Journal`, **mai il PMID**
> (verificato sul sorgente, due volte). Quindi il modello **non sceglie più le fonti**: gliele
> forniamo noi, numerate, e lui **cita per numero**. Non vedendo mai un identificativo in forma
> libera, non ne può inventare uno plausibile; un numero fuori intervallo è banale da scartare.

**Files:**
- Modify: `steps/_biomni_core.py`
- Modify: `tests/test_biomni_core.py`

**Interfaces:**
- Consumes: niente dal Task 1 se non il modulo.
- Produces: `Citation(pmid, title, year)`, `Claim(category, statement, label, refs)` dove
  `refs` è una tupla di **interi 1-based**, `RawDossier(taxon, detected_by, claims, references)`
  dove `references` è una tupla ordinata di `Citation`, `Dossier`, e
  `resolve_citations(raw) -> tuple[RawDossier, int]` che restituisce il dossier ripulito e
  quanti riferimenti sono stati scartati perché fuori intervallo.

- [ ] **Step 1: Scrivere il test che fallisce**

Aggiungere in fondo a `tests/test_biomni_core.py`:

```python
REFS = (
    core.Citation("111", "Sakacin production in Latilactobacillus sakei", "2019"),
    core.Citation("222", "Biogenic amines in dry sausage", "2021"),
)


def _raw(**kw):
    base = dict(
        taxon="Latilactobacillus sakei",
        detected_by="metaphlan",
        claims=(core.Claim("ruolo", "starter wild-type", "noto", (1, 7)),),
        references=REFS,
    )
    base.update(kw)
    return core.RawDossier(**base)


def test_reference_number_out_of_range_is_removed():
    out, dropped = core.resolve_citations(_raw())
    assert out.claims[0].refs == (1,)
    assert dropped == 1


def test_claim_losing_all_references_keeps_an_empty_tuple():
    raw = _raw(claims=(core.Claim("resistoma", "tet(M)", "noto", (9,)),))
    out, dropped = core.resolve_citations(raw)
    assert out.claims[0].refs == ()
    assert dropped == 1


def test_zero_is_not_a_valid_reference_number():
    raw = _raw(claims=(core.Claim("ruolo", "x", "noto", (0,)),))
    out, _ = core.resolve_citations(raw)
    assert out.claims[0].refs == ()


def test_valid_references_survive_untouched():
    raw = _raw(claims=(core.Claim("ruolo", "x", "noto", (1, 2)),))
    out, dropped = core.resolve_citations(raw)
    assert out.claims[0].refs == (1, 2)
    assert dropped == 0


def test_unknown_category_is_rejected():
    with pytest.raises(ValueError):
        core.Claim("astrologia", "x", "noto", ())


def test_unknown_label_is_rejected():
    with pytest.raises(ValueError):
        core.Claim("ruolo", "x", "certissimo", ())
```

- [ ] **Step 2: Eseguire i test e verificare che falliscano**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_core.py -v`
Expected: FAIL con `AttributeError: module '_biomni_core' has no attribute 'Citation'`

- [ ] **Step 3: Scrivere l'implementazione minima**

Aggiungere in `steps/_biomni_core.py`, subito dopo le costanti (e aggiungere
`from dataclasses import dataclass, replace` agli import in cima al file):

```python
@dataclass(frozen=True)
class Citation:
    pmid: str
    title: str
    year: str


@dataclass(frozen=True)
class Claim:
    category: str
    statement: str
    label: str
    refs: tuple          # 1-based indices into RawDossier.references

    def __post_init__(self):
        if self.category not in CATEGORIES:
            raise ValueError(f"unknown category: {self.category}")
        if self.label not in LABELS:
            raise ValueError(f"unknown label: {self.label}")


@dataclass(frozen=True)
class RawDossier:
    taxon: str
    detected_by: str
    claims: tuple
    references: tuple    # ordered Citation objects WE retrieved from NCBI


@dataclass(frozen=True)
class Dossier:
    taxon: str
    detected_by: str
    claims: tuple
    references: tuple
    dropped_refs: int


def resolve_citations(raw: RawDossier):
    """Rule 1: the model cites by NUMBER into a list we supplied.

    It never sees a free-form identifier, so it cannot invent a plausible one. A number
    outside 1..len(references) is not evidence — it is dropped and counted.
    Returns (cleaned RawDossier, how many references were dropped).
    """
    n = len(raw.references)
    dropped = 0
    kept = []
    for c in raw.claims:
        good = tuple(i for i in c.refs if isinstance(i, int) and 1 <= i <= n)
        dropped += len(c.refs) - len(good)
        kept.append(replace(c, refs=good))
    return replace(raw, claims=tuple(kept)), dropped
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_core.py -v`
Expected: PASS, 11 test

- [ ] **Step 5: Commit**

```bash
git add steps/_biomni_core.py tests/test_biomni_core.py
git commit -m "feat(phase-c): cite by number into a reference list we control"
```

---

## Task 3: Verifica dei PMID su NCBI (regola anti-invenzione 2)

**Files:**
- Modify: `steps/_biomni_core.py`
- Modify: `tests/test_biomni_core.py`

**Interfaces:**
> 🔄 **Ruolo cambiato dopo lo spike.** `verify_pmids` non serve più *a valle* per controllare
> quello che ha detto il modello (ora il modello cita per numero e non vede PMID). Serve **a
> monte**, quando il client costruisce l'elenco delle fonti: un PMID trovato da `esearch` entra
> nell'elenco **solo se** `esummary` restituisce titolo e anno. La funzione e i suoi test
> restano identici; cambia solo chi la chiama (il client del Task 8, non `build_dossier`).

- Consumes: `Citation` dal Task 2.
- Produces: `verify_pmids(pmids: set, fetch) -> tuple[dict, list]`. `fetch(pmid) -> Citation | None`: viene iniettata, così i test non toccano la rete. Ritorna `({pmid: Citation}, [pmid_scartati])`.

- [ ] **Step 1: Scrivere il test che fallisce**

Aggiungere in `tests/test_biomni_core.py`:

```python
REAL = {
    "111": core.Citation("111", "Sakacin production in Latilactobacillus sakei", "2019"),
    "222": core.Citation("222", "Biogenic amines in dry sausage", "2021"),
}


def _fetch(pmid):
    return REAL.get(pmid)


def test_existing_pmids_are_confirmed():
    ok, dropped = core.verify_pmids({"111", "222"}, _fetch)
    assert set(ok) == {"111", "222"}
    assert dropped == []


def test_nonexistent_pmid_is_dropped():
    ok, dropped = core.verify_pmids({"111", "404404"}, _fetch)
    assert set(ok) == {"111"}
    assert dropped == ["404404"]


def test_network_failure_drops_rather_than_confirms():
    def boom(pmid):
        raise OSError("network down")

    ok, dropped = core.verify_pmids({"111"}, boom)
    assert ok == {}
    assert dropped == ["111"]
```

- [ ] **Step 2: Eseguire i test e verificare che falliscano**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_core.py -k verify -v`
Expected: FAIL con `AttributeError: module '_biomni_core' has no attribute 'verify_pmids'`

- [ ] **Step 3: Scrivere l'implementazione minima**

Aggiungere in `steps/_biomni_core.py`:

```python
def verify_pmids(pmids, fetch):
    """Rule 2: re-check every PMID against NCBI. Anything we cannot confirm is DROPPED.

    `fetch(pmid)` returns a Citation or None; it is injected so tests never hit the network.
    A network error drops the citation: silence is not confirmation.
    """
    confirmed = {}
    dropped = []
    for pmid in sorted(pmids):
        try:
            cit = fetch(pmid)
        except Exception:
            cit = None
        if cit is None or not cit.title:
            dropped.append(pmid)
        else:
            confirmed[pmid] = cit
    return confirmed, dropped
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_core.py -v`
Expected: PASS, 12 test

- [ ] **Step 5: Commit**

```bash
git add steps/_biomni_core.py tests/test_biomni_core.py
git commit -m "feat(phase-c): verify every PMID against NCBI, drop what cannot be confirmed"
```

---

## Task 4: Etichettatura e declassamento automatico (regola anti-invenzione 3)

**Files:**
- Modify: `steps/_biomni_core.py`
- Modify: `tests/test_biomni_core.py`

**Interfaces:**
> 🔄 **Aggiornato dopo lo spike.** Le firme cambiano perché la prova non è più «un PMID
> verificato» ma «almeno un numero di riferimento valido»:
> `apply_labels(claims: tuple) -> tuple` e `build_dossier(raw: RawDossier) -> Dossier`
> (niente più `fetch`: le fonti arrivano già verificate dal client). Il codice qui sotto è già
> nella forma nuova. La logica di declassamento è invariata.

- Consumes: `Claim` (Task 2), `resolve_citations` (Task 2).
- Produces: `apply_labels(claims: tuple) -> tuple`, `build_dossier(raw: RawDossier) -> Dossier`.

- [ ] **Step 1: Scrivere il test che fallisce**

Aggiungere in `tests/test_biomni_core.py`:

```python
def test_noto_without_verified_citation_is_demoted():
    claims = (core.Claim("batteriocine", "sakacina", "noto", ()),)
    out = core.apply_labels(claims, verified=set())
    assert out[0].label == "ipotesi"


def test_assente_without_verified_citation_is_demoted():
    claims = (core.Claim("ammine_biogene", "nessuna hdc", "assente", ("999",)),)
    out = core.apply_labels(claims, verified={"111"})
    assert out[0].label == "ipotesi"


def test_noto_with_verified_citation_survives():
    claims = (core.Claim("batteriocine", "sakacina", "noto", ("111",)),)
    out = core.apply_labels(claims, verified={"111"})
    assert out[0].label == "noto"


def test_atteso_is_left_alone_even_without_citations():
    claims = (core.Claim("cazymes", "inferito dal genere", "atteso", ()),)
    out = core.apply_labels(claims, verified=set())
    assert out[0].label == "atteso"


def test_build_dossier_runs_all_the_rules():
    raw = core.RawDossier(
        taxon="Latilactobacillus sakei",
        detected_by="metaphlan+kraken",
        claims=(
            core.Claim("batteriocine", "sakacina", "noto", (1,)),
            core.Claim("resistoma", "tet(M)", "noto", (9,)),
        ),
        references=REFS,
    )
    d = core.build_dossier(raw)
    assert d.claims[0].label == "noto"
    assert d.claims[1].label == "ipotesi"
    assert d.dropped_refs == 1
    assert d.references == REFS
```

- [ ] **Step 2: Eseguire i test e verificare che falliscano**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_core.py -k "label or build_dossier" -v`
Expected: FAIL con `AttributeError: module '_biomni_core' has no attribute 'apply_labels'`

- [ ] **Step 3: Scrivere l'implementazione minima**

Aggiungere in `steps/_biomni_core.py`:

```python
def apply_labels(claims):
    """Rule 3: 'noto' and 'assente' require at least one SURVIVING reference number.

    Without one the claim is rewritten to 'ipotesi', whatever the model answered.
    'atteso' is an explicit inference and needs no citation.
    """
    out = []
    for c in claims:
        if c.label in ("noto", "assente") and not c.refs:
            out.append(replace(c, label="ipotesi"))
        else:
            out.append(c)
    return tuple(out)


def build_dossier(raw: RawDossier) -> Dossier:
    """Apply the anti-invention rules in order and return a finished Dossier.

    The references were retrieved and verified by the client BEFORE the model saw them,
    so there is nothing left to fetch here: resolve the numbers, then demote what has no
    surviving reference.
    """
    resolved, dropped = resolve_citations(raw)
    return Dossier(
        taxon=resolved.taxon,
        detected_by=resolved.detected_by,
        claims=apply_labels(resolved.claims),
        references=resolved.references,
        dropped_refs=dropped,
    )
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_core.py -v`
Expected: PASS, 17 test

- [ ] **Step 5: Commit**

```bash
git add steps/_biomni_core.py tests/test_biomni_core.py
git commit -m "feat(phase-c): demote unproven claims to hypothesis automatically"
```

---

## Task 5: Rendering di dossier, tabella e provenienza

**Files:**
- Modify: `steps/_biomni_core.py`
- Modify: `tests/test_biomni_core.py`

**Interfaces:**
- Consumes: `Dossier` (Task 4).
- Produces: `render_markdown(dossiers: list, meta: dict) -> str`, `render_tsv(dossiers: list) -> str`. `meta` contiene le chiavi `model`, `provider`, `date`, `n_taxa`, `confirmed`, `dropped`.

- [ ] **Step 1: Scrivere il test che fallisce**

Aggiungere in `tests/test_biomni_core.py`:

```python
META = {
    "model": "gpt-4o", "provider": "OpenAI", "date": "2026-08-06",
    "n_taxa": 1, "confirmed": 1, "dropped": 1,
}


def _one_dossier():
    raw = core.RawDossier(
        taxon="Latilactobacillus sakei",
        detected_by="metaphlan+kraken",
        claims=(core.Claim("batteriocine", "sakacina", "noto", (1,)),
                core.Claim("resistoma", "tet(M)", "noto", (9,))),
        references=(core.Citation("111", "Sakacin production", "2019"),),
    )
    return core.build_dossier(raw)


def test_markdown_header_declares_the_llm_and_the_counts():
    md = core.render_markdown([_one_dossier()], META)
    head = md.split("## ")[0]
    assert "LLM" in head
    assert "gpt-4o" in head and "OpenAI" in head
    assert "1" in head


def test_markdown_never_leaks_a_dropped_pmid_as_evidence():
    md = core.render_markdown([_one_dossier()], META)
    assert "PMID 111" in md
    assert "PMID 999" not in md


def test_tsv_has_one_row_per_claim_and_the_right_header():
    tsv = core.render_tsv([_one_dossier()])
    lines = tsv.strip().split("\n")
    assert lines[0].split("\t") == [
        "taxon", "rilevato_da", "categoria", "affermazione",
        "etichetta", "citazioni_verificate",
    ]
    assert len(lines) == 3


def test_tsv_marks_the_demoted_claim_as_ipotesi():
    tsv = core.render_tsv([_one_dossier()])
    assert "\tipotesi\t" in tsv
```

- [ ] **Step 2: Eseguire i test e verificare che falliscano**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_core.py -k "markdown or tsv" -v`
Expected: FAIL con `AttributeError: module '_biomni_core' has no attribute 'render_markdown'`

- [ ] **Step 3: Scrivere l'implementazione minima**

Aggiungere in `steps/_biomni_core.py`:

```python
_HEADER = (
    "> ATTENZIONE: documento generato da un modello linguistico (LLM), non da un esperto.\n"
    "> Modello: {model} ({provider}) · Data: {date} · Taxa analizzati: {n_taxa}\n"
    "> Citazioni ricontrollate su NCBI: {confirmed} confermate, {dropped} scartate.\n"
    "> Le righe \"atteso\" e \"ipotesi\" NON sono prove. Vanno verificate a mano.\n\n"
)


def _pmids(claim, references):
    """Map surviving 1-based reference numbers back to the PMIDs we retrieved."""
    return [references[i - 1].pmid for i in claim.refs]


def render_markdown(dossiers, meta) -> str:
    """Human-readable dossier. Only references WE retrieved are ever printed as evidence."""
    parts = [_HEADER.format(**meta)]
    for d in dossiers:
        parts.append(f"## {d.taxon}\n")
        parts.append(f"Rilevato da: {d.detected_by}\n\n")
        for c in d.claims:
            proof = _pmids(c, d.references)
            refs = "  [" + "; ".join(f"PMID {p}" for p in proof) + "]" if proof else ""
            parts.append(f"- {c.category}: {c.statement}  ({c.label}){refs}\n")
        if d.references:
            parts.append("\nFonti consultate:\n")
            for i, cit in enumerate(d.references, 1):
                parts.append(f"  [{i}] PMID {cit.pmid} — {cit.title} ({cit.year})\n")
        parts.append("\n")
    return "".join(parts)


def render_tsv(dossiers) -> str:
    """Machine-readable dossier: one row per claim."""
    rows = ["taxon\trilevato_da\tcategoria\taffermazione\tetichetta\tcitazioni_verificate"]
    for d in dossiers:
        for c in d.claims:
            proof = ";".join(_pmids(c, d.references))
            rows.append(f"{d.taxon}\t{d.detected_by}\t{c.category}\t{c.statement}\t{c.label}\t{proof}")
    return "\n".join(rows) + "\n"
```

> 🔄 **Test di questo task, aggiornati dopo lo spike.** In `_one_dossier()` costruire il
> `RawDossier` con `references=REFS` e claim con `refs=(1,)` e `refs=(9,)`, e chiamare
> `core.build_dossier(raw)` senza `_fetch`. Le asserzioni restano le stesse: `PMID 111`
> presente, `PMID 999` assente, header con modello e conteggi, TSV con `\tipotesi\t`.
> In più: `assert "Fonti consultate" in md`.

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_core.py -v`
Expected: PASS, 21 test

- [ ] **Step 5: Commit**

```bash
git add steps/_biomni_core.py tests/test_biomni_core.py
git commit -m "feat(phase-c): render dossier markdown and TSV with provenance header"
```

---

## Task 6: Riconoscimento fornitore e cancello di consenso

**Files:**
- Create: `steps/_biomni_consent.py`
- Create: `tests/test_biomni_consent.py`

**Interfaces:**
- Consumes: niente.
- Produces: `Provider`, `provider_for`, `consent_record_path`, `consent_is_valid`, `save_consent`.

- [ ] **Step 1: Scrivere il test che fallisce**

Creare `tests/test_biomni_consent.py`:

```python
# -*- coding: utf-8 -*-
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "steps"))
import _biomni_consent as cs  # noqa: E402


def test_provider_is_detected_from_the_model_name():
    assert cs.provider_for("gpt-4o").env_var == "OPENAI_API_KEY"
    assert cs.provider_for("claude-sonnet-5").env_var == "ANTHROPIC_API_KEY"
    assert cs.provider_for("gemini-2.0-pro").env_var == "GEMINI_API_KEY"


def test_local_model_needs_no_key():
    p = cs.provider_for("ollama/llama3.1")
    assert p.local is True
    assert p.env_var == ""


def test_unknown_model_raises_instead_of_guessing():
    try:
        cs.provider_for("supermodello-3000")
    except ValueError:
        return
    raise AssertionError("an unknown model must not be silently accepted")


def test_consent_is_valid_only_for_the_same_model_and_provider(tmp_path):
    path = cs.consent_record_path(str(tmp_path))
    p = cs.provider_for("gpt-4o")
    cs.save_consent(path, "gpt-4o", p, n_taxa=5)
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert cs.consent_is_valid(rec, "gpt-4o", p) is True
    assert cs.consent_is_valid(rec, "claude-sonnet-5", cs.provider_for("claude-sonnet-5")) is False


def test_missing_consent_is_not_valid():
    assert cs.consent_is_valid(None, "gpt-4o", cs.provider_for("gpt-4o")) is False


def test_consent_record_never_contains_a_key(tmp_path):
    path = cs.consent_record_path(str(tmp_path))
    cs.save_consent(path, "gpt-4o", cs.provider_for("gpt-4o"), n_taxa=5)
    text = path.read_text(encoding="utf-8").lower()
    assert "key" not in text and "sk-" not in text
```

- [ ] **Step 2: Eseguire i test e verificare che falliscano**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_consent.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named '_biomni_consent'`

- [ ] **Step 3: Scrivere l'implementazione minima**

Creare `steps/_biomni_consent.py`:

```python
# -*- coding: utf-8 -*-
# steps/_biomni_consent.py - provider detection, consent gate and credential handling
# for Phase C. No Biomni import: fully testable offline.
# Conda env: pmn_reports_py. Not meant to be run directly.
import json
import pathlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    env_var: str
    console_url: str
    local: bool


_PROVIDERS = (
    (("claude-",), Provider("anthropic", "Anthropic", "ANTHROPIC_API_KEY",
                            "https://console.anthropic.com/settings/keys", False)),
    (("gpt-", "o1-", "o3-"), Provider("openai", "OpenAI", "OPENAI_API_KEY",
                                      "https://platform.openai.com/api-keys", False)),
    (("gemini-",), Provider("google", "Google", "GEMINI_API_KEY",
                            "https://aistudio.google.com/apikey", False)),
    (("groq/",), Provider("groq", "Groq", "GROQ_API_KEY",
                          "https://console.groq.com/keys", False)),
    (("azure/",), Provider("azure", "Azure OpenAI", "AZURE_OPENAI_API_KEY",
                           "https://portal.azure.com", False)),
    (("bedrock/",), Provider("bedrock", "AWS Bedrock", "AWS_SECRET_ACCESS_KEY",
                             "https://console.aws.amazon.com/iam", False)),
    (("ollama/",), Provider("ollama", "Ollama (locale)", "", "https://ollama.com/download", True)),
)


def provider_for(llm: str) -> Provider:
    """Map a model name to its provider. Refuses to guess on an unknown name."""
    name = (llm or "").strip().lower()
    for prefixes, provider in _PROVIDERS:
        if any(name.startswith(p) for p in prefixes):
            return provider
    raise ValueError(
        f"unknown model '{llm}': use claude-*, gpt-*, gemini-*, groq/*, azure/*, "
        "bedrock/* or ollama/*"
    )


def consent_record_path(work_dir: str) -> pathlib.Path:
    return pathlib.Path(work_dir) / ".biomni_consent.json"


def consent_is_valid(record, llm: str, provider: Provider) -> bool:
    """Consent is tied to the exact model AND provider: change either and we ask again."""
    if not record:
        return False
    return record.get("llm") == llm and record.get("provider") == provider.key


def save_consent(path, llm: str, provider: Provider, n_taxa: int) -> None:
    """Record the consent. NEVER stores an API key."""
    from datetime import date
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"llm": llm, "provider": provider.key, "date": date.today().isoformat(),
             "authorised": "species names only", "n_taxa": n_taxa},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_consent.py -v`
Expected: PASS, 6 test

- [ ] **Step 5: Commit**

```bash
git add steps/_biomni_consent.py tests/test_biomni_consent.py
git commit -m "feat(phase-c): detect the provider from the model name and gate on consent"
```

---

## Task 7: Procedura guidata per la chiave API

**Files:**
- Modify: `steps/_biomni_consent.py`
- Modify: `tests/test_biomni_consent.py`

**Interfaces:**
- Consumes: `Provider` (Task 6).
- Produces: `credentials_path()`, `read_credentials(path) -> dict`, `store_credential(path, env_var, value)`, `resolve_api_key(provider, environ, path) -> str | None`, `translate_provider_error(status) -> str`.

- [ ] **Step 1: Scrivere il test che fallisce**

Aggiungere in `tests/test_biomni_consent.py`:

```python
import stat


def test_environment_wins_over_the_credentials_file(tmp_path):
    path = tmp_path / "credentials"
    cs.store_credential(path, "OPENAI_API_KEY", "from-file")
    p = cs.provider_for("gpt-4o")
    got = cs.resolve_api_key(p, {"OPENAI_API_KEY": "from-env"}, path)
    assert got == "from-env"


def test_credentials_file_is_used_when_the_environment_is_empty(tmp_path):
    path = tmp_path / "credentials"
    cs.store_credential(path, "OPENAI_API_KEY", "from-file")
    got = cs.resolve_api_key(cs.provider_for("gpt-4o"), {}, path)
    assert got == "from-file"


def test_a_local_model_needs_no_key_at_all(tmp_path):
    got = cs.resolve_api_key(cs.provider_for("ollama/llama3.1"), {}, tmp_path / "nope")
    assert got == ""


def test_a_world_readable_credentials_file_is_refused(tmp_path):
    if os.name != "posix":
        return  # POSIX permissions are not enforceable on Windows
    path = tmp_path / "credentials"
    cs.store_credential(path, "OPENAI_API_KEY", "secret")
    os.chmod(path, 0o644)
    try:
        cs.read_credentials(path)
    except PermissionError:
        return
    raise AssertionError("a world-readable credentials file must be refused")


def test_store_credential_writes_0600_on_posix(tmp_path):
    if os.name != "posix":
        return
    path = tmp_path / "credentials"
    cs.store_credential(path, "OPENAI_API_KEY", "secret")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_provider_errors_are_translated_into_plain_language():
    assert "valida" in cs.translate_provider_error(401)
    assert "credito" in cs.translate_provider_error(429)
    assert "raggiungere" in cs.translate_provider_error(None)
```

- [ ] **Step 2: Eseguire i test e verificare che falliscano**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_consent.py -k "credential or key or error" -v`
Expected: FAIL con `AttributeError: module '_biomni_consent' has no attribute 'store_credential'`

- [ ] **Step 3: Scrivere l'implementazione minima**

Aggiungere `import os` e `import stat as _stat` **agli import in cima al file** (non a metà), poi aggiungere in fondo a `steps/_biomni_consent.py`:

```python
def credentials_path() -> pathlib.Path:
    return pathlib.Path.home() / ".pmn" / "credentials"


def read_credentials(path) -> dict:
    """Read VAR=value lines. On POSIX a file wider than 0600 is REFUSED, not fixed."""
    path = pathlib.Path(path)
    if not path.exists():
        return {}
    if os.name == "posix":
        mode = _stat.S_IMODE(os.stat(path).st_mode)
        if mode != 0o600:
            raise PermissionError(
                f"{path} has permissions {oct(mode)}; expected 0600. "
                f"Fix it with: chmod 600 {path}"
            )
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def store_credential(path, env_var: str, value: str) -> None:
    """Write/replace one VAR=value line, 0600 on POSIX."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if path.exists():
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                 if not ln.strip().startswith(f"{env_var}=")]
    lines.append(f"{env_var}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if os.name == "posix":
        os.chmod(path, 0o600)


def resolve_api_key(provider: Provider, environ, path):
    """Environment first, credentials file second. Local models need no key ('')."""
    if provider.local:
        return ""
    from_env = (environ or {}).get(provider.env_var, "")
    if from_env:
        return from_env
    return read_credentials(path).get(provider.env_var) or None


def translate_provider_error(status) -> str:
    """Turn a provider HTTP status into something a non-programmer can act on."""
    if status in (401, 403):
        return ("La chiave non è valida. Forse è incompleta o è stata revocata: "
                "creane una nuova e reincollala.")
    if status in (402, 429):
        return ("La chiave è valida ma l'account non ha credito o un metodo di pagamento "
                "attivo. Controlla la sezione fatturazione del fornitore.")
    return ("Non riesco a raggiungere il fornitore: controlla la connessione a internet "
            "o le impostazioni del proxy.")
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_consent.py -v`
Expected: PASS, 12 test

- [ ] **Step 5: Commit**

```bash
git add steps/_biomni_consent.py tests/test_biomni_consent.py
git commit -m "feat(phase-c): guided API key setup with 0600 storage and plain-language errors"
```

---

## Task 8: Il passo eseguibile e l'adattatore Biomni

Questo è l'unico task che tocca l'API reale di Biomni. Le firme esatte vanno prese dai **findings del Task 0**.

**Files:**
- Create: `steps/50_biomni_dossier.py`
- Create: `tests/test_biomni_cli.py`

**Interfaces:**
- Consumes: tutto `_biomni_core` (Task 1-5) e tutto `_biomni_consent` (Task 6-7).
- Produces: eseguibile `50_biomni_dossier.py` con le opzioni `--metaphlan`, `--kraken`, `--out`, `--llm`, `--work-dir`, `--threshold-pct`, `--max-taxa`, `--dry-run`, `--yes-send-taxa`. Scrive `dossier_taxa.md`, `dossier_taxa.tsv`, `run_meta.json`.

- [ ] **Step 1: Scrivere il test che fallisce**

Creare `tests/test_biomni_cli.py`:

```python
# -*- coding: utf-8 -*-
import importlib.util
import json
import os
import sys

STEPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "steps")
sys.path.insert(0, STEPS)
_spec = importlib.util.spec_from_file_location("step50", os.path.join(STEPS, "50_biomni_dossier.py"))
step50 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(step50)

import _biomni_core as core  # noqa: E402

MPA = """clade_name\tS1
k__Bacteria|s__Latilactobacillus_sakei\t40.0
k__Bacteria|s__Staphylococcus_xylosus\t5.0
"""


class FakeClient:
    """Stands in for Biomni: fixed answers, zero cost, no network.

    One claim cites reference [1] (which exists) and one cites [9] (which does not) — so every
    run exercises both the surviving path and the automatic demotion to 'ipotesi'.
    """
    def __init__(self):
        self.asked = []

    def ask(self, taxon, detected_by):
        self.asked.append(taxon)
        return core.RawDossier(
            taxon=taxon, detected_by=detected_by,
            claims=(core.Claim("batteriocine", "sakacina", "noto", (1,)),
                    core.Claim("resistoma", "tet(M)", "noto", (9,))),
            references=(core.Citation("111", "Sakacin production", "2019"),),
        )


def _tables(tmp_path):
    m = tmp_path / "merged.txt"
    m.write_text(MPA, encoding="utf-8")
    return str(m)


def _run(tmp_path, client=None, **kw):
    """Hermetic call: cred_path always points inside tmp_path, never at the real home."""
    opts = dict(metaphlan=_tables(tmp_path), kraken="", out=str(tmp_path / "o"),
                llm="gpt-4o", work_dir=str(tmp_path), threshold_pct=0.001, max_taxa=5,
                dry_run=False, assume_yes=False, client=client or FakeClient(),
                environ={"OPENAI_API_KEY": "x"}, interactive=False,
                cred_path=tmp_path / "creds")
    opts.update(kw)
    return step50.run(**opts)


def test_dry_run_sends_nothing_and_needs_no_consent(tmp_path, capsys):
    client = FakeClient()
    assert _run(tmp_path, client=client, dry_run=True) == 0
    assert client.asked == []
    assert "Latilactobacillus sakei" in capsys.readouterr().out


def test_without_consent_and_without_a_terminal_it_stops(tmp_path):
    client = FakeClient()
    assert _run(tmp_path, client=client) != 0
    assert client.asked == []


def test_with_yes_flag_it_runs_and_writes_all_three_files(tmp_path):
    out = tmp_path / "o"
    assert _run(tmp_path, assume_yes=True) == 0
    assert (out / "dossier_taxa.md").exists()
    assert (out / "dossier_taxa.tsv").exists()
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["confirmed"] == 2 and meta["dropped"] == 2


def test_max_taxa_is_respected(tmp_path):
    client = FakeClient()
    _run(tmp_path, client=client, assume_yes=True, max_taxa=1)
    assert len(client.asked) == 1


def test_a_missing_key_stops_before_any_request(tmp_path):
    client = FakeClient()
    assert _run(tmp_path, client=client, assume_yes=True, environ={}) != 0
    assert client.asked == []


def test_the_key_never_appears_in_the_output(tmp_path):
    out = tmp_path / "o"
    _run(tmp_path, assume_yes=True, environ={"OPENAI_API_KEY": "sk-supersegreta"})
    for name in ("dossier_taxa.md", "dossier_taxa.tsv", "run_meta.json"):
        assert "sk-supersegreta" not in (out / name).read_text(encoding="utf-8")


def test_the_prompt_states_the_cost_and_a_no_sends_nothing(tmp_path):
    client, seen = FakeClient(), []
    rc = _run(tmp_path, client=client, interactive=True,
              ask=lambda _p: "n", show=seen.append)
    assert rc == 0
    assert client.asked == []
    assert any("COSTA SOLDI" in s for s in seen)


def test_a_yes_at_the_prompt_records_the_consent_once(tmp_path):
    client = FakeClient()
    _run(tmp_path, client=client, interactive=True, ask=lambda _p: "s", show=lambda _s: None)
    assert len(client.asked) == 2
    assert (tmp_path / ".biomni_consent.json").exists()
```

- [ ] **Step 2: Eseguire i test e verificare che falliscano**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_cli.py -v`
Expected: FAIL con `FileNotFoundError` su `steps/50_biomni_dossier.py`

- [ ] **Step 3: Scrivere l'implementazione minima**

Creare `steps/50_biomni_dossier.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# steps/50_biomni_dossier.py - Phase C: build a per-taxon dossier via a Biomni A1 agent.
# Conda env: pmn_biomni (biomni + pandas). OPTIONAL step, off by default.
#
# Only NORMALIZED SPECIES NAMES ever leave the machine. No samples, no SRR, no paths,
# no abundances, no reads. Consent is asked once per project and recorded in
# <work-dir>/.biomni_consent.json. API keys are read from the environment or from
# ~/.pmn/credentials and are never written to any output.
#
# Usage:
#   50_biomni_dossier.py [--metaphlan MERGED.txt] [--kraken MATRIX.tsv] --out DIR
#                        --llm MODEL --work-dir DIR [--threshold-pct 0.001]
#                        [--max-taxa 5] [--dry-run] [--yes-send-taxa]
import argparse
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _biomni_core as core          # noqa: E402
import _biomni_consent as consent    # noqa: E402


def _fail(msg: str) -> int:
    print(f"[FAIL] {msg}", file=sys.stderr)
    return 1


def _ask_consent(llm, provider, taxa, ask, show):
    """Show exactly what is about to leave, say that it costs, and require an explicit yes."""
    if provider.local:
        show(f"\n  Fase C · Biomni — modello LOCALE\n"
             f"  Modello : {llm}  (gira sul tuo computer)\n"
             f"  Costo   : ZERO\n"
             f"  Dati    : NON escono dal tuo computer\n"
             f"  Nota    : su questo compito un modello locale sbaglia più di uno grande.\n")
    else:
        show(f"\n  Fase C · Biomni — ATTENZIONE: QUESTA OPERAZIONE TI COSTA SOLDI\n"
             f"  Modello scelto da TE : {llm}  ({provider.label})\n"
             f"  Chi paga             : TU, con la tua {provider.env_var}\n"
             f"  Quanto costa         : NON è prevedibile in anticipo.\n"
             f"                         L'agente ragiona a più passaggi.\n"
             f"  Esce dal tuo PC      : {len(taxa)} nomi di specie\n"
             f"  NON esce             : campioni, SRR, path, abbondanze, FASTQ\n"
             f"  Alternativa gratuita : un modello locale (ollama/...), costo zero,\n"
             f"                         nessun dato fuori, ma sbaglia di più.\n")
    return ask("  Procedo, e accetto il costo? [s/N] ").strip().lower() in ("s", "si", "sì", "y")


def run(metaphlan, kraken, out, llm, work_dir, threshold_pct, max_taxa,
        dry_run, assume_yes, client, environ, interactive,
        cred_path=None, ask=input, show=print):
    """Everything is injected (client, environ, interactive, cred_path, ask, show)
    so tests are hermetic and cost nothing."""
    try:
        provider = consent.provider_for(llm)
    except ValueError as e:
        return _fail(str(e))

    taxa = core.select_taxa(metaphlan, kraken, threshold_pct, max_taxa)
    if not taxa:
        return _fail("no taxa above the abundance threshold: nothing to do")

    if dry_run:
        print(f"DRY-RUN: {len(taxa)} species would be sent to {llm} ({provider.label}).")
        print("Nothing else leaves this machine. Species:")
        for name, _src in taxa:
            print(f"  - {name}")
        return 0

    key = consent.resolve_api_key(provider, environ, cred_path or consent.credentials_path())
    if key is None:
        return _fail(
            f"no API key for {provider.label}. Set {provider.env_var} in your environment, "
            f"or create one at {provider.console_url}"
        )

    rec_path = consent.consent_record_path(work_dir)
    record = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.exists() else None
    if not consent.consent_is_valid(record, llm, provider):
        if assume_yes:
            consent.save_consent(rec_path, llm, provider, len(taxa))
        elif not interactive:
            return _fail(
                "Phase C needs your consent before any species name leaves this machine, "
                "and there is no terminal to ask on. Re-run with --yes-send-taxa."
            )
        elif _ask_consent(llm, provider, taxa, ask, show):
            consent.save_consent(rec_path, llm, provider, len(taxa))
        else:
            show("  Nessun problema: non è stato inviato niente.")
            return 0

    dossiers, confirmed, dropped = [], 0, 0
    for name, src in taxa:
        d = core.build_dossier(client.ask(name, src))
        dossiers.append(d)
        confirmed += len(d.references)
        dropped += d.dropped_refs

    meta = {"model": llm, "provider": provider.label, "date": date.today().isoformat(),
            "n_taxa": len(dossiers), "confirmed": confirmed, "dropped": dropped,
            "max_taxa": max_taxa, "threshold_pct": threshold_pct}

    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "dossier_taxa.md"), "w", encoding="utf-8") as f:
        f.write(core.render_markdown(dossiers, meta))
    with open(os.path.join(out, "dossier_taxa.tsv"), "w", encoding="utf-8") as f:
        f.write(core.render_tsv(dossiers))
    with open(os.path.join(out, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"[OK] {len(dossiers)} dossiers written to {out} "
          f"({confirmed} citations confirmed, {dropped} dropped)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase C: per-taxon dossier via Biomni.")
    ap.add_argument("--metaphlan", default="", help="merged MetaPhlAn table (optional)")
    ap.add_argument("--kraken", default="", help="Kraken/Bracken matrix TSV (optional)")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--llm", required=True, help="model name, e.g. gpt-4o or ollama/llama3.1")
    ap.add_argument("--work-dir", required=True, help="where the consent record lives")
    ap.add_argument("--threshold-pct", type=float, default=0.001)
    ap.add_argument("--max-taxa", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes-send-taxa", action="store_true")
    a = ap.parse_args()
    if not a.metaphlan and not a.kraken:
        return _fail("provide at least one of --metaphlan / --kraken")

    from _biomni_client import BiomniClient  # imported late: heavy dependency
    return run(a.metaphlan, a.kraken, a.out, a.llm, a.work_dir, a.threshold_pct,
               a.max_taxa, a.dry_run, a.yes_send_taxa,
               BiomniClient(a.llm), os.environ, sys.stdin.isatty())


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `conda run -n pmn_reports_py python -m pytest tests/test_biomni_cli.py -v`
Expected: PASS, 8 test

- [ ] **Step 5: Scrivere l'adattatore reale**

Creare `steps/_biomni_client.py`. Le firme esatte di `A1.__init__` e `go()` sono nei findings
del Task 0 (§Q2): **leggerle da lì e usarle verbatim**, non fidarsi di questo scheletro.

> 🔄 **Riscritto dopo lo spike.** `query_pubmed` di Biomni **non restituisce il PMID**, quindi
> la ricerca la facciamo noi: `esearch` → `esummary` → elenco numerato → il modello legge e
> cita per numero. Il modello non vede mai un identificativo in forma libera.

```python
# -*- coding: utf-8 -*-
# steps/_biomni_client.py - the ONLY module that talks to Biomni and to NCBI over the network.
# Conda env: pmn_biomni. Imported late by 50_biomni_dossier.py so the pure logic stays testable.
#
# We do the literature search ourselves. Biomni's query_pubmed searches PubMed for real but
# returns only Title/Abstract/Journal - the PMID never appears in its return value, which would
# make every citation untraceable. So: esearch -> esummary -> a NUMBERED reference list handed
# to the agent, which cites by number and never sees a free-form identifier.
import json
import urllib.parse
import urllib.request

import _biomni_core as core

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_DOMAIN = '("fermented meat"[tiab] OR sausage[tiab] OR salami[tiab] OR "dry-cured"[tiab])'

_PROMPT = """You are given ONE microbial species: "{taxon}", and a NUMBERED list of papers.
Use ONLY these papers as evidence. Do not use any other source.

{refs}

Return ONLY valid JSON, no prose, with this exact shape:
{{"claims":[{{"category":"ruolo|batteriocine|ammine_biogene|cazymes|resistoma|virulenza",
"statement":"one short sentence","label":"noto|assente|atteso","refs":[1,3]}}]}}

Rules:
- "refs" holds NUMBERS from the list above. Never write a PubMed ID or a DOI.
- Use label "noto" or "assente" ONLY when a listed paper supports it, and cite its number.
- With no supporting paper, use label "atteso" (inference from the genus) and "refs": [].
"""


def pubmed_search(taxon: str, retmax: int = 12):
    """esearch restricted to the fermented-meat domain. Returns a list of PMID strings."""
    term = f'"{taxon}"[tiab] AND {_DOMAIN}'
    url = (f"{_EUTILS}/esearch.fcgi?db=pubmed&retmode=json&retmax={int(retmax)}"
           f"&term={urllib.parse.quote(term)}")
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.load(r)
    return list(data.get("esearchresult", {}).get("idlist", []))


def ncbi_fetch(pmid: str):
    """esummary for one PMID. Returns a Citation, or None when NCBI has no usable record."""
    url = (f"{_EUTILS}/esummary.fcgi?db=pubmed&retmode=json&id={urllib.parse.quote(pmid)}")
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.load(r)
    rec = data.get("result", {}).get(pmid)
    if not rec or not rec.get("title"):
        return None
    return core.Citation(pmid, rec["title"], (rec.get("pubdate", "") or "")[:4])


def build_references(taxon: str):
    """Search, then keep only the PMIDs esummary can actually confirm (Task 3's rule 2)."""
    confirmed, _dropped = core.verify_pmids(set(pubmed_search(taxon)), ncbi_fetch)
    return tuple(sorted(confirmed.values(), key=lambda c: (c.year, c.pmid), reverse=True))


def _extract_json(text: str) -> str:
    """A1 may wrap the JSON in prose or a fence; take the outermost object."""
    s, e = text.find("{"), text.rfind("}")
    if s < 0 or e <= s:
        raise ValueError("the model did not return JSON")
    return text[s:e + 1]


class BiomniClient:
    def __init__(self, llm: str, data_path: str = ""):
        from biomni.agent import A1
        self._agent = A1(path=data_path or "./biomni_data", llm=llm)

    def ask(self, taxon: str, detected_by: str) -> core.RawDossier:
        refs = build_references(taxon)
        listing = "\n".join(
            f"[{i}] {c.title} ({c.year})" for i, c in enumerate(refs, 1)
        ) or "(no papers found for this species in this domain)"
        answer = self._agent.go(_PROMPT.format(taxon=taxon, refs=listing))
        payload = json.loads(_extract_json(answer))
        claims = tuple(
            core.Claim(c["category"], c["statement"], c["label"],
                       tuple(i for i in c.get("refs", []) if isinstance(i, int)))
            for c in payload.get("claims", [])
            if c.get("category") in core.CATEGORIES and c.get("label") in core.LABELS
        )
        return core.RawDossier(taxon, detected_by, claims, refs)
```

- [ ] **Step 6: Commit**

```bash
git add steps/50_biomni_dossier.py steps/_biomni_client.py tests/test_biomni_cli.py
git commit -m "feat(phase-c): runnable step with injected client, plus the real Biomni adapter"
```

---

## Task 9: Integrazione nella pipeline

**Files:**
- Modify: `bin/lib/parse_config.py:74` (dopo `PMN_GROUP_COL`)
- Modify: `bin/lib/validate.sh`
- Modify: `bin/lib/requirements.sh`
- Modify: `bin/preflight.sh`
- Modify: `bin/run.sh:19-40` (parsing opzioni) e in coda (blocco Fase C)
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `steps/50_biomni_dossier.py` (Task 8).
- Produces: variabili shell `PMN_BIOMNI_ON`, `PMN_BIOMNI_LLM`, `PMN_BIOMNI_DATA`, `PMN_BIOMNI_MAX`; flag `--phase a|b|c|all`.

- [ ] **Step 1: Leggere il nuovo blocco di configurazione**

In `bin/lib/parse_config.py`, subito dopo la riga `emit("PMN_GROUP_COL", ...)`:

```python
    emit("PMN_BIOMNI_ON", get(cfg, "analysis", "biomni", "enabled", default=False))
    emit("PMN_BIOMNI_LLM", get(cfg, "analysis", "biomni", "llm", default=""))
    emit("PMN_BIOMNI_DATA", get(cfg, "analysis", "biomni", "data_path", default=""))
    emit("PMN_BIOMNI_MAX", get(cfg, "analysis", "biomni", "max_taxa", default="5"))
```

- [ ] **Step 2: Aggiungere il validatore del nome modello**

In `bin/lib/validate.sh`, in fondo:

```bash
# Model name for Phase C: letters, digits, . _ - / :  (no spaces, no leading dash)
validate_llm_name() {
  local n="${1:-}"
  [ -n "$n" ] || return 1
  [ ${#n} -le 96 ] || return 1
  case "$n" in
    -*)                     return 1 ;;
    *[!A-Za-z0-9._:/-]*)    return 1 ;;
    *)                      return 0 ;;
  esac
}
```

- [ ] **Step 3: Dichiarare il nuovo ambiente conda**

In `bin/lib/requirements.sh`, aggiungere a `PMN_ENV_PKGS`, `PMN_ENV_PROBE` e `PMN_ENV_ORDER`:

```bash
  [pmn_biomni]="python pandas pip"
```

```bash
  [pmn_biomni]="python -c 'import biomni'"
```

```bash
PMN_ENV_ORDER=(
  pmn_download pmn_qc pmn_trim pmn_hostfilter
  pmn_metaphlan pmn_kraken pmn_stats_r pmn_reports_py pmn_biomni
)
```

E in `bin/preflight.sh` l'ambiente `pmn_biomni` va controllato **solo** se `PMN_BIOMNI_ON = yes`, perché è opzionale: la sua assenza non deve far fallire una pipeline che non lo usa. `biomni` si installa con `pip` dentro l'env (non è su conda-forge).

- [ ] **Step 4: Aggiungere il flag `--phase` a run.sh**

In `bin/run.sh`, nel blocco `while [ $# -gt 0 ]`, aggiungere prima del ramo `*)`:

```bash
    --phase)          PHASE="${2:-}"; shift 2 ;;
```

e inizializzare accanto a `CONFIG=""; DRY=0; SKIP_PREFLIGHT=0`:

```bash
PHASE="all"
```

subito dopo il parsing:

```bash
validate_in_set "$PHASE" all a b c || die "invalid --phase (all|a|b|c)"
```

Poi racchiudere il blocco della Fase A in `if [ "$PHASE" = "all" ] || [ "$PHASE" = "a" ]; then ... fi` e quello della Fase B in `if [ "$PHASE" = "all" ] || [ "$PHASE" = "b" ]; then ... fi`.

- [ ] **Step 5: Aggiungere il blocco Fase C**

In `bin/run.sh`, subito **prima** della riga `ok "$(say "Pipeline complete...`:

```bash
# ============================ PHASE C — taxa dossier (OPTIONAL) ============================
# Never submitted to PBS: compute nodes usually have no internet, and the Biomni data lake
# would eat the user's disk quota. Off by default; only species names ever leave the machine.
if [ "$PMN_BIOMNI_ON" = "yes" ] && { [ "$PHASE" = "all" ] || [ "$PHASE" = "c" ]; }; then
  if [ "$PMN_SCHED" = "pbs" ]; then
    info "$(say "Phase C skipped under PBS. Download the results and run: bash bin/run.sh --config <cfg> --phase c" \
             "Fase C saltata sotto PBS. Scarica i risultati e lancia: bash bin/run.sh --config <cfg> --phase c")"
  else
    validate_llm_name "$PMN_BIOMNI_LLM" || die "analysis.biomni.enabled is true but analysis.biomni.llm is invalid or empty"
    validate_uint "$PMN_BIOMNI_MAX"     || die "invalid analysis.biomni.max_taxa"
    awk -v v="$PMN_BIOMNI_MAX" 'BEGIN{exit !(v>=1 && v<=500)}' || die "analysis.biomni.max_taxa must be between 1 and 500"
    { [ -z "$PMN_BIOMNI_DATA" ] || validate_path_safe "$PMN_BIOMNI_DATA"; } || die "unsafe analysis.biomni.data_path"
    c=(--out "$RES_DIR/biomni_dossier" --llm "$PMN_BIOMNI_LLM" --work-dir "$PMN_WORK_DIR"
       --threshold-pct "$PMN_THRESHOLD" --max-taxa "$PMN_BIOMNI_MAX")
    [ -n "$MPA_MERGED" ] && c+=(--metaphlan "$MPA_MERGED")
    [ -n "$KRK_MATRIX" ] && c+=(--kraken "$KRK_MATRIX")
    [ "$DRY" -eq 1 ] && c+=(--dry-run)
    do_step pmn_biomni dossier -- python "$PMN_ROOT/steps/50_biomni_dossier.py" "${c[@]}"
  fi
fi
```

- [ ] **Step 6: Rete di sicurezza sulle credenziali**

Aggiungere in fondo a `.gitignore`:

```
# Phase C credentials (never commit an API key)
.pmn/
*.credentials
.biomni_consent.json
```

- [ ] **Step 7: Verificare che la pipeline non si sia rotta**

Run: `bash bin/run.sh --config config.example.yaml --dry-run --skip-preflight --phase c`
Expected: nessun errore di parsing; la Fase C viene saltata perché `enabled: false` non è ancora nel file di esempio (arriva al Task 10).

Run: `conda run -n pmn_reports_py python -m pytest tests/ -v`
Expected: PASS, 41 test (21 core + 12 consent + 8 CLI)

⚠️ **Lacuna dichiarata:** il salto della Fase C sotto PBS (test 9 dello spec §11) è logica **bash**, non coperta da pytest. Va verificata a mano con `PMN_SCHED=pbs` in un `--dry-run`, e la verifica va annotata nel commit. Non dichiararla "testata".

- [ ] **Step 8: Commit**

```bash
git add bin/lib/parse_config.py bin/lib/validate.sh bin/lib/requirements.sh bin/preflight.sh bin/run.sh .gitignore
git commit -m "feat(phase-c): wire the optional dossier step into run.sh behind --phase c"
```

---

## Task 10: Documentazione e configurazione di esempio

**Files:**
- Modify: `config.example.yaml` (blocco `analysis`)
- Modify: `SPEC.md` (§2 intervista, §3 ordine di esecuzione, §0 costituzione)
- Modify: `SECURITY.md`
- Modify: `README.md` (sezione inglese e sezione italiana)

**Interfaces:**
- Consumes: il comportamento fissato nei Task 6-9.
- Produces: niente codice; è il contratto verso l'utente.

- [ ] **Step 1: Aggiungere il blocco a config.example.yaml**

Sotto `analysis:`, dopo `group_col`:

```yaml
  # -------------------------------------------------------------------------
  # PHASE C - taxa dossier via Biomni. OPTIONAL, OFF BY DEFAULT, LOCAL ONLY.
  # FASE C - dossier dei taxa via Biomni. OPZIONALE, SPENTA, SOLO IN LOCALE.
  # Only species NAMES ever leave your machine, and only after you consent.
  # Escono solo i NOMI delle specie, e solo dopo il tuo consenso.
  # -------------------------------------------------------------------------
  biomni:
    enabled: false
    llm: ""            # REQUIRED when enabled. You choose / lo scegli TU:
                       #  PAID (needs YOUR api key, COSTS REAL MONEY):
                       #    claude-*  (Anthropic, ANTHROPIC_API_KEY)
                       #    gpt-*     (OpenAI,    OPENAI_API_KEY)
                       #    gemini-*  (Google,    GEMINI_API_KEY)
                       #    groq/* | azure/* | bedrock/*
                       #  FREE AND LOCAL (no key, no cost, nothing leaves):
                       #    ollama/<model>
    data_path: ""      # where to keep the Biomni data lake (~11GB); empty -> ./biomni_data
    max_taxa: 5        # HARD CAP. Start at 5 to MEASURE the cost, then raise. Max 500.
```

- [ ] **Step 2: Aggiornare SPEC.md**

- In §2 (intervista) aggiungere il punto 9: chiedere se l'utente vuole la Fase C, presentando **nello stesso spazio** le due famiglie di modelli (a pagamento e locali) e dichiarando che quelli a pagamento costano.
- In §3 (ordine di esecuzione) aggiungere: «**Phase C** (optional): only if `analysis.biomni.enabled` is true, only locally, never under PBS.»
- In §0 aggiungere la regola 9: «Consenso prima dell'uscita dei dati. Prima di inviare qualsiasi cosa a un servizio esterno, mostra esattamente cosa stai per inviare, a chi, e che l'operazione comporta un costo. Il consenso è per progetto e decade se cambia modello o fornitore.»

- [ ] **Step 3: Aggiornare SECURITY.md**

Aggiungere una sezione "Phase C — data egress and API keys" con: cosa esce (solo nomi di specie), cosa non esce mai, come si dà e si revoca il consenso (cancellare `<work_dir>/.biomni_consent.json`), dove stanno le chiavi (`ambiente` o `~/.pmn/credentials` a `0600`), il fatto che su Windows i permessi POSIX non sono applicabili, e che le chiavi non compaiono mai in log o output.

- [ ] **Step 4: Aggiungere la sezione al README (inglese e italiano)**

In entrambe le metà, dopo la sezione 17 ("Scope"), aggiungere "18. Phase C — taxa dossier (optional)" / "18. Fase C — dossier dei taxa (opzionale)" con: a cosa serve, che è spenta di default, le due famiglie di modelli presentate allo stesso modo, come si crea la chiave, che **costa e quanto non è prevedibile**, e come si lancia:

```bash
bash bin/run.sh --config config.yaml --phase c
```

Rinumerare le sezioni successive in entrambe le lingue e aggiornare l'indice.

- [ ] **Step 5: Verificare che l'esempio si legga ancora**

Run: `bash bin/run.sh --config config.example.yaml --dry-run --skip-preflight`
Expected: nessun errore di validazione; nessuna esecuzione di Fase C (`enabled: false`).

- [ ] **Step 6: Commit**

```bash
git add config.example.yaml SPEC.md SECURITY.md README.md
git commit -m "docs(phase-c): document the optional dossier, both model families and the cost"
```

---

## Task 11: Prima esecuzione reale e misura del costo

**Files:**
- Create: `docs/superpowers/specs/2026-08-06-biomni-fase-c-PRIMA-RUN.md`

**Interfaces:**
- Consumes: tutto quanto sopra.
- Produces: la decisione se la Fase C ha valore scientifico, e il costo reale misurato.

- [ ] **Step 1: Provare a vuoto, senza spendere**

```bash
bash bin/run.sh --config config.yaml --phase c --dry-run
```

Expected: elenca le specie che invierebbe e non fa nient'altro.

- [ ] **Step 2: Eseguire davvero su 5 taxa**

Con `max_taxa: 5` in `config.yaml`:

```bash
bash bin/run.sh --config config.yaml --phase c
```

- [ ] **Step 3: Leggere il consumo sulla console del fornitore**

Annotare i token consumati e il costo per quei 5 taxa. È l'unico modo onesto di sapere quanto costa.

- [ ] **Step 4: Giudicare la qualità con l'occhio del biologo**

Prendere 3 affermazioni etichettate `noto` e controllare a mano i PMID. Se anche una sola citazione verificata risultasse sbagliata, la regola di verifica ha un buco: fermarsi e aprire un'indagine con `superpowers:systematic-debugging`.

- [ ] **Step 5: Scrivere il verdetto**

Il file deve contenere: costo misurato per 5 taxa, costo estrapolato per 50, quante affermazioni `noto` / `atteso` / `ipotesi`, quante citazioni scartate, e un giudizio esplicito: **la Fase C vale o no**.

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/specs/2026-08-06-biomni-fase-c-PRIMA-RUN.md
git commit -m "docs(phase-c): first real run - measured cost and quality verdict"
```

---

## Copertura dello spec

| Requisito dello spec | Task |
|---|---|
| §3 architettura, env separato | 1, 9 |
| §4 input dai loader esistenti | 1 |
| §5.1 markdown con intestazione di provenienza | 5 |
| §5.2 TSV una riga per affermazione | 5 |
| §5.3 `run_meta.json` | 8 |
| §6.1 due famiglie di modelli, pari trattamento | 6, 10 |
| §6.2 costo dichiarato, `max_taxa` 5, `--dry-run` | 8, 10, 11 |
| §6.3 consenso, registrazione, invalidazione, non interattivo | 6, 8 |
| §6.4 procedura guidata chiave API | 7 |
| §6.5 cosa esce e cosa no | 8 |
| §7 regola 1 (solo citazioni cercate) | 2 |
| §7 regola 2 (verifica NCBI) | 3 |
| §7 regola 3 (declassamento) | 4 |
| §8 configurazione e validazione | 9, 10 |
| §9 `--phase c`, mai su PBS, errore chiaro senza chiave | 8, 9 |
| §10 elenco file | 9, 10 |
| §11 i 16 test | 1-9 |
| §13 le cinque incognite | 0, 11 |
