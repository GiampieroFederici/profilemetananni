# Contratto motore-interfaccia · Engine-GUI contract (v0.3, 16/10/2026)

> Regola (D006, standard RAPID): **l'interfaccia non fa scienza**. Mostra, chiede, lancia.
> Tutto il calcolo sta nel motore, dentro WSL2 (Windows) o Linux.
> Questo documento è il patto fra i due: se l'interfaccia lo rispetta, può essere costruita
> subito contro un **finto motore** che risponde allo stesso modo (D032).
>
> **v0.2 (16/10/2026, filone "Motore, seconda parte", D055):** comandi `sicurezza` e `referto`, referto in
> `risultati/referto/`, consigli di System One v0, `stima` a gruppi. Le aggiunte sono segnate **[v0.2]**;
> tutto ciò che c'era in v0 resta valido.
>
> **v0.3 (16/10/2026, filone "richieste dell'app", dopo S5b e S6):** regola prodotto → ospite in `info.prodotti`,
> `stima.tempo_totale_s` e `stima.nomi_campioni`, Bracken `-t` dal progetto, nomi dei campioni locali come in `bin/run.sh`,
> fonti dei parametri in italiano, `dominanti` fino a 15 specie, valore finale in ufc/g negli scenari di sicurezza,
> `REFERTO_PARZIALE` e `fine` dopo un errore con testi in italiano più precisi, numeri all'italiana negli avvisi FSSP,
> finto motore con lucchetto a pid e `stima` coerente con `esegui`. Aggiunte segnate **[v0.3]**: solo campi nuovi o testi
> migliori, nessun campo tolto o rinominato (l'interfaccia v0.2 continua a funzionare).
>
> **[lingua, 18/10/2026, ramo `lingua-it-en`]** Opzione `--lingua it|en` per tutti i comandi (§1): i testi per l'utente
> (eventi, referto, FSSP) nella lingua scelta. Senza l'opzione tutto resta come prima, in italiano: nessun campo nuovo,
> tolto o rinominato. Aggiunte segnate **[lingua]**.

> **[v1.1, 30/10/2026, installatore]** `installa` scarica a pezzi e più sorgenti insieme (D165): solo **campi nuovi
> facoltativi** in `avanzamento` (`byte_fatti`, `byte_totali`, `velocita_mb_s`, `sorgente`, `sorgenti`) e nel risultato
> di `--stima` (`spazio_necessario_byte`, `spazio_libero_byte`, `sorgenti`); nessun campo tolto o rinominato.
> Aggiunte segnate **[v1.1]**.

---

## 1. Come si chiama il motore

- Un solo programma: `pmn-motore <comando> [opzioni]`, installato da `installer/installa_motore.sh`
  in `~/.pmn/bin/pmn-motore`.
  **Esiste dal 16/10/2026** (`motore/pmn-motore` + `motore/pmn_motore.py`, D053): stessi comandi ed eventi del
  finto motore; `installa` passa all'installatore, `esegui` lancia `bin/run.sh`, `verifica` lancia `installer/verifica_motore.sh`.
- Da Windows: `wsl.exe -d pmn -u pmn -e /home/pmn/.pmn/bin/pmn-motore <comando> ...` (utente `pmn` e percorso assoluto, come `app/motore.py`).
- Da Linux: direttamente.
- **[lingua]** `--lingua it|en` vale per ogni comando (predefinita `it`; anche la variabile `PMN_LINGUA`). L'app la passa
  solo quando l'utente ha scelto l'inglese, quindi con l'italiano i comandi sono identici a prima. Il motore la passa a
  `motore/referto.py` (variabile `PMN_LINGUA`). Testi: `motore/lingua.py` + `motore/lingua_en.json` (l'italiano è nel
  codice ed è la chiave del catalogo). `installa` per ora resta in italiano (`installer/installa_motore.sh`, bash).
- **stdout** = solo eventi JSON, uno per riga (JSON Lines, §4). **stderr** = vuoto o diagnostica breve.
  I dettagli tecnici vanno nel file di log indicato nell'evento `inizio`.

## 2. Comandi

| Comando | Cosa fa | Ingresso | Uscita (evento `fine`, campo `risultato`) |
|---|---|---|---|
| `info` | descrive PC e installazione, senza calcoli lunghi | nessuno | §5.1 |
| `installa` | installa o completa programmi e database; riprende da dove era rimasto | `--catalogo <file o URL>` (predefinito: quello dell'installazione) | `{"programmi": 8, "database": [gruppi del catalogo], "verifica": "verde"}`; con `--stima`: `{"da_scaricare_gb", "spazio_necessario_gb", "spazio_libero_gb", "velocita_mb_s", "tempo_stimato_s"}`; **[v1.1]** in più `spazio_necessario_byte`, `spazio_libero_byte` (byte esatti: l'unica regola dello spazio, la legge anche `installa_pmn.ps1`) `da_scaricare_byte` (byte esatti di `da_scaricare_gb`: alla ripresa senza i pezzi già sul disco) e `sorgenti` (`[{"sorgente", "da_scaricare_gb", "da_scaricare_byte", "velocita_mb_s", "velocita_da_sola_mb_s", "tempo_stimato_s"}]`, `null` se non misurata); **[B1]** `velocita_mb_s` è misurata con tutte le sorgenti insieme, `velocita_da_sola_mb_s` con la sorgente da sola; `tempo_stimato_s` (totale e per sorgente) viene da una simulazione: le sorgenti vanno alla velocità misurata insieme, quando una finisce la sua banda passa alle altre ma nessuna supera la sua velocità da sola (vale sia se il limite è la linea del PC sia se è ogni connessione); lo stesso calcolo dà `eta_s` durante lo scarico |
| `verifica` | MD5 dei database + mini-campione di regressione (D032) | nessuno | `{"esito": "verde" \| "rosso", "controlli": [...]}` |
| `stima` | tempo e spazio previsti, prima di partire (D023, D034) | `--progetto <config.yaml>` | §5.2 |
| `esegui` | analisi completa del progetto | `--progetto <config.yaml>` | §5.3 |
| `annulla` | ferma una corsa in modo pulito, di `esegui` o di `installa` (il codice `corsa` dell'evento `inizio`) | `--corsa <id>` | `{"annullata": true}` |
| `sicurezza` **[v0.2]** | previsioni di crescita (FSSP: *Listeria*, LAB) per un prodotto | `--ingresso <richiesta.json>` [`--progetto <config.yaml>`] | §5.4 |
| `referto` **[v0.2]** | rifà il referto di un progetto già analizzato (per esempio dopo `sicurezza`) | `--progetto <config.yaml>` | `{"cartella", "referto": {"html", "pdf", "xlsx"}}` |

- Un solo `esegui` alla volta (un campione alla volta, D016): un secondo `esegui` risponde con l'errore `GIA_IN_CORSO`.
- `installa` ed `esegui` sono **riprendibili**: rilanciati con gli stessi ingressi, saltano ciò che è già fatto e verificato.
  **[22/10]** Con parametri diversi (ospite, database o confidence di Kraken, modalità o indice di MetaPhlAn) `esegui`
  rifà le uscite fatte con quelli vecchi (timbro dei parametri accanto alle uscite, P01 della revisione): il referto
  dichiara sempre i parametri che hanno prodotto i numeri. Una cartella senza timbro (corse di prima) si rifà.
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
- **[v0.3]** `profiling.bracken_min_reads` (Bracken `-t`, numero intero ≥ 0): vuoto o assente = valore consigliato del
  profilo del database in `refs/kraken_profili.tsv` (oggi 10), come `kraken_confidence` e `abundance_threshold_pct` (D080);
  un valore scritto vince. Un valore non valido dà `CONFIG_NON_VALIDA`. Il referto dice se è il consigliato o "scelto nel progetto".
- **[v0.3]** Read locali (`data_source: local`): il nome del campione è il nome del file senza il suffisso della prima read,
  con le stesse regole di `bin/run.sh`: `C1_R1.fastq.gz` + `C1_R2.fastq.gz` = `C1` (anche `_1`/`_2`, `_R1_001`/`_R2_001`,
  `.fq.gz`); un file a coppia senza la sua compagna si salta; ogni altro `.fastq.gz`/`.fq.gz` è un campione a lettura
  singola (nome = file senza estensione). Nomi ammessi: lettere, cifre, `.`, `_`, `-`, al massimo 64, non all'inizio `-` o `.`.
- L'interfaccia scrive il file; il motore lo **valida** (lettura sicura, `yaml.safe_load`) e risponde con
  `errore` e codice `CONFIG_NON_VALIDA` se qualcosa non va, indicando il campo.

## 4. Eventi (stdout, JSON Lines)

Ogni riga è un oggetto JSON con `tipo` e `ora` (ISO 8601). Testi in **italiano semplice** (D027); **[lingua]** in inglese
semplice con `--lingua en`. Codici, `tipo`, `passo` ed `esito` non cambiano mai con la lingua.

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
- **[v1.1]** In `installa`, durante lo scarico dei database, un `avanzamento` **almeno ogni 30 s** (il motore lo manda
  ogni 15 s, anche dentro un file da 85 GB) con i campi nuovi facoltativi: `byte_fatti` e `byte_totali` (tutti i
  database del catalogo, già scaricati compresi), `velocita_mb_s` (somma delle sorgenti, media degli ultimi ~60 s),
  `sorgente` (quella che decide il tempo che manca, la più lenta, o `null`) e `sorgenti`
  (`[{"sorgente", "byte_fatti", "byte_totali", "velocita_mb_s"}]`, una voce per sorgente del catalogo: `kraken`,
  `pmn`). `eta_s` si ricalcola a ogni evento con la velocità vera di ogni sorgente; `percentuale` = 22 + 70 × byte
  fatti / byte totali e non torna indietro. Gli eventi d'inizio file ("Scarico ...") restano senza questi campi.
  Chi non li conosce li ignora.
- **[v0.2]** `passo` `sicurezza` (un avanzamento per scenario) e `referto` (ultimo passo di `esegui`, e del comando `referto`).
- L'interfaccia mostra `messaggio` così com'è; per la barra usa `percentuale` ed `eta_s`.
- **[v0.2]** Testi per l'utente con le vere lettere accentate (è, à, ù, perché), mai l'apostrofo al posto dell'accento.
  `cosa_fare` per motore mancante: "Apri la pagina Motore e premi Installa." (la pagina dell'app si chiama "Motore").
- **[v0.2]** In `esegui` `eta_s` è calcolato con le stesse regole di `stima` (§5.2) e scende a ogni evento: secondi
  per finire il passo in corso più i passi dopo. Il download non è stimato (dipende dalla rete); se le dimensioni
  dei campioni non si possono chiedere (rete giù) `eta_s` resta `null`.
- **[17/10]** `eta_s` e `percentuale` seguono il piano per campione nell'ordine vero di `bin/run.sh` (download, triage,
  pulizia e ospite per campione, MultiQC, poi MetaPhlAn e Kraken **alternati** per campione, riepilogo, referto):
  `eta_s` = il passo che parte, contato intero, più i passi non ancora partiti; `percentuale` = la parte di tempo già
  fatta (all'inizio di Kraken di SF3RAt7: 37 %, non più 95 %). Un passo di un gruppo prima di quello in corso che non è
  partito, `run.sh` l'ha saltato e non si conta; in una corsa ripresa non si contano i passi con l'uscita già sul disco
  (read scaricate, read senza ospite, profilo MetaPhlAn, Bracken). Il download ora è stimato. `percentuale` non torna
  mai indietro. L'interfaccia fra due eventi fa scendere da sé il tempo che manca e avanzare la barra con un orologio
  locale (un passo come Kraken dura anche mezz'ora); se il passo dura più del previsto scrive "qualche minuto".
- **[17/10, A1]** In `esegui` ogni `avanzamento` ha anche `passo_s`: i secondi previsti per il passo che parte (0 se
  già fatto, `null` se `eta_s` è `null`). L'orologio locale dell'interfaccia fa scendere `eta_s` solo per `passo_s`:
  se il passo sfora (SF3RAt3: download previsto 3 min, durato 37 con la rete lenta) tempo e barra si fermano a quello
  che resta dopo il passo, con la nota "tempo che manca dopo questo passo, che sta durando più del previsto".
  Senza `passo_s` (motore più vecchio) vale la regola di prima. Il finto motore lo manda anche lui.
- **[v0.2]** `errore.passo`: il passo dell'ultimo `avanzamento` (o quello in cui l'errore è nato, per esempio
  `kraken` per `DB_MANCANTE` di Kraken). **[22/10]** Anche l'installatore: il passo in corso (`controllo`,
  `programmi`, `database`, `verifica`), e `risultato` = `{"codice", "passo"}` nel `fine` (D068: ora obbligatorio).
- Ogni corsa finisce **sempre** con un solo evento `fine`, anche dopo un errore.
- **[v0.3]** `fine` dopo un errore: `messaggio` dice dove si è fermato, che cosa è successo e che cosa fare, già pronto
  ("Problema durante la classificazione con Kraken e Bracken. Manca il database di Kraken. Apri la pagina Motore e premi
  Installa."; senza "Problema durante..." se l'errore è nato prima del primo passo). `risultato` = `{"codice", "passo"}`
  (`passo` come in `errore`, o `null`).

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
| `REFERTO_PARZIALE` | avviso | `esegui`/`referto`: manca il PDF o l'Excel (la pagina HTML c'è sempre). **[v0.3]** Testo solo in italiano, per esempio "Il referto non è completo: manca l'Excel: nel motore non c'è il modulo che lo scrive (openpyxl). La pagina del referto si apre lo stesso."; il dettaglio tecnico va nel log |
| `KRAKEN_VUOTO` | avviso | **[v1.1]** `esegui`/`referto`: in un campione nessuna specie arriva alle read minime di Bracken (`-t`), quindi il suo profilo di Kraken è vuoto ma valido e l'analisi continua (MetaPhlAn, referto). Esempio: "Kraken: nessuna specie con almeno 10 read in ERR2603036; il profilo di Kraken di questo campione è vuoto." |
| `METAPHLAN_VUOTO` | avviso | **[v1.1]** `esegui`/`referto`: MetaPhlAn non trova specie in un campione (profilo con la sola riga UNCLASSIFIED, per esempio read casuali), quindi il suo profilo di MetaPhlAn è vuoto ma valido: il campione resta fuori dalla matrice di MetaPhlAn, dalla diversità e dal multicampione, il referto scrive una frase al suo posto e l'analisi continua. Esempio: "MetaPhlAn: nessuna specie trovata in CASUALE; il profilo di MetaPhlAn di questo campione è vuoto." |

Anche `RAM_INSUFFICIENTE`, `SPAZIO_INSUFFICIENTE`, `DB_MANCANTE`, `TEMPO_LUNGO` possono arrivare come **avviso**
da `info` e `stima` (consigli di System One v0, §5.5): consigliano, non fermano nulla.
**[v1.1]** In `esegui`, se Linux chiude un programma perché la memoria è finita (`Killed`, codice 137 di bowtie2 o MetaPhlAn) l'errore è `RAM_INSUFFICIENTE`, non `ERRORE_INTERNO`: "L'analisi si è fermata perché la memoria del computer non basta.", con che cosa fare (chiudere gli altri programmi e riprovare; sotto 16 GB l'analisi non può finire).
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
- **[v0.3]** `prodotti`: la regola prodotto → ospite (System One v0, §5.5), nell'ordine del menu del passo 1 (D074).
  L'interfaccia scrive `ospiti` in `hosts:` del progetto e mostra `frase` e `perche` così come sono; il DNA umano (GRCh38)
  si toglie sempre (`filter_human`).

```json
"prodotti": [{"prodotto": "maiale", "ospiti": ["sus_scrofa"], "genomi": ["Sscrofa11.1"],
              "frase": "Toglierò il DNA del maiale e quello umano.", "perche": "Sono la gran parte delle read...",
              "livello": "info", "fonte": "D021: ..."},
             {"prodotto": "bovino", "ospiti": ["bos_taurus"], "genomi": ["ARS-UCD1.2"], ...},
             {"prodotto": "pecora", "ospiti": ["ovis_aries"], "genomi": ["ARS-UI_Ramb_v2.0"], ...},
             {"prodotto": "altro", "ospiti": [], "genomi": [], "frase": "Toglierò solo il DNA umano.", "livello": "avviso", ...}]
```

- **[17/10, sessione A]** `esempio`: il campione d'esempio a un clic, cioè il mini-campione della verifica (200.000 coppie
  di SF3RAt7, già nel motore in `PMN_PROVA`), oppure `null` se non è installato. `cartella` è già come la vede il motore:
  l'interfaccia la scrive così com'è in `paths.local_reads_dir` (con `data_source: local`) e `hosts:` dalla regola di
  `prodotto`. Il finto motore dà lo stesso oggetto (la cartella non la legge). Sul PC di casa: stima 389 s, reale 348 s.

```json
"esempio": {"campione": "mini_SF3RAt7", "prodotto": "maiale", "coppie": 200000, "cartella": "/home/pmn/.pmn/db/prova",
            "frase": "200.000 coppie di read di SF3RAt7 (SRR4875279), un salame a fermentazione spontanea campionato al giorno 7 di stagionatura, già nel motore."}
```

### 5.2 `stima`

```json
{"campioni": 1, "coppie_totali": 3240847,
 "tempo_s": {"download": 130, "controllo_qualita": 15, "pulizia": 18, "ospite": 327, "metaphlan": 361,
             "kraken": 1426, "riepilogo": 10, "referto": 10}, "tempo_totale_s": 2297, "spazio_gb": 3.2}
```

- **[v0.3, 17/10]** Regole di stima (`tempi()` e `piano()` in `motore/pmn_motore.py`), misurate in S2.2-S2.3 e nella
  prova L1a del 17/10 (SF3RAt7 su NVMe, 24 processori: 37 min 39 s dall'inizio al referto; l'esempio qui sopra è la
  sua stima, 38 min):

  | Passo | Regola | Misura |
  |---|---|---|
  | `download` | byte delle read gz (ENA) / 4,1 MB/s; 0 per le read locali | 533,5 MB in 129 s (rete di casa) |
  | `pulizia` | 5,6 s per milione di coppie | fastp 18 s per 3,24 M |
  | `ospite` | 101 s per milione di coppie (non scala con i processori) | 325 s (S2.2), 327 s con 24 processori |
  | `metaphlan` | 86,2 s per milione di coppie **senza ospite** + 230 s fissi per campione | 357 s per 1,51 M |
  | `kraken` | coppie **senza ospite** / (37.000 al minuto × √(processori / 8)); rapido 10 M al minuto | 40 min 47 s con 8 (K2), 1.415 s con 24 |
  | `controllo_qualita`, `riepilogo`, `referto` | 15 s, 10 s, 10 s fissi; triage (se attivo) 60 s per campione, non misurato | MultiQC 3-16 s, tabelle 4 s, referto 1 s |

- Coppie senza ospite: dal triage (`results/triage.tsv`, colonna `host_pct`) se c'è; altrimenti il 53 % delle coppie
  è dell'ospite quando il progetto ne toglie uno (`hosts:` non vuoto: SF3RAt7, maiale, 3,24 M → 1,51 M; bovino e
  pecora non ancora misurati), 0 % se si toglie solo l'uomo (prudente).
