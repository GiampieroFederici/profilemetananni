# Fase C — dossier dei taxa con Biomni

**Data:** 2026-08-06
**Stato:** design approvato, implementazione non iniziata
**Metodo:** superpowers `brainstorming` → questo documento → `writing-plans` → `executing-plans`

> **English summary.** This spec adds an OPTIONAL "Phase C" to profilemetananni: after
> read-based profiling, the list of detected species is handed to a
> [Biomni](https://github.com/snap-stanford/Biomni) A1 agent, which returns, for each taxon,
> (a) what the literature says about its role in fermented meat and (b) which functions are
> expected (CAZymes, biogenic amines, bacteriocins, resistome). The user picks the LLM —
> paid hosted models or a free local one — is told plainly that hosted models cost money, and
> must consent before any taxon name leaves the machine. Every citation is re-checked against
> NCBI; unverified ones are dropped. Phase C never runs on the cluster and is OFF by default.

---

## 1. Perché

Biomni ha 23 moduli di tool biomedici (`genomics.py`, `genetics.py`, `literature.py`,
`microbiology.py`, …) ma — dalla lettura delle descrizioni di `microbiology.py` — **nessuno
strumento di profiling metagenomico**: niente Kraken, niente MetaPhlAn, niente 16S, niente
tassonomia da reads.

profilemetananni ha esattamente il contrario: la pipeline di profiling c'è ed è testata, ma si
ferma alla tabella di abbondanza. Da lì in poi l'interpretazione è tutta a carico dell'utente.

La Fase C mette in comunicazione le due cose: **profilemetananni produce i taxa, Biomni dice
cosa si sa di quei taxa e cosa ci si aspetta che facciano.** Serve a decidere, con criterio, se
e su quali genomi vale la pena affrontare una vera annotazione funzionale (Bakta, eggNOG-mapper,
dbCAN, antiSMASH), che è costosa in tempo di calcolo.

---

## 2. Decisioni prese (brainstorming del 2026-08-06)

| # | Domanda | Decisione |
|---|---------|-----------|
| 1 | Direzione dell'integrazione | Biomni **dentro** profilemetananni, come consulente. profilemetananni resta padrone della pipeline. |
| 2 | Cosa produce | Un **dossier per taxon**: letteratura (ruolo) + funzione attesa. |
| 3 | Dove gira | **Solo in locale**, con LLM a scelta dell'utente. Mai sul cluster. |
| 4 | Per chi | **Funzione pubblica** di profilemetananni: opzionale, spenta di default, documentata EN+IT. |
| 5 | Consenso | **Una sola chiave** (`enabled`) + domanda interattiva la prima volta, che dichiara anche il costo. |

---

## 3. Architettura

Un solo file nuovo e un solo env conda nuovo. Fase A e Fase B non vengono toccate.

```
Fase B (esistente)                    Fase C (nuova)
──────────────────────                ─────────────────────────────────
merged_abundance.txt   ──┐
kraken_matrix.tsv      ──┤
                         │
                         ▼
              steps/_profiling_io.py          ← riuso, zero modifiche
              load_metaphlan_species()
              load_kraken_matrix()
                         │
                         ▼
              lista specie sopra soglia
                         │
                         ▼
              steps/50_biomni_dossier.py      ← NUOVO
                         │
                    ┌────┴────┐
                    │ consenso│  (interattivo, la prima volta)
                    └────┬────┘
                         ▼
                   Biomni A1  →  LLM scelto dall'utente
                         │       + ricerca reale su PubMed
                         ▼
              verifica citazioni su NCBI E-utilities
                         │
                         ▼
   results/biomni_dossier/dossier_taxa.md   (per leggere)
   results/biomni_dossier/dossier_taxa.tsv  (per rielaborare)
   results/biomni_dossier/run_meta.json     (provenienza)
```

**Perché un env conda separato (`pmn_biomni`).** Biomni porta con sé molte dipendenze pesanti.
Mescolarlo con `pmn_reports_py` (pandas, openpyxl) metterebbe a rischio Fase A e Fase B, che
oggi funzionano. Il progetto usa già un env per famiglia di strumenti (`pmn_metaphlan`,
`pmn_stats_r`, `pmn_reports_py`): questa scelta segue lo stesso schema.

---

## 4. Input

L'input è la **lista dei nomi di specie** sopra la soglia di abbondanza, ottenuta riusando i
loader già presenti in `steps/_profiling_io.py`:

- `load_metaphlan_species(path, threshold_pct)` → `{specie_normalizzata: abbondanza_max}`
- `load_kraken_matrix(path, threshold_pct)` → `{specie_normalizzata: abbondanza_max}`

Se `profiling.tool: both`, le due liste vengono unite (unione, non intersezione) e ogni taxon
riporta da quale profilatore proviene.

La normalizzazione dei nomi (inclusa la mappa dei generi riclassificati nel 2020, es.
`Lactobacillus sakei` → `Latilactobacillus sakei`) è già dentro `_profiling_io.normalize()` e
viene applicata **prima** di qualsiasi ricerca in letteratura, così le citazioni si cercano sul
nome valido.

**Le abbondanze vengono lette ma NON inviate** (vedi §6).

---

## 5. Output

### 5.1 `dossier_taxa.md` — per leggere

Intestazione obbligatoria, in cima al file:

```
> ATTENZIONE: documento generato da un modello linguistico (LLM), non da un esperto.
> Modello: <nome> (<fornitore>) · Data: <YYYY-MM-DD> · Taxa analizzati: <N>
> Citazioni ricontrollate su NCBI: <X> confermate, <Y> scartate.
> Le righe "atteso" e "ipotesi" NON sono prove. Vanno verificate a mano.
```

Poi un blocco per taxon:

```
## Latilactobacillus sakei
Rilevato da: MetaPhlAn + Kraken

Ruolo in carne fermentata: starter wild-type dominante
  evidenza: 3 studi   [PMID … ; PMID … ; PMID …]

Funzioni attese:
  batteriocine (sakacina)   noto      [PMID …]
  ammine biogene            assente   [PMID …]
  CAZymes                   atteso    (inferito dal genere)

Vale la pena annotarlo in Fase D?  SÌ — batteriocine
```

### 5.2 `dossier_taxa.tsv` — per rielaborare

Una riga per coppia (taxon, affermazione). Colonne:

`taxon` · `rilevato_da` · `categoria` · `affermazione` · `etichetta` · `citazioni` ·
`citazioni_verificate` · `vale_fase_d`

dove `categoria` ∈ {`ruolo`, `batteriocine`, `ammine_biogene`, `cazymes`, `resistoma`,
`virulenza`} ed `etichetta` ∈ {`noto`, `atteso`, `ipotesi`, `assente`}.

### 5.3 `run_meta.json` — provenienza

Modello, fornitore, data, numero di taxa inviati, `max_taxa`, versione di profilemetananni,
conteggio citazioni confermate/scartate. Serve alla riproducibilità: un dossier senza la sua
provenienza non è un documento scientifico.

---

## 6. Scelta del modello, costo e consenso

### 6.1 Il modello lo sceglie l'utente — le due famiglie si dichiarano allo stesso modo

Non esiste un modello imposto né suggerito di nascosto. La documentazione e l'intervista
presentano **entrambe le famiglie in modo paritario**, con pregi e difetti espliciti:

**A pagamento (pronte all'uso, serve la TUA chiave API):**

| Famiglia | Esempio | Chiave d'ambiente |
|---|---|---|
| Anthropic | `claude-…` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-…` | `OPENAI_API_KEY` |
| Google | `gemini-…` | `GEMINI_API_KEY` |
| Groq | — | `GROQ_API_KEY` |
| Azure OpenAI | — | variabili Azure |
| AWS Bedrock | — | credenziali AWS |

*Pro:* ragionamento migliore su un compito complesso, funzionano subito.
*Contro:* **costano soldi veri**, e i nomi dei taxa escono dal computer.

**Gratuite e locali (nessun costo, nessun dato fuori):**

| Famiglia | Esempio |
|---|---|
| Ollama | `ollama/<modello>` |

*Pro:* costo zero, nessun dato lascia il PC, coerente con `SPEC.md` §0.5.
*Contro:* su un compito di ragionamento a più passaggi un modello locale sbaglia di più, e
serve hardware adeguato.

> **Rischio aperto — da verificare al passo 1 dell'implementazione.** La documentazione di
> Biomni che ho letto elenca esplicitamente Anthropic, OpenAI, Azure, Gemini, Groq e AWS
> Bedrock. **Il supporto a Ollama NON è stato verificato.** Biomni serve un proprio modello
> locale (Biomni-R0 via SGLang), quindi una via locale è plausibile, ma finché non è provata
> non va promessa nella documentazione pubblica. Se risultasse non supportato, la tabella
> "gratuite e locali" va corretta con la via che funziona davvero (es. SGLang), oppure va
> dichiarato che al momento il locale non è disponibile.

### 6.2 Il costo si dichiara, non si nasconde

L'agente A1 non fa una singola chiamata: pianifica, esegue codice, itera. Il consumo **non è
prevedibile in anticipo** e dipende dal modello e dal numero di taxa.

Conseguenze di progetto:

- `max_taxa` in `config.example.yaml` ha default **5**, con il commento che dice di alzarlo
  solo dopo aver misurato la spesa reale. Tetto massimo accettato: 500.
- Esiste `--dry-run`: mostra esattamente cosa verrebbe inviato e a chi, **senza spendere**.
- Al termine, `run_meta.json` registra quanti taxa sono stati processati, così la spesa
  osservata è riconducibile a un numero.
- La documentazione **non stima cifre in euro**: sarebbero inventate.

### 6.3 Il cancello di consenso

Una sola chiave in `config.yaml` (`enabled`), più una domanda interattiva la prima volta.

Con un modello **a pagamento**:

```
┌─ Fase C · Biomni ── ATTENZIONE: QUESTA OPERAZIONE TI COSTA SOLDI ──┐
│  Modello scelto da TE : <modello>  (<fornitore>)                   │
│  Chi paga             : TU, con la tua <VAR_CHIAVE>                │
│  Quanto costa         : NON è prevedibile in anticipo.             │
│                         L'agente ragiona a più passaggi.           │
│                         → parti con max_taxa: 5 e misura.          │
│                                                                    │
│  Esce dal tuo PC      : <N> nomi di specie                         │
│  NON esce             : campioni, SRR, path, abbondanze, FASTQ     │
│                                                                    │
│  Alternativa gratuita : un modello locale — costo zero, nessun     │
│                         dato fuori, ma sbaglia di più.             │
│                                                                    │
│  Procedo, e accetto di pagare?  [s/N]                              │
└────────────────────────────────────────────────────────────────────┘
```

Con un modello **locale**:

```
┌─ Fase C · Biomni ── modello LOCALE ────────────────────────────────┐
│  Modello : <modello>  (gira sul tuo computer)                      │
│  Costo   : ZERO                                                     │
│  Dati    : NON escono dal tuo computer                              │
│  Nota    : su un compito di ragionamento come questo un modello    │
│            locale sbaglia più di uno grande.                        │
│  Procedo?  [s/N]                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

Regole del consenso:

1. La risposta affermativa viene scritta in `<work_dir>/.biomni_consent.json` con data,
   modello, fornitore e cosa è stato autorizzato. Le volte successive non chiede più.
2. Se cambia modello **o** fornitore, **richiede**: il destinatario dei dati è diverso.
3. Senza terminale interattivo e senza consenso registrato, **si ferma** con un messaggio che
   indica il flag `--yes-send-taxa`. Non parte mai di nascosto.
4. `--dry-run` non richiede consenso perché non invia nulla.

### 6.4 La chiave API: procedura guidata, non un messaggio d'errore

profilemetananni è pensato per chi **non** è informatico. Dire "esporta la variabile
`OPENAI_API_KEY` nella tua shell" e fallire è un modo per perdere l'utente. Il tool deve fare
il bioinformatico *al posto* suo, quindi accompagna la configurazione passo per passo.

**Regola di progetto: se manca la chiave, il tool non fallisce — insegna.**

#### Passo 1 — riconosce da solo quale chiave serve

Dal nome del modello scritto in `llm:` il tool deduce fornitore e variabile d'ambiente:

| Se `llm:` inizia con | Fornitore | Variabile | Dove si crea la chiave |
|---|---|---|---|
| `claude-` | Anthropic | `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `gpt-`, `o1-`, `o3-` | OpenAI | `OPENAI_API_KEY` | platform.openai.com/api-keys |
| `gemini-` | Google | `GEMINI_API_KEY` | aistudio.google.com/apikey |
| `groq/` | Groq | `GROQ_API_KEY` | console.groq.com/keys |
| `azure/` | Azure OpenAI | variabili Azure | portale Azure → risorsa OpenAI |
| `bedrock/` | AWS Bedrock | credenziali AWS | console AWS → IAM |
| `ollama/` | locale | **nessuna** | — (gratis, niente chiave) |

> Gli indirizzi in questa tabella vanno **riverificati al momento dell'implementazione**: le
> console dei fornitori cambiano. Un link morto in un tool per non-informatici è un bug.

#### Passo 2 — se la chiave manca, la spiega e la chiede

```
┌─ Fase C · serve una chiave API ───────────────────────────────────┐
│  Hai scelto il modello:  gpt-4o   (fornitore: OpenAI)             │
│  Per usarlo serve una TUA chiave personale. Non l'ho trovata.     │
│                                                                    │
│  COME OTTENERLA — circa 3 minuti:                                 │
│   1. Apri  https://platform.openai.com/api-keys                   │
│   2. Registrati o accedi                                          │
│   3. Premi "Create new secret key" e COPIA la chiave              │
│      (inizia con "sk-", è lunga una cinquantina di caratteri)     │
│   4. ATTENZIONE: serve un metodo di pagamento attivo sul tuo      │
│      account, altrimenti la chiave non funziona.                  │
│                                                                    │
│  Incolla qui la chiave (NON verrà mostrata mentre la scrivi):     │
│   >                                                                │
│                                                                    │
│  Oppure:                                                          │
│   [L] uso un modello LOCALE gratis  →  ti mostro come             │
│   [A] annulla                                                      │
└────────────────────────────────────────────────────────────────────┘
```

L'inserimento è mascherato (niente eco a schermo). La chiave **non compare mai** nei log, nei
messaggi d'errore, in `run_meta.json` né in `config.yaml`.

#### Passo 3 — chiede dove salvarla, e spiega la differenza

```
  Dove salvo la chiave?
   [1] ~/.pmn/credentials      consigliato
       File riservato: permessi 600 (solo il tuo utente può leggerlo),
       fuori dalla cartella del progetto, mai finisce su GitHub.
       Le prossime volte non ti chiederò più nulla.

   [2] da nessuna parte
       La uso solo per questa esecuzione e poi me la dimentico.
       Dovrai reincollarla ogni volta.
```

Vincoli sul file `~/.pmn/credentials`:

- creato con permessi `600`; se i permessi risultano più larghi, il tool **rifiuta di usarlo**
  e lo dice;
- una riga per fornitore, formato `VARIABILE=valore`;
- si trova **fuori** dal repository, quindi non può finire in un commit;
- `.gitignore` del progetto aggiunge comunque `.pmn/` e `*.credentials` come rete di sicurezza;
- se la stessa variabile è già presente nell'ambiente, **l'ambiente vince** e il file viene
  ignorato (chi sa già usare `export` non viene scavalcato).

#### Passo 4 — verifica subito che la chiave funzioni

Prima di partire con i taxa, il tool fa **una sola chiamata minima** al fornitore per
controllare che la chiave sia valida.

```
  Verifico la chiave...  OK — la chiave funziona.
```

Se non funziona, spiega **cosa** è andato storto in parole comuni, non con l'errore grezzo:

| Cosa risponde il fornitore | Cosa dice il tool |
|---|---|
| 401 / non autorizzato | "La chiave non è valida. Forse è incompleta o è stata revocata: ricreala." |
| 402 / 429 su credito | "La chiave è valida ma l'account non ha credito o metodo di pagamento attivo." |
| errore di rete | "Non riesco a raggiungere il fornitore: controlla la connessione o il proxy." |

Questo costa una frazione irrisoria ed evita il caso peggiore: scoprire che la chiave è
sbagliata **dopo** venti minuti di elaborazione.

#### Passo 5 — se sceglie il modello locale, lo guida lo stesso

Chi preme `[L]` non viene abbandonato con "installa Ollama":

```
  MODELLO LOCALE — gratis, nessun dato esce dal tuo computer.
   1. Scarica Ollama da  https://ollama.com/download
   2. Apri il terminale e scarica un modello:   ollama pull <modello>
   3. Scrivi in config.yaml:   llm: "ollama/<modello>"
   4. Rilancia:  bash bin/run.sh --config config.yaml --phase c

  Nota onesta: un modello locale su un compito di ragionamento come questo
  sbaglia più di un modello grande a pagamento. Guadagni privacy e costo zero,
  perdi in qualità.
```

Il nome preciso del modello da suggerire e i comandi vanno **verificati** in fase di
implementazione, insieme al supporto Ollama in Biomni (§13, rischio 1).

#### Passo 6 — mai imbrogliare sul rapporto costo/beneficio

Nel README e nell'intervista le due famiglie di modelli compaiono **sempre insieme**, con lo
stesso spazio e la stessa chiarezza: a pagamento (pronte, migliori, costano) e locali (gratis,
private, meno precise). Non c'è un default nascosto e non c'è una famiglia presentata come
"quella vera".

### 6.5 Cosa esce e cosa no

**Esce:** soltanto i nomi normalizzati delle specie (es. `Latilactobacillus sakei`).

**Non esce mai:** nomi dei campioni, accessioni SRR, percorsi di file, valori di abbondanza,
metadati, reads. Questo rispetta `SPEC.md` §0.5 ("Never exfiltrate") riducendo l'invio al
minimo indispensabile, e i nomi di specie sono comunque il contenuto pubblico di qualunque
database tassonomico.

**Chiavi API:** lette **solo** dall'ambiente, mai scritte in `config.yaml`, mai stampate nei
log. È la stessa regola già applicata a `NCBI_API_KEY`.

---

## 7. Anti-invenzione: come si evita che l'LLM si inventi le citazioni

Un modello linguistico produce con facilità DOI e PMID plausibili e inesistenti. In un tool
scientifico questo è il rischio principale. Tre regole, applicate dal codice e non affidate al
buon senso del modello:

1. **Nessuna citazione dalla memoria del modello.** Sono accettati solo PMID/DOI restituiti da
   una ricerca reale (Biomni `literature.py` / PubMed). Un identificativo che compare nel testo
   generato ma non nei risultati di ricerca viene ignorato.
2. **Verifica a valle su NCBI.** Ogni PMID sopravvissuto viene richiesto alle E-utilities di
   NCBI e confrontato: se titolo e anno non corrispondono, **la riga viene scartata**, non
   "segnalata". I conteggi di confermate/scartate finiscono nell'intestazione del dossier e in
   `run_meta.json`.
3. **Etichetta obbligatoria su ogni affermazione funzionale:**
   - `noto` — dimostrato in *quella* specie, con almeno una citazione verificata;
   - `assente` — assenza documentata, con citazione verificata;
   - `atteso` — inferito dal genere o dalla famiglia, dichiarato come inferenza;
   - `ipotesi` — nessuna citazione verificata → **declassamento automatico**.

   Una riga senza citazione verificata **non può** essere `noto` né `assente`: il codice la
   riscrive a `ipotesi` indipendentemente da ciò che ha risposto il modello.

---

## 8. Configurazione

Nuovo blocco in `config.example.yaml`, sotto `analysis`:

```yaml
analysis:
  biomni:
    enabled: false      # false = Fase C spenta (default)
    llm: ""             # OBBLIGATORIO se enabled. Lo scegli TU.
                        #  A PAGAMENTO (serve la TUA chiave API, costa soldi veri):
                        #     claude-*  (Anthropic) | gpt-* (OpenAI) | gemini-* (Google)
                        #     groq | azure | bedrock
                        #  GRATIS E LOCALE (nessun costo, nessun dato esce dal PC):
                        #     ollama/<modello>
    data_path: ""       # dove tenere il data lake di Biomni (~11 GB). Vuoto -> ./biomni_data
    max_taxa: 5         # tetto duro. Parti da 5 per MISURARE la spesa, poi alza. Max 500.
```

Validazione (in `bin/lib/validate.sh`, come per ogni altro valore):

- `enabled` → `validate_yesno`
- `llm` → non vuoto se `enabled: true`; formato ristretto (lettere, cifre, `.`, `_`, `-`, `/`, `:`)
- `data_path` → `validate_path_safe`
- `max_taxa` → `validate_uint`, compreso fra 1 e 500

---

## 9. Esecuzione

- Nuovo flag di `bin/run.sh`: `--phase c` esegue **solo** la Fase C. Serve al caso d'uso reale:
  Fase A e B sul cluster, poi si scaricano le tabelle (poche centinaia di KB) e si esegue la
  Fase C sul proprio computer.
- La Fase C **non viene mai sottomessa a PBS**, nemmeno con `scheduler: pbs`. Motivi: i nodi di
  calcolo tipicamente non hanno accesso a internet, e il data lake da ~11 GB peserebbe sulla
  quota disco dell'utente. Se `enabled: true` in una run PBS, la Fase C viene **saltata** con un
  messaggio esplicito che spiega come eseguirla in locale.
- Se `enabled: true` ma manca la chiave API richiesta dal modello scelto, la Fase C **fallisce
  con un messaggio chiaro** e non compromette i risultati di Fase A/B già prodotti.

---

## 10. File toccati

| File | Cosa |
|---|---|
| `steps/50_biomni_dossier.py` | **nuovo** — l'intero passo |
| `steps/_profiling_io.py` | riuso, **nessuna modifica** |
| `bin/run.sh` | Fase C + flag `--phase c` |
| `bin/lib/parse_config.py` | lettura del blocco `analysis.biomni` |
| `bin/lib/validate.sh` | validatori del blocco `analysis.biomni` |
| `bin/lib/requirements.sh` | definizione dell'env `pmn_biomni` |
| `bin/preflight.sh` | controllo dell'env `pmn_biomni` (solo se `enabled: true`) |
| `config.example.yaml` | blocco commentato |
| `.gitignore` | `.pmn/` e `*.credentials` (rete di sicurezza per le chiavi) |
| `SPEC.md` | Fase C nell'ordine di esecuzione + regola di consenso e costo |
| `SECURITY.md` | sezione sull'uscita dei dati e sulle chiavi API |
| `README.md` | sezione nuova, in inglese e in italiano |
| `RESEARCH_PROPOSAL/pmn_workflow.*` | figura del flusso aggiornata con la Fase C — **già fatta** (html sorgente + png/jpg/pdf) |
| `RESEARCH_PROPOSAL/PMN_SPIEGATO.md` | documento divulgativo su PMN — **già fatto** |

---

## 11. Collaudo

Il collaudo **non deve costare soldi**. Un finto client Biomni (una classe che restituisce
risposte fisse, iniettata al posto dell'agente vero) permette di testare tutto il codice nostro:

1. La lista dei taxa viene costruita correttamente da MetaPhlAn, da Kraken e dall'unione dei due.
2. Un PMID inventato — presente nella risposta del modello ma assente dai risultati di ricerca —
   viene **scartato**.
3. Un PMID che esiste ma con titolo diverso viene **scartato** dalla verifica NCBI.
4. Un'affermazione senza citazioni verificate viene **riscritta a `ipotesi`**, anche se il
   modello l'aveva marcata `noto`.
5. Con `enabled: true` e nessun consenso registrato, in ambiente non interattivo il passo
   **si ferma** e non invia nulla.
6. Cambiando modello, il consenso registrato **non vale più** e viene richiesto di nuovo.
7. `--dry-run` non invia nulla e non richiede consenso.
8. `max_taxa` viene rispettato: con 100 taxa e `max_taxa: 5` ne partono 5.
9. Con `scheduler: pbs`, la Fase C viene saltata con il messaggio corretto.
10. L'intestazione di provenienza è presente nel `.md` e i conteggi coincidono con `run_meta.json`.
11. Con `llm: "gpt-…"` e nessuna chiave nell'ambiente, parte la **procedura guidata** (§6.4) e
    non un errore grezzo.
12. La chiave incollata **non compare** in nessun log, messaggio d'errore o file di output.
13. Se `~/.pmn/credentials` ha permessi più larghi di `600`, il tool **rifiuta di leggerlo**.
14. Se la variabile è già nell'ambiente, **l'ambiente vince** sul file delle credenziali.
15. Con una chiave non valida, il messaggio mostrato è quello tradotto della tabella in §6.4,
    non l'errore grezzo del fornitore.
16. Con `llm: "ollama/…"` non viene chiesta nessuna chiave e non parte nessuna verifica.

Solo alla fine, **una** esecuzione reale con `max_taxa: 5` sui dati della tesi, per giudicare se
i dossier hanno valore scientifico e per misurare la spesa effettiva.

---

## 12. Fuori scope (dichiarato)

- La Fase C **non sostituisce** l'annotazione funzionale vera (Bakta, eggNOG-mapper,
  InterProScan, dbCAN, antiSMASH, CARD/RGI). Prevede, non annota.
- Non tocca Fase A e Fase B.
- Non invia mai reads, abbondanze, metadati o identificativi di campione.
- Non produce conclusioni biologiche: produce materiale etichettato che un umano deve valutare.

---

## 13. Rischi aperti da chiudere nel piano

1. **Supporto a Ollama in Biomni: non verificato.** Va provato prima di scriverlo nel README.
2. **Biomni su Windows: non verificato.** L'installazione documentata è `bash setup.sh` + conda,
   di impostazione Linux. Probabile necessità di WSL. Da provare prima di dichiarare i requisiti.
3. **Spazio disco:** il data lake è ~11 GB. Va verificato lo spazio libero prima di scaricarlo,
   e `data_path` deve poter puntare a un disco diverso.
4. **Licenze:** Biomni è Apache 2.0, ma i singoli tool integrati possono avere licenze più
   restrittive. Va controllato prima di dichiarare qualcosa in `README.md` e `LICENSE`.
5. **Costo reale:** ignoto finché non lo si misura. Per questo il default di `max_taxa` è 5.
