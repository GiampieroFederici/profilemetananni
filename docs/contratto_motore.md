# Contratto motore-interfaccia · Engine-GUI contract (v0.2, 16/10/2026)

> Regola (D006, standard RAPID): **l'interfaccia non fa scienza**. Mostra, chiede, lancia.
> Tutto il calcolo sta nel motore, dentro WSL2 (Windows) o Linux.
> Questo documento è il patto fra i due: se l'interfaccia lo rispetta, può essere costruita
> subito contro un **finto motore** che risponde allo stesso modo (D032).
>
> **v0.2 (16/10/2026, filone "Motore, seconda parte", D055):** comandi `sicurezza` e `referto`, referto in
> `risultati/referto/`, consigli di System One v0, `stima` a gruppi. Le aggiunte sono segnate **[v0.2]**;
> tutto ciò che c'era in v0 resta valido.

---

## 1. Come si chiama il motore

- Un solo programma: `pmn-motore <comando> [opzioni]`, installato da `installer/installa_motore.sh`
  in `~/.pmn/bin/pmn-motore`.
  **Esiste dal 16/10/2026** (`motore/pmn-motore` + `motore/pmn_motore.py`, D053): stessi comandi ed eventi del
  finto motore; `installa` passa all'installatore, `esegui` lancia `bin/run.sh`, `verifica` lancia `installer/verifica_motore.sh`.
- Da Windows: `wsl.exe -d <distro> -- ~/.pmn/bin/pmn-motore <comando> ...`.
- Da Linux: direttamente.
- **stdout** = solo eventi JSON, uno per riga (JSON Lines, §4). **stderr** = vuoto o diagnostica breve.
  I dettagli tecnici vanno nel file di log indicato nell'evento `inizio`.

## 2. Comandi