- **[17/10, A1]** In `esegui`, appena l'ospite è tolto (dal passo MultiQC in poi) `eta_s` ricalcola MetaPhlAn e Kraken
  sulle coppie rimaste davvero, lette dai log di Bowtie2 di `steps/21` (`hostfilter_logs/`, `quote_ospite()`): prima
  entrate nel primo indice, poi rimaste dopo l'ultimo. Prova del 17/10 su SF3RAt3 (68 % di ospite, non 53 %): all'inizio
  di Kraken `eta_s` 1.954 s con la quota fissa, 1.324 s con i log, reale 1.533 s (+27,5 % → −13,6 %). La `stima` prima
  di partire resta con la quota fissa (scelta del 17/10): su SF3RAt3 3.026 s contro 4.598 s reali, di cui
  2.229 s di download con la rete lenta.
- Processori: `execution.threads` (quelli che `run.sh` usa davvero), poi `motore.processori`, poi 8.
  La radice quadrata per Kraken viene da 2 sole misure (8 e 24 processori): da riconfermare su altri PC.
- Prima del 17/10 Kraken e MetaPhlAn contavano le coppie **prima** di togliere l'ospite e download, pulizia, MultiQC e
  referto non c'erano: SF3RAt7 era stimato 1,7 ore contro 37 min veri.
