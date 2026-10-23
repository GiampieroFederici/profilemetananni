# 🧰 Installatore del motore · Engine installer

> Stato (15/10/2026): provato da zero su una WSL nuova (Ubuntu 24.04) con lo **specchio locale**.
> I pacchetti di profilemetananni (fette, indici dell'ospite, mini-campione) **non sono ancora pubblicati** (D035):
> senza `--specchio` l'installatore si ferma e lo dice.

## Cosa installa

| Pezzo | Dove | Peso |
|---|---|---|
| micromamba 2.9.0 (gestore dei programmi, controllo SHA-256) | `~/.pmn/bin/` | 18 MB |
| 8 ambienti `pmn_*` dal **file di blocco** (`lock/`: stesse versioni e build degli ambienti validati) | `~/.pmn/mamba/envs/` | ~11 GB |
| MetaPhlAn: catalogo `.pkl` di vJan25 + **6 fette** dell'indice (D016, D026) | `~/.pmn/db/metaphlan`, `fette` | 24,9 GB |
| Kraken2: **PlusPF completo** (predefinito, D023) e **PlusPF-8** (screening rapido) | `~/.pmn/db/kraken/` | 118,6 + 8,6 GB |
| Indici dell'ospite: maiale, bovino, pecora, uomo (D021, D042) | `~/.pmn/db/ospite/` | ~15 GB |
| Mini-campione di regressione (200.000 coppie di SF3RAt7) | `~/.pmn/db/prova/` | 30 MB |

- **Spazio:** ~190 GB a installazione finita; fino a ~300 GB **durante**, perché l'archivio di Kraken (91 GB) e i suoi file estratti stanno insieme per qualche minuto. L'installatore controlla lo spazio prima di partire.
- **Tempo:** dipende dalla rete. L'installatore misura la velocità e dice il tempo stimato prima di scaricare (D034).
- **Nessun permesso di amministratore** dentro Linux/WSL.

## Come si usa

```bash
bash installer/installa_motore.sh
```

- Chiede conferma dopo aver detto peso, spazio e tempo stimato. `--si` salta la domanda (la fa l'interfaccia).
- `--stima`: dice peso, spazio e tempo stimato e si ferma senza scaricare (serve all'interfaccia per fare la domanda, D034).
- `--json`: messaggi come eventi JSON per l'interfaccia (`docs/contratto_motore.md`).
- **Se si interrompe** (rete che cade, PC spento): si rilancia lo stesso comando. Riprende i download a metà e salta ciò che è già scaricato e controllato con MD5.
- Alla fine fa da solo la **prova finale** (`verifica_motore.sh`): versioni dei programmi + mini-campione con MD5 identico al riferimento. Esito **VERDE** o **ROSSO**.

## File

| File | Cosa contiene |
|---|---|
| `installa_motore.sh` | l'installatore |
| `verifica_motore.sh` | la prova finale (si può rilanciare quando si vuole) |
| `catalogo.tsv` | ogni file da scaricare: sorgente, byte, MD5, destinazione |
| `md5/kraken_*.md5` | MD5 ufficiali dei file dentro gli archivi Kraken |
| `lock/pmn_*.txt` | file di blocco: pacchetti esatti con URL e MD5 |
| `riferimenti.tsv` | versioni attese e MD5 del mini-campione |
| `windows/installa_pmn.cmd` | doppio clic per installare su Windows (avvia `installa_pmn.ps1` senza finestre nere) |
| `windows/installa_pmn.ps1` | parte Windows: attiva WSL, riavvio e ripresa da sola, controllo dello spazio vero sul disco interno con più spazio, WSL `pmn`, motore con barra di avanzamento (S3-W, 15/10/2026: provato da Windows 11 pulito in una VM Hyper-V, un doppio clic → 1 riavvio → ripresa da sola → VERDE in 17 min; anche con risposta "No" al riavvio e riavvio a mano) |
| `finto_motore.py`, `finto/` | **finto motore** per costruire l'interfaccia (S4-S6): stessi comandi ed eventi del contratto, tempi accorciati, risultati di una corsa vera di SF3RAt7; non si installa per gli utenti |
| `windows/prepara_pmn.sh` | dentro la WSL `pmn`: crea l'utente Linux e copia `installer/`, `motore/`, `bin/`, `steps/` e `refs/` (tutto quello che serve al motore) |

## Fonti dei dati e dei programmi

- Archivi Kraken2/Bracken PlusPF e PlusPF-8 del 26/06/2026: indici pubblici di Ben Langmead (`genome-idx.s3.amazonaws.com/kraken`), MD5 ufficiali.
- Catalogo `.pkl` di MetaPhlAn `mpa_vJan25_CHOCOPhlAnSGB_202503`: identico al file ufficiale (MD5 uguale).
- Le 6 fette sono **un derivato** dell'indice Bowtie2 di vJan25, costruite da noi (`PROVENIENZA.md` nel pacchetto).
- Indici dell'ospite costruiti con Bowtie2 dai genomi NCBI: Sscrofa11.1 (GCF_000003025.6), ARS-UCD1.2 (GCF_002263795.1), ARS-UI_Ramb_v2.0 (GCF_016772045.1), GRCh38.p14 (GCF_000001405.40).
- Programmi da conda-forge e Bioconda; micromamba da `github.com/mamba-org/micromamba-releases`.

## Come citare

Se usi i risultati del motore, cita i programmi e i database usati (elenco completo e DOI nel `README.md`, sezione 21; verificati su PubMed il 15/10/2026):

- **MetaPhlAn 4** (Blanco-Míguez et al. 2023, *Nat Biotechnol* 41(11):1633-1644) con il database `mpa_vJan25_CHOCOPhlAnSGB_202503`. Le 6 fette sono un nostro derivato del suo indice: dichiaralo.
- **Kraken2** (Wood et al. 2019, *Genome Biol*) e **Bracken** (Lu et al. 2017, *PeerJ Comput Sci*), con gli indici PlusPF/PlusPF-8 del 26/06/2026 di Ben Langmead.
- **Bowtie 2** (Langmead & Salzberg 2012, *Nat Methods* 9(4):357-359), **fastp** (Chen et al. 2018; Chen 2023), **SAMtools** (Danecek et al. 2021).
- **Bioconda** (Grüning et al. 2018, *Nat Methods* 15(7):475-476) per l'installazione dei programmi.
- Il genoma dell'ospite usato: maiale (Warr et al. 2020), bovino (Rosen et al. 2020), pecora (Davenport et al. 2022), uomo (Schneider et al. 2017).
- Per la scelta dei parametri di Kraken2: Wright, Comeau & Langille 2023 (*Microb Genom* 9(3):000949).