| Comando | Cosa fa | Ingresso | Uscita (evento `fine`, campo `risultato`) |
|---|---|---|---|
| `info` | descrive PC e installazione, senza calcoli lunghi | nessuno | §5.1 |
| `installa` | installa o completa programmi e database; riprende da dove era rimasto | `--catalogo <file o URL>` (predefinito: quello dell'installazione) | `{"programmi": 8, "database": [gruppi del catalogo], "verifica": "verde"}`; con `--stima`: `{"da_scaricare_gb", "spazio_necessario_gb", "spazio_libero_gb", "velocita_mb_s", "tempo_stimato_s"}` |
| `verifica` | MD5 dei database + mini-campione di regressione (D032) | nessuno | `{"esito": "verde" \| "rosso", "controlli": [...]}` |
| `stima` | tempo e spazio previsti, prima di partire (D023, D034) | `--progetto <config.yaml>` | §5.2 |
| `esegui` | analisi completa del progetto | `--progetto <config.yaml>` | §5.3 |
| `annulla` | ferma una corsa in modo pulito | `--corsa <id>` | `{"annullata": true}` |
| `sicurezza` **[v0.2]** | previsioni di crescita (FSSP: *Listeria*, LAB) per un prodotto | `--ingresso <richiesta.json>` [`--progetto <config.yaml>`] | §5.4 |
| `referto` **[v0.2]** | rifà il referto di un progetto già analizzato (per esempio dopo `sicurezza`) | `--progetto <config.yaml>` | `{"cartella", "referto": {"html", "pdf", "xlsx"}}` |

- Un solo `esegui` alla volta (un campione alla volta, D016): un secondo `esegui` risponde con l'errore `GIA_IN_CORSO`.
- `installa` ed `esegui` sono **riprendibili**: rilanciati con gli stessi ingressi, saltano ciò che è già fatto e verificato.
- **[v0.2]** `esegui` prepara da solo il referto alla fine; `sicurezza` con `--progetto` salva il risultato in
  `risultati/sicurezza/`, poi l'interfaccia lancia `referto` per averlo anche nel referto.

## 3. Ingresso del progetto (`config.yaml`)

- Lo schema è quello di `config.example.yaml`, con questi campi in più per l'app:

```yaml
motore:
  metaphlan_modo: fette        # fette (16 GB, D016) | standard (>= 40 GB)
  kraken_db: completo          # completo (PlusPF, D023) | rapido (PlusPF-8, screening)
  virus: false                 # true = opzione sperimentale, non validata a fette (D017, D033)
  processori: 8
```

- I parametri con più valori in letteratura (`kraken_confidence`, `abundance_threshold_pct`, Bracken) li sceglie
  l'utente da un menu con il consigliato preselezionato e la fonte accanto (D022). Il motore li riporta nel referto.
- L'interfaccia scrive il file; il motore lo **valida** (lettura sicura, `yaml.safe_load`) e risponde con
  `errore` e codice `CONFIG_NON_VALIDA` se qualcosa non va, indicando il campo.

## 4. Eventi (stdout, JSON Lines)

Ogni riga è un oggetto JSON con `tipo` e `ora` (ISO 8601). Testi in **italiano semplice** (D027).

| `tipo` | Campi | Esempio di `messaggio` |
|---|---|---|
| `inizio` | `comando`, `corsa` (id), `log` (percorso del log tecnico) | "Analisi avviata: 3 campioni" |
| `avanzamento` | `passo`, `campione`, `fatto`, `totale`, `percentuale` (0-100), `eta_s` (secondi stimati, o null) | "Campione 1 di 3: allineo sulla parte 3 di 6 del database" |
| `avviso` | `codice`, `messaggio` | "Restano 40 GB liberi: bastano per questo progetto" |
| `errore` | `codice`, `messaggio`, `cosa_fare`; **[v0.2]** `passo` (dove si è fermato, o `null` se prima di iniziare) | "Manca il database di Kraken." / "Apri la pagina Motore e premi Installa." |
| `fine` | `esito` (`ok`, `errore`, `annullata`), `risultato` (oggetto) | "Analisi finita in 1 h 12 min" |

- `passo` per `esegui`: `download`, `controllo_qualita`, `pulizia`, `ospite`, `metaphlan`, `kraken`, `riepilogo`.
- `passo` per `installa`: `controllo`, `programmi`, `database`, `verifica`, `fine`
  (già così in `installer/installa_motore.sh --json`).
- **[v0.2]** `passo` `sicurezza` (un avanzamento per scenario) e `referto` (ultimo passo di `esegui`, e del comando `referto`).
- L'interfaccia mostra `messaggio` così com'è; per la barra usa `percentuale` ed `eta_s`.
- **[v0.2]** Testi per l'utente con le vere lettere accentate (è, à, ù, perché), mai l'apostrofo al posto dell'accento.
  `cosa_fare` per motore mancante: "Apri la pagina Motore e premi Installa." (la pagina dell'app si chiama "Motore").
- **[v0.2]** In `esegui` `eta_s` è calcolato con le stesse regole di `stima` (§5.2) e scende a ogni evento: secondi
  per finire il passo in corso più i passi dopo. Il download non è stimato (dipende dalla rete); se le dimensioni
  dei campioni non si possono chiedere (rete giù) `eta_s` resta `null`.
- **[v0.2]** `errore.passo`: il passo dell'ultimo `avanzamento` (o quello in cui l'errore è nato, per esempio
  `kraken` per `DB_MANCANTE` di Kraken). L'installatore non lo manda ancora: lì vale l'ultimo `avanzamento`.
- Ogni corsa finisce **sempre** con un solo evento `fine`, anche dopo un errore.

### Codici di uscita

| Codice | Significato |
|---|---|
| 0 | `fine` con `esito: ok` |
| 1 | errore nei dati o nel progetto (l'utente può correggere) |
| 2 | errore dell'installazione (database o programmi mancanti o rovinati) |
| 3 | annullata dall'utente |
| 4 | errore interno (va segnalato: il log serve a noi) |

### Codici di errore e avviso (prima lista, si allunga)

`CONFIG_NON_VALIDA`, `DB_MANCANTE`, `DB_ROVINATO` (MD5 diverso), `SPAZIO_INSUFFICIENTE`, `RAM_INSUFFICIENTE`,
`READ_NON_TROVATE`, `DOWNLOAD_FALLITO`, `GIA_IN_CORSO`, `TEMPO_LUNGO` (avviso: stima oltre 4 h, propone screening rapido o cloud, D023).

Dall'installatore: errori `SISTEMA_NON_ADATTO` (non Linux a 64 bit), `PROGRAMMA_MANCANTE` (programma di sistema),
`VERIFICA_ROSSA` (prova finale fallita); avvisi `RETE_NON_MISURATA`, `RETE_INTERROTTA` (riprova da sola).
`ERRORE_INTERNO` (codice di uscita 4: un errore nostro, non dell'utente; `cosa_fare` indica il log da mandarci).

**Codice dell'interfaccia, non del motore (S5a, D077):** `MOTORE_NON_AVVIATO` lo crea `app/motore.py` quando il motore
non parte o si chiude senza aver mandato `inizio` (per esempio manca la WSL `pmn`); se si chiude dopo `inizio` senza `fine`,
l'app crea un `ERRORE_INTERNO`. Così ogni corsa vista dalle pagine finisce sempre con un solo `fine`.

**[v0.2]** Nuovi codici:

| Codice | Tipo | Quando |
|---|---|---|
| `INGRESSO_NON_VALIDO` | errore (uscita 1) | `sicurezza`: dati del prodotto mancanti o fuori dai limiti; il messaggio dice quale campo |
| `FUORI_CAMPO` | avviso | `sicurezza`: un fattore è fuori dal campo di validità del modello (M8); uno per fattore e modello, con i campi `modello` (`listeria`, `listeria_lab`, `lab`) e `fattore`, testo già pronto ("Per il modello della Listeria: pH = 5.4: fuori dal campo...") |
| `CAMPIONE_DA_CONTROLLARE`, `CAMPIONE_DA_RIFARE` | avviso | `esegui`: esito del triage (System One v0, §5.5) |
| `REFERTO_PARZIALE` | avviso | `esegui`/`referto`: manca il PDF o l'Excel (la pagina HTML c'è sempre) |

Anche `RAM_INSUFFICIENTE`, `SPAZIO_INSUFFICIENTE`, `DB_MANCANTE`, `TEMPO_LUNGO` possono arrivare come **avviso**
da `info` e `stima` (consigli di System One v0, §5.5): consigliano, non fermano nulla.
In `esegui`, se ENA e NCBI non rispondono il motore lo dice con l'avviso `RETE_INTERROTTA` e **riprova da solo** (3 tentativi, 2 minuti fra l'uno e l'altro) prima di arrendersi con `DOWNLOAD_FALLITO`.

## 5. Uscite

### 5.1 `info`

```json
{"motore": "0.1.0", "ram_gb": 15.6, "processori": 24, "spazio_libero_gb": 643,
 "modo_consigliato": {"metaphlan": "fette", "kraken": "completo"},
 "programmi": {"metaphlan": "4.2.4", "bowtie2": "2.5.5", "kraken2": "2.17.2", "bracken": "3.1", "fastp": "1.4.0"},
 "database": [{"nome": "metaphlan_fette_vJan25_v1", "installato": true, "gb": 24.5}]}
```

- `modo_consigliato` viene dalle regole di System One v0 (D031): sotto ~40 GB di RAM, MetaPhlAn a fette.
- **[v0.2]** `consigli`: lista di `{"codice", "livello", "messaggio", "fonte"}` (§5.5). Quelli con `livello: "avviso"`
  arrivano anche come eventi `avviso`; quelli `"info"` solo qui (per esempio `MODO_METAPHLAN`).

### 5.2 `stima`

```json
{"campioni": 3, "coppie_totali": 4500000,
 "tempo_s": {"ospite": 900, "metaphlan": 838, "kraken": 7297}, "spazio_gb": 12}
```

- Regole di stima (misurate in S2.2-S2.3): Kraken completo ~37.000 coppie/min con 8 processori;
  MetaPhlAn a fette 86,2 s per milione di coppie + ~150 s fissi per campione.
- **[v0.2]** In più: `spazio_libero_gb` (disco dove andrà il lavoro) e `consigli` (§5.5: `TEMPO_LUNGO`,
  `SPAZIO_INSUFFICIENTE`, `DB_MANCANTE`). Le dimensioni si chiedono **a gruppi**: una richiesta a ENA ogni 100
  campioni, e una a NCBI ogni 100 per quelli che ENA non conosce o se ENA non risponde (94 campioni in ~1 s).

### 5.3 `esegui`: cartella dei risultati

```
<cartella del progetto>/risultati/
  risultati.json            # indice di tutto (sotto)
  metaphlan/<campione>_profile.txt
  kraken/<campione>.bracken, <campione>.k2report
  tabelle/ (matrici unite, parameters.tsv, triage.tsv se il triage è attivo)
  referto/ referto.html, referto.pdf, referto.xlsx      [v0.2]
  sicurezza/<campione>.json                              [v0.2, se calcolata]
  log/
```

`risultati.json`:

```json
{"motore": "0.1.0", "corsa": "2026-10-15T10-00-00",
 "campioni": [{"nome": "SF3RAt7", "esito": "ok", "coppie_dopo_ospite": 1507887,
               "file": {"metaphlan": "metaphlan/SF3RAt7_profile.txt", "kraken": "kraken/SF3RAt7.bracken"}}],
 "parametri": {"metaphlan_modo": "fette", "kraken_db": "completo", "kraken_confidence": 0.0},
 "versioni": {"metaphlan": "4.2.4", "database_metaphlan": "mpa_vJan25_CHOCOPhlAnSGB_202503"},
 "citazioni": ["..."]}
```

- `citazioni`: gli strumenti e i database davvero usati nella corsa (D036), da mostrare in fondo al referto.
  **[v0.2]** con DOI, verificate su PubMed; `parametri` = le righe di `tabelle/parameters.tsv` (`metaphlan_mode`,
  `kraken_profile`, `kraken_confidence`, `bracken_min_reads`, `abundance_threshold_pct`, `hosts`, ...);
  `versioni` anche di Bracken, Bowtie 2, fastp e il database di Kraken.
- **[v0.2]** Per ogni campione `sintesi` (l'interfaccia mostra, non calcola, D006), MetaPhlAn e Kraken separati:

```json
"sintesi": {
 "metaphlan": {"specie": 27, "dominanti": [{"nome": "Latilactobacillus sakei", "pct": 21.617793}],
               "non_assegnata_pct": 53.651104,
               "frase": "MetaPhlAn: 27 specie sopra la soglia; dominano Latilactobacillus sakei (21,6 % delle read), ... Il 53,7 % delle read non è assegnato a specie note."},
 "kraken": {"microbi": 48, "dominanti": [{"nome": "Latilactobacillus sakei", "pct_microbi": 37.16}],
            "non_microbi": [{"nome": "Homo sapiens", "gruppo": "altri eucarioti", "pct": 0.054, "letture": 74}],
            "frase": "Kraken: 48 microbi sopra la soglia; dominano ... Segnalati a parte (non microbi o virus): Leishmania mexicana 0,082 %, Homo sapiens 0,054 %, ..."}}
```

  `dominanti`: le prime 3 sopra la soglia di abbondanza (MetaPhlAn in % sul totale delle read, Kraken in % fra i
  soli microbi); `non_microbi`: tutto ciò che Kraken assegna fuori da batteri, archei e funghi (D023).
- **[v0.2]** Campi nuovi: `triage` (`[{"campione", "esito": "buono" | "da controllare" | "da rifare", "motivi", "punteggio"}]`,
  vuoto se il triage non è attivo), `consigli` (§5.5), `referto` (`{"html", "pdf", "xlsx"}`: percorsi dentro
  `risultati/`, `null` se quel file manca).

#### Referto [v0.2]

- Italiano semplice, termini tecnici spiegati (riquadro "Parole usate", D027).
- **MetaPhlAn e Kraken in tabelle e fogli Excel separati, mai fusi.** MetaPhlAn: specie con "% sul totale delle read"
  (come le scrive MetaPhlAn) e "% fra le specie trovate"; UNCLASSIFIED detto a parte. Kraken: solo batteri, archei,
  funghi (dall'albero del report), con "% fra i soli microbi" e "% sul totale assegnato"; *Homo*, *Leishmania*,
  altri eucarioti e virus in una tabella "segnalati a parte" (D023). Nelle tabelle solo le specie sopra la soglia di
  abbondanza; l'Excel le ha tutte.
- Parametri usati con la fonte (D022, fonti di `refs/kraken_profili.tsv`), "Strumenti e database usati" con versioni
  e citazioni (D036), postilla sui virus (D017, D033), sezione "Sicurezza alimentare" solo se c'è `risultati/sicurezza/`.
- Il PDF lo fa il motore dallo stesso HTML (Qt, già nell'ambiente `pmn_reports_py`): l'interfaccia non deve
  convertire nulla. Fogli Excel: `Leggimi`, `MetaPhlAn_specie`, `Kraken_microbi`, `Kraken_a_parte`, `Triage`,
  `Sicurezza`, `Parametri`, `Strumenti_citazioni` (gli ultimi tre fissi, `Triage` e `Sicurezza` solo se ci sono).

### 5.4 `sicurezza` [v0.2]

Ingresso (`--ingresso`, JSON; stesso schema di `steps/45_previsione_fssp.py`):

```json
{"modalita": "migliorata",
 "prodotto": {"temperatura": 5, "sale_fase_acquosa": 3.0, "ph": 6.2, "nitrito": 60, "acidi": {"lattico": 7000}},
 "giorni": 30,
 "conte": {"lab_ufc_g": 10000},
 "campione": "SF3RAt7"}
```

- `modalita`: `migliorata` (predefinita, D048) o `fssp` (fedele a FSSP). Al posto di `giorni`, `profilo_temperatura`:
  `[[temperatura, ore], ...]`. Al posto del sale, `aw`. `conte` facoltativo: `lab_ufc_g` oppure `totale_ufc_g` (D019).
- Il profilo delle specie: `profilo_specie` (`{nome: %}`) oppure, con `--progetto`, il **profilo MetaPhlAn** del
  campione in `risultati/` (`campione` serve solo se i campioni sono più di uno). Mai Kraken (D016).
- Scenari *Listeria* **1 e 100 ufc/g sempre** (cambiabili con `scenari_listeria_ufc_g`). Modello LAB solo per
  *L. sakei*/*L. curvatus*; per *Leuconostoc*, *Weissella*, *Carnobacterium* una nota (Mejlholm & Dalgaard 2013).

Uscita (`fine.risultato`):

```json
{"modalita": "migliorata", "campione": "SRR4875279", "profilo_usato": "MetaPhlAn, campione SRR4875279 (...)",
 "previsioni": [{"scenario": "Listeria 1 ufc/g (e se)", "modello": "listeria", "listeria_puo_crescere": false,
                 "psi_listeria": 1.53, "mu_listeria_h": 0.0, "cento_volte_listeria_giorni": null,
                 "curva": {"giorni": [...], "log_listeria": [...]}}],
 "avvisi": [{"codice": "FUORI_CAMPO", "modello": "listeria", "fattore": "ph", "valore": 5.4, "campo": [5.6, 7.7], "messaggio": "..."}],
 "note": ["..."], "ponte": {"listeria_trovata": false, "lab_trovati": ["latilactobacillus sakei"], "specie_non_coperte": ["..."]},
 "citazione": "Previsioni basate sui modelli del Food Spoilage and Safety Predictor (FSSP) 4.0 ...",
 "richiesta": {"prodotto": {...}, "giorni": 30}, "file": "<progetto>/risultati/sicurezza/SRR4875279.json"}
```

- Con il modello *Listeria* + LAB ci sono anche `mu_lab_h`, `psi_lab`, `cento_volte_lab_giorni`,
  `sette_log_lab_giorni` e `curva.log_lab`. Le curve hanno un punto all'ora.
- L'interfaccia mostra `note` e gli avvisi così come sono (sono già in italiano).

### 5.5 System One v0: le regole [v0.2]

Consigliano e non calcolano (D031): nessun comando cambia da solo una scelta dell'utente.
Codice: `motore/system_one.py`. Ogni consiglio porta la sua `fonte`.

| Regola | Soglia | Codice | Fonte |
|---|---|---|---|
| Modo MetaPhlAn | `standard` solo con RAM ≥ 40 GB **e** indice intero installato, altrimenti `fette` | `MODO_METAPHLAN` (info) | S2.1 (picco 25,5 GB), PC da 31,4 GB non basta; D051 |
| Memoria troppo poca | RAM visibile < 7,5 GB | `RAM_INSUFFICIENTE` | fette provate con WSL a 8 GB (14/10) |
| Database Kraken | completo se installato, altrimenti rapido con avviso; scelto ma non installato | `DB_MANCANTE` | installazione del motore |
| Tempo | stima totale > 4 h | `TEMPO_LUNGO` | D023 |
| Spazio | spazio stimato × 1,15 > spazio libero | `SPAZIO_INSUFFICIENTE` | regola di `steps/05` |
| Triage | `pass` / `review` / `exclude` di `steps/17` → buono / da controllare / da rifare, con i motivi | `CAMPIONE_DA_CONTROLLARE`, `CAMPIONE_DA_RIFARE` | soglie `triage.*` del progetto (host 95 %, 1 M frammenti, Q30 70 %) |

## 6. Finto motore

- `installer/finto_motore.py`: stessi comandi, stessi eventi, tempi accorciati, risultati presi da
  una corsa vera di SF3RAt7 (`installer/finto/`). Serve solo per costruire l'interfaccia; non si installa per gli utenti.
- `python installer/finto_motore.py <comando> [--progetto config.yaml] [--corsa ID] [--velocita N] [--scenario S]`:
  `--velocita` = quante volte più veloce del vero (predefinito 60, `0` = senza attese);
  `--scenario` = `ok`, `DB_MANCANTE`, `GIA_IN_CORSO`, `annullata`, `READ_NON_TROVATE`, `TEMPO_LUNGO`,
  **[v0.2]** `CAMPIONE_DA_CONTROLLARE` (esito del triage).
- **[v0.2]** `sicurezza` fa il calcolo vero (`motore/sicurezza.py`: Python puro, istantaneo); `esegui` copia il referto
  vero di SF3RAt7 (`installer/finto/referto/`); `referto` lo rifà con `motore/referto.py` (HTML sempre, Excel e PDF
  se ci sono `openpyxl` e PySide6, altrimenti `REFERTO_PARZIALE`); `info` e `stima` danno i consigli con le regole vere.
- Come il vero: un solo `esegui` alla volta (`GIA_IN_CORSO`) e `annulla --corsa <id>` ferma davvero la corsa.
- `tests/test_finto_motore.py` controlla ogni comando e scenario contro il §4; **[v0.2]** anche `tests/test_sicurezza.py`,
  `tests/test_referto.py`, `tests/test_system_one.py`, `tests/test_stima_gruppi.py`.

## 7. Cosa NON fa l'interfaccia

- Non legge né modifica i file dei database.
- Non calcola profili, soglie o stime: le chiede al motore.
- Non mostra all'utente testi in inglese del log tecnico: solo `messaggio` e `cosa_fare`.