- **[v0.2]** In più: `spazio_libero_gb` (disco dove andrà il lavoro) e `consigli` (§5.5: `TEMPO_LUNGO`,
  `SPAZIO_INSUFFICIENTE`, `DB_MANCANTE`). Le dimensioni si chiedono **a gruppi**: una richiesta a ENA ogni 100
  campioni, e una a NCBI ogni 100 per quelli che ENA non conosce o se ENA non risponde (94 campioni in ~1 s).
- **[v0.3]** `tempo_totale_s`: la somma di `tempo_s`, già pronta (**[17/10]** download compreso); `nomi_campioni`: i
  nomi con cui il motore chiamerà i campioni (codici SRR, e per le read locali le regole del §3), nello stesso ordine
  del conteggio.
- **[17/10]** `tempo_s` ha una chiave per ogni passo di `esegui` (più `referto`), nell'ordine in cui girano; chi è 0
  non gira (per esempio `kraken` con solo MetaPhlAn). Nessuna chiave tolta: le 3 di prima restano.

### 5.3 `esegui`: cartella dei risultati

```
<cartella del progetto>/risultati/
  risultati.json            # indice di tutto (sotto)
  metaphlan/<campione>_profile.txt
  kraken/<campione>.bracken, <campione>.k2report
  tabelle/ (matrici unite, parameters.tsv, triage.tsv se il triage è attivo)
  referto/ referto.html, referto.pdf, referto.xlsx      [v0.2]
  sicurezza/<campione>.json                              [v0.2, se calcolata]
  qc/ <progetto>_multiqc_report.html (+ cartella _data/), <campione>_fastp.html, fastqc/*_fastqc.html   [v0.4]
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
               "frase": "MetaPhlAn: 27 specie trovate; dominano Latilactobacillus sakei (21,6 % delle read), ... Il 53,7 % delle read non è assegnato a specie note."},
 "kraken": {"microbi": 48, "dominanti": [{"nome": "Latilactobacillus sakei", "pct_microbi": 37.16}],
            "non_microbi": [{"nome": "Homo sapiens", "gruppo": "altri eucarioti", "pct": 0.054, "letture": 74}],
            "frase": "Kraken: 48 taxa sopra la soglia; dominano ... Segnalati a parte (non del prodotto, o virus): Leishmania mexicana 0,082 %, Homo sapiens 0,054 %, ..."}}
```

  `dominanti`: le prime 3 (MetaPhlAn tutte le specie, nessuna soglia, D128, in % sul totale delle read; Kraken sopra la
  soglia di abbondanza, in % fra i soli taxa del prodotto); `non_microbi`: tutto ciò che Kraken assegna fuori da batteri, archei e funghi (D023).
  **[v0.3]** `dominanti` arriva fino a **15** specie sopra la soglia (in ordine di abbondanza; meno se sopra la soglia
  ce ne sono meno); la `frase` continua a nominarne 3. Il resto delle specie resta nel referto e nell'Excel.
