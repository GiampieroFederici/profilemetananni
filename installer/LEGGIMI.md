# 🧰 Installatore del motore · Engine installer

## Per chi installa (Windows 10 e 11)

1. Estrai lo zip (tasto destro, **Estrai tutto**) e fai doppio clic su **Installa profilemetananni**.
2. Windows chiede il permesso di attivare **WSL** (un suo componente): rispondi **Sì**. Se chiede di riavviare, riavvia:
   dopo il riavvio l'installazione riprende da sola (al massimo 2 minuti dopo l'accesso). Se dopo 5 minuti non vedi
   la finestra, fai di nuovo doppio clic su **Installa profilemetananni**: riprende da dove era.
3. Prima di scaricare, l'installatore dice **quanto scarica, quanto spazio serve, quanto ce n'è** e **quanto tempo
   ci vorrà**, separato per Kraken e per gli altri database. Rispondi **Sì** per partire, **No** per non scaricare nulla
   (sul computer non resta niente: il programma e le icone si copiano solo dopo il Sì).
4. Se lo scarico dura più di mezz'ora e il computer è un portatile, chiede se impostare la chiusura del coperchio su
   **Non fare nulla** finché l'installazione finisce: con **Sì** lo fa lui e alla fine rimette l'impostazione di prima;
   con **No** tieni il coperchio aperto. Se il computer va a batteria, ti consiglia di collegare l'alimentatore.
5. Durante lo scarico la finestra mostra quanti GB sono arrivati e a che velocità. Il pulsante **Interrompi** ferma
   l'installazione (chiede conferma): quello che è già scaricato resta, e quando riapri l'installazione **riprende da
   lì**. Dopo Interrompi l'installazione **non** riparte da sola.
6. Alla fine: **Tutto pronto**, e si apre il programma ProfileMetaNanni (lo trovi anche sul desktop e nel menu Start).

**Spazio.** Servono circa **176 GB** liberi sul disco (installazione completa, da zero): a installazione finita ne
restano occupati circa 168. Prima della versione 1.1 servivano 257 GB, perché l'archivio di Kraken (85 GB) restava sul
disco insieme ai file estratti: ora si estrae mentre arriva. Se invece lo spazio c'è, durante lo scarico di Kraken
l'installatore tiene i pezzi già estratti fino al controllo finale, così se si ferma non riscarica nulla: per qualche
ora Kraken occupa circa il doppio (fino a 85 GB in più), poi i pezzi si cancellano da soli. Se lo spazio è poco l'installatore lo dice prima di
scaricare e dice quanti GB liberare. Durante lo scarico controlla lo spazio ogni minuto: se il disco sta per riempirsi
(meno di 5 GB liberi) si ferma e dice di liberare spazio; poi riapri l'installazione e riprende.

**Tempo.** Dipende dalla rete. Gli indici di Kraken (85 GB) arrivano da un server che dà poca velocità a ogni
connessione: l'installatore li scarica a pezzi con 16 connessioni insieme, mentre gli altri database (42 GB, da GitHub)
arrivano in parallelo. Su una rete domestica conta da qualche ora a una notte; la stima che vedi prima di partire è
misurata sulla tua rete.

**Se qualcosa si ferma.** Ogni messaggio dice che cosa è successo e che cosa fare (per esempio: controlla la
connessione, libera spazio). Riapri l'installazione con lo stesso doppio clic: riprende da dove era, senza riscaricare
quello che è già arrivato e controllato. Se un file arriva rovinato, l'installatore lo riscarica da solo una volta; se
succede ancora, il messaggio indica il file da mandarci. Se il computer si spegne durante lo scarico, al prossimo
accesso l'installazione riparte da sola.

