# Contratto motore-interfaccia · Engine-GUI contract (v0, 15/10/2026)

> Regola (D006, standard RAPID): **l'interfaccia non fa scienza**. Mostra, chiede, lancia.
> Tutto il calcolo sta nel motore, dentro WSL2 (Windows) o Linux.
> Questo documento è il patto fra i due: se l'interfaccia lo rispetta, può essere costruita
> subito contro un **finto motore** che risponde allo stesso modo (D032).

---

## 1. Come si chiama il motore

- Un solo programma: `pmn-motore <comando> [opzioni]`, installato da `installer/installa_motore.sh`
  in `~/.pmn/bin/pmn-motore`.
- Da Windows: `wsl.exe -d <distro> -- ~/.pmn/bin/pmn-motore <comando> ...`.
- Da Linux: direttamente.
- **stdout** = solo eventi JSON, uno per riga (JSON Lines, §4). **stderr** = vuoto o diagnostica breve.
  I dettagli tecnici vanno nel file di log indicato nell'evento `inizio`.

## 2. Comandi

| Comando | Cosa fa | Ingresso | Uscita (evento `fine`, campo `risultato`) |
|---|---|---|---|
| `info` | descrive PC e installazione, senza calcoli lunghi | nessuno | §5.1 |
| `installa` | installa o completa programmi e database; riprende da dove era rimasto | `--catalogo <file o URL>` (predefinito: quello dell'installazione) | elenco dei pezzi installati |
| `verifica` | MD5 dei database + mini-campione di regressione (D032) | nessuno | `{"esito": "verde" \| "rosso", "controlli": [...]}` |
| `stima` | tempo e spazio previsti, prima di partire (D023, D034) | `--progetto <config.yaml>` | §5.2 |
| `esegui` | analisi completa del progetto | `--progetto <config.yaml>` | §5.3 |
| `annulla` | ferma una corsa in modo pulito | `--corsa <id>` | `{"annullata": true}` |

- Un solo `esegui` alla volta (un campione alla volta, D016): un secondo `esegui` risponde con l'errore `GIA_IN_CORSO`.
- `installa` ed `esegui` sono **riprendibili**: rilanciati con gli stessi ingressi, saltano ciò che è già fatto e verificato.

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
| `errore` | `codice`, `messaggio`, `cosa_fare` | "Manca il database di Kraken." / "Apri Impostazioni e premi Installa." |
| `fine` | `esito` (`ok`, `errore`, `annullata`), `risultato` (oggetto) | "Analisi finita in 1 h 12 min" |

- `passo` per `esegui`: `download`, `controllo_qualita`, `pulizia`, `ospite`, `metaphlan`, `kraken`, `riepilogo`.
- `passo` per `installa`: `controllo`, `programmi`, `database`, `verifica`, `fine`
  (già così in `installer/installa_motore.sh --json`).
- L'interfaccia mostra `messaggio` così com'è; per la barra usa `percentuale` ed `eta_s`.
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

## 5. Uscite

### 5.1 `info`

```json
{"motore": "0.1.0", "ram_gb": 15.6, "processori": 24, "spazio_libero_gb": 643,
 "modo_consigliato": {"metaphlan": "fette", "kraken": "completo"},
 "programmi": {"metaphlan": "4.2.4", "bowtie2": "2.5.5", "kraken2": "2.17.2", "bracken": "3.1", "fastp": "1.4.0"},
 "database": [{"nome": "metaphlan_fette_vJan25_v1", "installato": true, "gb": 24.5}]}
```

- `modo_consigliato` viene dalle regole di System One v0 (D031): sotto ~40 GB di RAM, MetaPhlAn a fette.

### 5.2 `stima`

```json
{"campioni": 3, "coppie_totali": 4500000,
 "tempo_s": {"ospite": 900, "metaphlan": 838, "kraken": 7297}, "spazio_gb": 12}
```

- Regole di stima (misurate in S2.2-S2.3): Kraken completo ~37.000 coppie/min con 8 processori;
  MetaPhlAn a fette 86,2 s per milione di coppie + ~150 s fissi per campione.

### 5.3 `esegui`: cartella dei risultati

```
<cartella del progetto>/risultati/
  risultati.json            # indice di tutto (sotto)
  metaphlan/<campione>_profile.txt
  kraken/<campione>.bracken, <campione>.k2report
  tabelle/ (matrici unite), referto/ (quando ci sarà)
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

## 6. Finto motore

- `installer/finto_motore.py` (da scrivere): stessi comandi, stessi eventi, tempi accorciati, risultati presi da
  una corsa vera di SF3RAt7. Serve solo per costruire l'interfaccia; non si installa per gli utenti.

## 7. Cosa NON fa l'interfaccia

- Non legge né modifica i file dei database.
- Non calcola profili, soglie o stime: le chiede al motore.
- Non mostra all'utente testi in inglese del log tecnico: solo `messaggio` e `cosa_fare`.