- **[v0.2]** Campi nuovi: `triage` (`[{"campione", "esito": "buono" | "da controllare" | "da rifare", "motivi", "punteggio"}]`,
  vuoto se il triage non è attivo), `consigli` (§5.5), `referto` (`{"html", "pdf", "xlsx"}`: percorsi dentro
  `risultati/`, `null` se quel file manca).
- **[v0.4, 22/10]** Campo `qc`: il controllo qualità delle read, copiato in `risultati/qc/` (report MultiQC con la sua
  cartella `_data/`, HTML di fastp, HTML di FastQC delle read grezze e pulite). Percorsi dentro `risultati/`;
  `multiqc` è `null` e le liste sono vuote se mancano (analisi di prima del 22/10). Per campione i numeri del referto,
  letti dal JSON di fastp (`summary`, `duplication`) e dai log di Bowtie 2 (`hostfilter_logs/`); "coppie" = read / 2
  se `a_coppie`, altrimenti read singole; `ospite_pct` e `coppie_profili` `null` se l'ospite non è stato tolto:

```json
"qc": {"multiqc": "qc/Salame_multiqc_report.html", "fastp": ["qc/C1_fastp.html"],
       "fastqc": ["qc/fastqc/C1_1_fastqc.html", "qc/fastqc/C1_trim_1_fastqc.html"],
       "campioni": [{"nome": "C1", "a_coppie": true, "coppie_prima": 2000000, "coppie_dopo": 1900000,
                     "q30_prima_pct": 91.2, "q30_dopo_pct": 95.4, "duplicati_pct": 7.3, "lunghezza_media": 145.0,
                     "ospite_pct": 70.0, "coppie_profili": 570000}]}
```

  FastQC (`steps/20_trim.sh`) è obbligatorio: se c'è ma non scrive il report, il passo `pulizia` si ferma (prima
  passava `-o`, che FastQC 0.13.0 non conosce, e l'errore restava un avviso nel log). Alla ripresa si rifanno solo i
  report che mancano. `versioni` ha anche `fastqc` e `multiqc`, `citazioni` anche FastQC e MultiQC.
