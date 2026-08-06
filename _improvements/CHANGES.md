# ProfileMetaNanni — CHANGES (branch `pmn-improvements-iter`)

Iterazione 2 dell'orchestrazione multi-agente. 7 modifiche in-architettura, tutte non
distruttive, idempotenti e conformi alla Safety Constitution. Diff: 10 file, +100 / −32.

Base: `main` @ `dee3436`. Patch portabile: `_improvements/pmn-improvements-iter.patch`.

## Modifiche

| ID | Prio | Titolo | File |
|----|------|--------|------|
| ACC-1 | P0 | `preflight.sh` esce **≠0** anche con env BROKEN (non solo MISSING) + valida `--lang` | bin/preflight.sh |
| ACC-2 | P1 | Le probe verificano **ogni** tool/libreria-R per env, non solo uno; guard di consistenza | bin/lib/requirements.sh |
| ACC-3 | P1 | Riferimento umano automatico **GRCh38 → T2T-CHM13v2.0** (`chm13`, `GCF_009914755.1`) | refs/hosts.tsv, bin/run.sh, config.example.yaml, SPEC.md, README.md |
| ACC-4 | P1 | Statistiche host-removal di Bowtie2 catturate nel report **MultiQC** (osservabilità) | steps/21_hostfilter.sh, bin/run.sh |
| ACC-5 | P1 | Validatori più stretti: `pbs_mem` richiede l'unità; walltime MM/SS in 00–59 | bin/lib/validate.sh, config.example.yaml |
| ACC-6 | P2 | Spike-in Illumina **phiX174** (`GCF_000819615.1`) selezionabile come host (opt-in) | refs/hosts.tsv, config.example.yaml, SPEC.md |
| ACC-7 | P2 | Preset host-filter **`--very-sensitive-local`** opt-in (default = comportamento attuale) | bin/lib/parse_config.py, bin/run.sh, steps/21_hostfilter.sh, config.example.yaml |

## Perché (evidenza)

- **ACC-1** — Un preflight che stampa BROKEN ma ritorna 0 viola SPEC §0.7 (onestà exit code) e lascia
  passare il gate di `run.sh:141` verso una pipeline che poi crasha. Bugfix P0.
- **ACC-3** — Due benchmark peer-reviewed 2025 (Zhou, mSystems; Forbes, Cell Reports Methods) mostrano
  che GRCh38 lascia reads umane residue misclassificate come microbiche; T2T-CHM13v2.0 le rimuove
  (−~48% falsi positivi) ed elimina il segnale del cromosoma Y → **privacy** (regola "mai dati
  identificabili"). Accession verificato live su NCBI Datasets.
- **ACC-4** — Il tasso di host-removal è già su stderr di Bowtie2 ma va perso; qui viene persistito
  dove MultiQC lo mostra → intercetta over-/under-depletion.
- **ACC-5** — Un `pbs_mem` senza unità (`4000`) alcune config PBS lo leggono come **byte** → job che
  chiede ~4KB e fallisce dopo la coda. Ora fallisce subito con messaggio chiaro.
- **ACC-6/ACC-7** — Allineati a Barcenilla 2024 (dominio carni/WMS): phiX + host + preset -local;
  entrambi opt-in, default invariato.

## Verifica (iterazione 2, statica)

Non eseguibile end-to-end su questa macchina (serve Linux + conda + DB grandi + eventuale cluster);
verificato staticamente:
- `bash -n` su tutti gli script modificati: **OK**.
- Guard di `requirements.sh`: silenzioso, 8 env / 8 probe consistenti.
- Validatori: `32GB/512mb/1tb/4000b` accettati; `4000/32/vuoto` rifiutati; walltime `24:00:00/168:00:00`
  ok, `1:99:99/1:60:00/25:61:00` rifiutati.
- `hosts.tsv`: tab preservati (NF=3); `host_accession()` risolve `chm13/grch38/phix`.
- `parse_config.py`: compila; `config.example.yaml` → `PMN_HOST_PRESET=very-sensitive`, `PMN_PBS_MEM=32GB`
  (passa i validatori inaspriti). Nessun CRLF.

## Iterazione 3 — review avversariale (10 revisori) ed esito

Review multi-agente sola-lettura sul diff: **0 BLOCKER, 0 HIGH**. Due finding CONFIRMED, entrambe
corrette in questa iterazione:

- **MEDIUM (corretta)** — regressione introdotta in ACC-2: la probe `pmn_stats_r` testava anche
  `ade4/ape/ggpubr` (mai usate da `41_diversity.R`) e `zCompositions/rstatix` (opzionali, con
  fallback `requireNamespace()`). Un loro fallimento di load avrebbe marcato l'env BROKEN →
  preflight exit 2 → run bloccata inutilmente. **Fix:** probe ridotta all'unica dipendenza hard,
  `Rscript -e 'suppressMessages(library(vegan))'`, + commento corretto. Verificato: `bash -n` OK,
  guard silenzioso, probe pulita (nessuna libreria non-usata).
- **LOW (corretta)** — la chiave `host_sensitivity` era documentata in README e config ma non in
  `SPEC.md`. **Fix:** aggiunta una clausola nell'intervista SPEC §2.

**Osservazione DEFERITA (decisione dell'autore, non toccata):** `r-ade4`, `r-ape`, `r-ggpubr` sono
in `PMN_ENV_PKGS[pmn_stats_r]` ma non usati da `41_diversity.R`. Rimuoverli snellirebbe l'install
(e quelle librerie R "notoriously fail to build from bioconda"), ma è una scelta pre-esistente:
valutala tu se non servono a feature future (es. diversità filogenetica con `ape`).

## Come applicare / annullare

Le modifiche sono sul branch `pmn-improvements-iter` (working tree), `main` è intatto.
- Rivedere:  `git diff main`
- Tenere:    `git add -A && git commit -m "..."` (poi eventualmente merge in main)
- Annullare: `git checkout main` (le modifiche restano sul branch) oppure `git checkout -- .`
- Portabile: `git apply _improvements/pmn-improvements-iter.patch` da un checkout di `main`.

Reversibilità mirata: ACC-3 si annulla riportando `PMN_HUMAN_HOST="grch38"` in `bin/run.sh`.