**Memoria.** Serve un PC con almeno **16 GB** di memoria (l'analisi con MetaPhlAn usa fino a 8 GB dentro Linux).
Con meno l'installatore si ferma subito, prima di installare o scaricare qualsiasi cosa, e lo dice.

**Se l'installatore ti chiede di mandarci un file**, il percorso che vedi si apre da Windows (una copia del registro
tecnico in `%LOCALAPPDATA%\profilemetananni\`, accanto a `installazione_windows.log`).

**Nessun permesso di amministratore** dopo quello per attivare WSL.

---

## Per chi sviluppa

> Stato (30/10/2026, v1.1): scarico a pezzi provato con lo specchio locale "difficile" (`tests/specchio_server.py`,
> `tests/test_scarico_pezzi.py`); la prova da zero sulla VM Windows 11 è quella di v1.1 (`VERIFICHE_v1.1.md`).
> I pacchetti di profilemetananni (fette, `.pkl`, indici dell'ospite, mini-campione: 71 file, 41,8 GB) si scaricano dalla
> Release `database-v1` di GitHub, con i nomi piatti: `/` diventa `__` (`fette_vJan25_v1/idx3/fetta3.1.bt2` si chiama
> `fette_vJan25_v1__idx3__fetta3.1.bt2`). `--specchio` o la variabile `PMN_URL_PACCHETTI` cambiano l'indirizzo.

### Cosa installa

| Pezzo | Dove | Peso |
|---|---|---|
| micromamba 2.9.0 (gestore dei programmi, controllo SHA-256) | `~/.pmn/bin/` | 18 MB |
| 8 ambienti `pmn_*` dal **file di blocco** (`lock/`: stesse versioni e build degli ambienti validati) | `~/.pmn/mamba/envs/` | ~11 GB |
| MetaPhlAn: catalogo `.pkl` di vJan25 + **6 fette** dell'indice (D016, D026) | `~/.pmn/db/metaphlan`, `fette` | 24,9 GB |
| Kraken2: **PlusPF completo** (predefinito, D023) e **PlusPF-8** (screening rapido) | `~/.pmn/db/kraken/` | 118,6 + 8,6 GB |
| Indici dell'ospite: maiale, bovino, pecora, uomo (D021, D042) | `~/.pmn/db/ospite/` | ~15 GB |
| Mini-campione di regressione (200.000 coppie di SF3RAt7) | `~/.pmn/db/prova/` | 30 MB |

### Come si usa da riga di comando (Linux o WSL)

```bash
bash installer/installa_motore.sh
```

- Chiede conferma dopo aver detto peso, spazio e tempo stimato. `--si` salta la domanda (la fa l'interfaccia).
- `--stima`: dice peso, spazio e tempo stimato per sorgente e si ferma senza scaricare (D034). Nel risultato
  `spazio_necessario_byte` è **l'unica regola dello spazio**: la legge anche `windows/installa_pmn.ps1`.
- `--json`: messaggi come eventi JSON per l'interfaccia (`docs/contratto_motore.md`; v1.1: campi nuovi facoltativi
  `byte_fatti`, `byte_totali`, `velocita_mb_s`, `sorgente`, `sorgenti`, un avanzamento ogni 15 s durante lo scarico).
- `--connessioni N` (o `PMN_CONNESSIONI`): connessioni insieme per i file a pezzi, predefinita 16 (D165).
- `--spazio-libero B`: byte liberi veri (li passa la parte Windows; dentro WSL `df` vede il disco virtuale da 1 TB).
- `--solo-database`: solo i database, senza programmi e prova finale (prove con lo specchio locale).
- **Se si interrompe** (rete che cade, PC spento): si rilancia lo stesso comando. Riprende i pezzi a metà e salta ciò che
  è già scaricato e controllato con MD5.
- Alla fine fa da solo la **prova finale** (`verifica_motore.sh`): versioni dei programmi + mini-campione con MD5 identico
  al riferimento. Esito **VERDE** o **ROSSO**.

### Come scarica (v1.1, D165, D166)

- **A pezzi**: i file della sorgente `kraken` (S3: velocità limitata per connessione, 0,17 MB/s con una connessione e
  1,42 MB/s con otto, prova del 29/10) si dividono in pezzi (almeno 8 per connessione, al massimo 128 MiB) chiesti con
  richieste HTTP Range, `N` connessioni insieme, un file `<nome>.pezzo.<i>` per pezzo e l'elenco dei pezzi in
  `<nome>.pezzi` (resta per la ripresa). Ogni pezzo riprende dal byte dove era arrivato; nuovi tentativi con attesa
  crescente (5, 10, 20, 40, 60 s, fino a 30 tentativi). Il `<file>.parziale` di una 1.0 interrotta diventa il primo pezzo.
  Se il server non risponde `206` a una richiesta Range si torna a un solo curl come in 1.0.
- **Sorgenti insieme**: una coda per sorgente, tutte in parallelo; `kraken` un file alla volta a `N` connessioni,
  `pmn` (Release GitHub) 4 file alla volta, una connessione ciascuno. Nel catalogo l'ordine resta quello del file.
- **Seconda sorgente** (D166): colonna facoltativa `url_alternativo` (nona colonna di `catalogo.tsv`, URL completo della
  stessa copia): i pezzi (e i nuovi tentativi) si dividono fra le due sorgenti. Oggi nessuna riga la usa.
- **Estrazione dal flusso**: gli archivi si leggono pezzo per pezzo, in ordine, anche mentre gli ultimi arrivano;
  `tee` passa i byte a `md5sum` e a `tar -xz` nello stesso passaggio (niente rilettura di 85 GB). Se lo spazio basta
  per archivio intero + estratto, i pezzi restano fino all'MD5 giusto (una interruzione durante l'estrazione non
  riscarica nulla); se no, ogni pezzo si cancella appena letto (picco = estratto + al massimo `2N` pezzi; lo dice il
  log) e un'interruzione fa ripartire quell'archivio da capo. MD5 sbagliato: via l'estratto e i pezzi, si riscarica una
  volta da solo; alla seconda si ferma con `DB_ROVINATO`.
- **Spazio** (`--stima`, `spazio_necessario_byte`): byte finali di ciò che manca + i pezzi in volo dell'archivio più
  grande (`2N` × pezzo, ~4,3 GB con 16 connessioni) + 16 GB di programmi se un ambiente manca. Catalogo intero da zero:
  176 GB (prima 257).
- **Stima e avanzamento** (B1): prima di partire ogni sorgente si misura da sola (6 s) e poi tutte insieme (10 s), come
  si scaricherà davvero (16 pezzi di Kraken, i primi 4 file pmn). Il tempo viene da una simulazione: le sorgenti vanno
  alla velocità misurata insieme; quando una finisce, la sua banda passa alle altre, ma nessuna supera la sua velocità
  da sola. Così la stima va bene sia se il limite è la linea del PC (VM del 30/10: GitHub da 1,1 a 7 MB/s finito
  Kraken) sia se è ogni connessione (PC del 29/10: S3 0,17 MB/s per connessione). Durante lo scarico lo stesso calcolo,
  con la velocità media degli ultimi ~60 s per sorgente, ricalcola `eta_s` ogni 15 s.
- **Niente processi orfani**: all'uscita (fine, errore, annulla, segnale) si fermano code, curl e tar. Se nessuno legge
  più gli eventi (finestra di Windows chiusa a forza) il motore se ne accorge al primo evento (entro 15 s) e si ferma.

### Parte Windows (`windows/installa_pmn.ps1`)

- Fase 1: attiva WSL (permesso di Windows), riavvio e ripresa da sola: voce RunOnce e, come seconda via (A0, VM del
  30/10: RunOnce ha lanciato conhost all'accesso ma PowerShell non è partito), un'attività pianificata "all'accesso"
  di questo utente con 2 minuti di ritardo (`profilemetananni - continua installazione`, senza amministratore), tolta
  a fine installazione, dopo un No o dopo Interrompi. Se partono tutte e due, la seconda copia trova l'installazione
  aperta (lucchetto `Local\profilemetananni_installa`) ed esce.
- Fase 2: WSL `pmn` sul disco interno con più spazio (D045), `prepara_pmn.sh`, poi `installa_motore.sh --stima`: lo
  spazio che serve viene dal motore e si confronta con lo spazio vero di Windows. Dopo il Sì copia l'app e le icone
  (v1.1: non prima, così un tentativo fermato non lascia resti), chiede del coperchio (`powercfg`, impostazione
  `LIDACTION`, solo con l'alimentatore; il valore di prima resta in `%LOCALAPPDATA%\profilemetananni\coperchio.txt`
  finché non è rimesso: a fine installazione, dopo un errore, dopo Interrompi o alla ripresa successiva), poi lancia il
  motore con `--spazio-libero`.
- Interrompi: `pmn-motore annulla --corsa` (P41), e se dopo 30 s il motore non si è fermato `wsl --terminate pmn` (come
  un PC spento: la ripresa funziona lo stesso); niente RunOnce dopo un arresto voluto.
- Ogni minuto controlla lo spazio libero di Windows (sotto 5 GB ferma con un messaggio); ogni 5 minuti scrive nel log
  `installazione_windows.log` una riga `RIASSUNTO:` con GB fatti, velocità e tempo che manca.
- Prova con lo specchio locale (D038, D044) o con un altro catalogo (D170): file `prova.conf` accanto allo script,
  righe `specchio=URL` e `catalogo=installer/<file>.tsv` (la sola riga `catalogo=` usa le sorgenti vere).

### File

| File | Cosa contiene |
|---|---|
| `installa_motore.sh` | l'installatore |
| `verifica_motore.sh` | la prova finale (si può rilanciare quando si vuole) |
| `catalogo.tsv` | ogni file da scaricare: sorgente, byte, MD5, destinazione (facoltativa: `url_alternativo`) |
| `md5/kraken_*.md5` | MD5 ufficiali dei file dentro gli archivi Kraken |
| `lock/pmn_*.txt` | file di blocco: pacchetti esatti con URL e MD5 |
| `riferimenti.tsv` | versioni attese e MD5 del mini-campione |
| `windows/installa_pmn.cmd` | doppio clic per installare su Windows (avvia `installa_pmn.ps1` senza finestre nere) |
| `windows/installa_pmn.ps1` | parte Windows (sopra) |
| `finto_motore.py`, `finto/` | **finto motore** per costruire l'interfaccia (S4-S6): stessi comandi ed eventi del contratto, tempi accorciati, risultati di una corsa vera di SF3RAt7; non si installa per gli utenti |
| `windows/prepara_pmn.sh` | dentro la WSL `pmn`: crea l'utente Linux e copia `installer/`, `motore/`, `bin/`, `steps/` e `refs/` (tutto quello che serve al motore) |

### Prove

- Motore (WSL): `tests/test_scarico_pezzi.py` (specchio locale con velocità per connessione, cadute, server senza
  Range, MD5 sbagliato, due sorgenti, picco su disco, nessun processo orfano), `tests/test_installa_eventi.py`.
- Windows: `tests/test_installa_ps1.py` (sintassi, coperchio, spazio, riga riassuntiva, `prova.conf`), con il Python
  dell'app.

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