- **[lingua]** I valori fissi restano chiavi italiane in ogni lingua (`triage.esito`: buono, da controllare, da rifare;
  `non_microbi.gruppo`: virus, altri eucarioti, altro; `modalita`: migliorata, fssp): l'interfaccia li traduce solo
  quando li mostra. I testi (`frase`, `motivi`, `citazioni`, `messaggio` dei consigli) sono scritti nella lingua della
  corsa e restano così: se poi si cambia lingua, li rifà una nuova analisi (il comando `referto` rifà il referto, non
  `risultati.json`).

#### Referto [v0.2]

- Italiano semplice, termini tecnici spiegati (riquadro "Parole usate", D027).
- **MetaPhlAn e Kraken in tabelle e fogli Excel separati, mai fusi.** MetaPhlAn: specie con "% sul totale delle read"
  (come le scrive MetaPhlAn) e "% fra le specie trovate"; UNCLASSIFIED detto a parte. Kraken: solo batteri, archei,
  funghi (dall'albero del report), con "% fra i taxa" e "% sul totale assegnato"; *Homo*, *Leishmania*,
  altri eucarioti e virus in una tabella "segnalati a parte" (D023). Kraken: nelle tabelle solo i taxa sopra la soglia di
  abbondanza, l'Excel li ha tutti; MetaPhlAn: tutte le specie, nessuna soglia (D128).
- Parametri usati con la fonte (D022, fonti di `refs/kraken_profili.tsv`, **[v0.3]** scritte in italiano), "Strumenti e database usati" con versioni
  e citazioni (D036), postilla sui virus (D017, D033), sezione "Sicurezza alimentare" solo se c'è `risultati/sicurezza/`.
- **[17/10, D115]** Le sezioni di Kraken e della sicurezza alimentare si aprono con il riquadro "Prototipo, non per
  decisioni." (`PROTOTIPO_KRAKEN`, `PROTOTIPO_FSSP` in `motore/referto.py`), come le pagine dell'app, finché K4 e L3
  non sono fatte.
- Il PDF lo fa il motore dallo stesso HTML (Qt, già nell'ambiente `pmn_reports_py`): l'interfaccia non deve
  convertire nulla. Fogli Excel: `Leggimi`, `MetaPhlAn_specie`, `Kraken_taxa`, `Kraken_a_parte`, `Triage`,
  `Sicurezza`, `Parametri`, `Strumenti_citazioni` (gli ultimi tre fissi, `Triage` e `Sicurezza` solo se ci sono).
  **[lingua]** Con l'inglese: `ReadMe`, `MetaPhlAn_species`, `Kraken_taxa`, `Kraken_separate`, `Triage`, `Safety`,
  `Parameters`, `Tools_citations`; numeri con il punto per i decimali e la virgola per le migliaia; `<html lang="en">`.
- **[R1, 18/10]** Sezione **"4. Diversità alfa"** (poi virus = 5): ricchezza, Shannon, Simpson **a profondità uguale**
  (quella del campione più povero; rarefazione, Schloss 2024), con l'avviso che la ricchezza dipende dalle read e, con un
  solo campione, che si confronta solo con campioni della stessa profondità. MetaPhlAn e Kraken in due tabelle e due
  fogli Excel separati (`Diversità_MetaPhlAn`, `Diversità_Kraken`; con l'inglese `Diversity_MetaPhlAn`,
  `Diversity_Kraken`). Kraken: taxa del prodotto sopra la soglia, valore atteso esatto della rarefazione delle letture di
  Bracken. MetaPhlAn: nessuna soglia; i profili rifatti a profondità uguale stanno in `risultati/metaphlan_pari/`
  (copiati da `results/alpha_metaphlan_pari/`, steps/42); tabelle anche in `risultati/tabelle/alpha_diversity_*.tsv`.
- **[v0.4, 22/10]** Sezione **"Controllo qualità delle read"** (numero che segue, prima di "Parametri usati"): per
  campione coppie prima e dopo fastp, % di basi ≥ Q30 prima e dopo, % di duplicati, lunghezza media dopo fastp, % di
  ospite tolto, coppie rimaste per i profili. Due tabelle di 5 colonne al massimo (il PDF di Qt rende male le tabelle
  larghe), una frase su come leggerle e il collegamento a `risultati/qc/<...>_multiqc_report.html`; senza `qc` una riga
  "non disponibile". Foglio Excel **`QC`** (stesso nome in inglese), prima di `Parametri`, solo se ci sono i numeri.
  Nell'app il pulsante "Apri il controllo qualità" apre il report MultiQC con il browser di Windows.

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
- **[v0.3]** Per ogni scenario `finale_listeria_ufc_g` (e con il modello *Listeria* + LAB anche `finale_lab_ufc_g`): la
  concentrazione alla fine della curva in ufc/g, cioè 10 alla potenza dell'ultimo log, **arrotondata a 2 cifre
  significative** (10^4,48 → 30000), pronta da mostrare come "circa 30.000 ufc/g" (D088): l'interfaccia non fa più 10^x.
- L'interfaccia mostra `note` e gli avvisi così come sono (sono già in italiano). **[v0.3]** Con i numeri all'italiana
  (virgola per i decimali, al massimo 2 cifre dopo la virgola, punto per le migliaia: "sale nella fase acquosa (%) =
  13,99", "(0,7-9)") e i nomi delle specie con la maiuscola ("Leuconostoc carnosum"). Anche i messaggi di
  `INGRESSO_NON_VALIDO` hanno i numeri all'italiana. I campi numerici (`valore`, `campo`) restano numeri JSON.
  `ponte.lab_trovati` e `ponte.specie_non_coperte` restano in minuscolo (sono chiavi, non testi).

### 5.5 System One v0: le regole [v0.2]

Consigliano e non calcolano (D031): nessun comando cambia da solo una scelta dell'utente.
Codice: `motore/system_one.py`. Ogni consiglio porta la sua `fonte`.

| Regola | Soglia | Codice | Fonte |
|---|---|---|---|
| Modo MetaPhlAn | `standard` solo con RAM ≥ 40 GB **e** indice intero installato, altrimenti `fette` | `MODO_METAPHLAN` (info) | S2.1 (picco 25,5 GB), PC da 31,4 GB non basta; D051 |
| **[v0.3]** Prodotto → ospite | maiale → `sus_scrofa` (Sscrofa11.1), bovino → `bos_taurus` (ARS-UCD1.2), pecora → `ovis_aries` (ARS-UI_Ramb_v2.0), altro → nessuno (avviso); l'uomo sempre | `info.prodotti` (non un codice) | D021, D074 |
| Memoria troppo poca | RAM visibile < 7,5 GB | `RAM_INSUFFICIENTE` | fette provate con WSL a 8 GB (14/10) |
| Database Kraken | completo se installato, altrimenti rapido con avviso; scelto ma non installato | `DB_MANCANTE` | installazione del motore |
| Tempo | stima totale > 4 h | `TEMPO_LUNGO` | D023 |
| Spazio | spazio stimato × 1,15 > spazio libero | `SPAZIO_INSUFFICIENTE` | regola di `steps/05` |
| Triage | `pass` / `review` / `exclude` di `steps/17` → buono / da controllare / da rifare, con i motivi | `CAMPIONE_DA_CONTROLLARE`, `CAMPIONE_DA_RIFARE` | soglie `triage.*` del progetto (host 95 %, 1 M frammenti, Q30 70 %) |

## 6. Finto motore

- `installer/finto_motore.py`: stessi comandi, stessi eventi, tempi accorciati, risultati presi da
  una corsa vera di SF3RAt7 (`installer/finto/`). Serve solo per costruire l'interfaccia; non si installa per gli utenti.
- `python installer/finto_motore.py <comando> [--progetto config.yaml] [--corsa ID] [--velocita N] [--scenario S]
  [--lingua it|en]`:
  `--velocita` = quante volte più veloce del vero (predefinito 60, `0` = senza attese);
  `--scenario` = `ok`, `DB_MANCANTE`, `GIA_IN_CORSO`, `annullata`, `READ_NON_TROVATE`, `TEMPO_LUNGO`,
  **[v0.2]** `CAMPIONE_DA_CONTROLLARE` (esito del triage).
- **[v0.2]** `sicurezza` fa il calcolo vero (`motore/sicurezza.py`: Python puro, istantaneo); `esegui` copia il referto
  vero di SF3RAt7 (`installer/finto/referto/`); `referto` lo rifà con `motore/referto.py` (HTML sempre, Excel e PDF
  se ci sono `openpyxl` e PySide6, altrimenti `REFERTO_PARZIALE`); `info` e `stima` danno i consigli con le regole vere.
- Come il vero: un solo `esegui` alla volta (`GIA_IN_CORSO`) e `annulla --corsa <id>` ferma davvero la corsa.
- **[lingua]** Con `--lingua en` `esegui` non copia il referto italiano di SF3RAt7: rifà `sintesi` con `motore/referto.py`,
  traduce le citazioni e rifà il referto (senza `openpyxl` nel Python dell'app: `REFERTO_PARZIALE`, come il vero).
- **[v0.3]** Il lucchetto `%TEMP%\pmn_finto\esegui.lock` contiene `{"corsa", "pid"}` come quello vero: se il processo che
  l'ha messo non c'è più (un `esegui` chiuso a metà) il lucchetto si toglie da solo e la corsa parte; anche un lucchetto
  nel formato vecchio (solo il codice della corsa) si toglie. Su Windows il controllo del pid usa `OpenProcess`.
- **[v0.3]** `stima` ed `esegui` usano gli stessi tempi per ospite, MetaPhlAn e Kraken, presi da `motore.kraken_db` del
  progetto: completo 41 min di Kraken, rapido 20 s (misurato su SF3RAt7 con PlusPF-8); i dati copiati restano quelli della
  corsa con lo screening rapido. `info.prodotti`, `stima.tempo_totale_s`, `stima.nomi_campioni` e i testi di `fine` e
  `REFERTO_PARZIALE` sono quelli del motore vero.
- **[17/10]** I tempi del finto vengono da `tempi()` del motore vero (§5.2) per SF3RAt7 (3,24 M coppie, 533,5 MB) con
  il progetto dato: stessi passi, stesso ordine di `run.sh` (MultiQC dopo l'ospite), stesso totale in `stima` ed `esegui`.
  Il finto e il vero non danno più due stime diverse per lo stesso progetto (prima 51 min contro 1,7 ore).
- `tests/test_finto_motore.py` controlla ogni comando e scenario contro il §4; **[v0.2]** anche `tests/test_sicurezza.py`,
  `tests/test_referto.py`, `tests/test_system_one.py`, `tests/test_stima_gruppi.py`.

## 6b. Server MCP [R1, 18/10, D130]

- `pmn_mcp/server.py` (SDK ufficiale `mcp` 2.3.0, ambiente `pmn_mcp/.venv`): gli stessi comandi (`info`, `stima`,
  `esegui`, `annulla`, `referto`, `sicurezza`) per gli assistenti compatibili MCP, con gli stessi eventi di questo
  contratto (restituiti in `eventi`; `avanzamento` anche come "progress" MCP). Aiuti in più che non toccano il motore:
  `progetti`, `stato`. Solo stdio (nessuna porta); `esegui` solo con la conferma della persona; progetto = `config.yaml`
  dentro la cartella dei progetti. Lancia il motore come l'app (`wsl.exe -d pmn -u pmn -e pmn-motore`), o il finto con
  `PMN_MOTORE=finto`. Istruzioni per i client in `pmn_mcp/LEGGIMI.md`; test `tests/test_mcp.py`.

## 7. Cosa NON fa l'interfaccia

- Non legge né modifica i file dei database.
- Non calcola profili, soglie o stime: le chiede al motore.
- Non mostra all'utente testi in inglese del log tecnico: solo `messaggio` e `cosa_fare`.
