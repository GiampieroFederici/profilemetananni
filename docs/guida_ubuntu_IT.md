# ProfileMetaNanni su Ubuntu

Questa guida installa ProfileMetaNanni su un computer con Ubuntu: il motore e l'app con le finestre, nello stesso Linux. Non servono permessi di amministratore, tranne per i programmi di sistema che Ubuntu non ha già (lo script dice quali).

Versione inglese: [guida_ubuntu_EN.md](guida_ubuntu_EN.md).

## 1. Che cosa serve

| | |
|---|---|
| Sistema | Ubuntu 24.04 o 26.04, processore x86_64 (64 bit). La 24.04 è stata provata su un Ubuntu pulito dentro una macchina virtuale, la 26.04 su un PC fisico (desktop LXQt su X11, sistema in italiano) |
| Memoria | 8 GB o più. Lo script si ferma prima di scaricare se memoria e swap insieme sono meno di 4,75 GB |
| Disco | circa 180 GB liberi su un disco interno, nella tua cartella personale. Se hai molto più spazio libero, lo script tiene i pezzi scaricati fino al controllo, e lo dice prima di partire: sul PC fisico di prova, con 416 GB liberi, ha annunciato fino a circa 257 GB occupati durante lo scarico. Poi cancella i pezzi: alla fine restano occupati circa 170 GB |
| Rete | per scaricare circa 130 GB di database. Misurato: 3 h 23 min con una linea da circa 10 MB/s, 5 h 56 min con una linea da circa 6 MB/s |

## 2. Installare: una riga nel Terminale

1. Apri il Terminale, incolla questa riga e premi Invio:

   ```bash
   wget -nv -O- https://github.com/GiampieroFederici/profilemetananni/releases/latest/download/installa_profilemetananni_linux.sh | bash
   ```

   La riga prende un piccolo script dall'ultima Release di ProfileMetaNanni su GitHub. Lo script scarica il pacchetto per Linux (1 MB), controlla che sia quello pubblicato (impronta SHA-256), lo estrae in una cartella temporanea e avvia l'installazione. Non chiede mai la password di amministratore.

   Se il Terminale risponde che `wget` non c'è, usa questa riga: fa lo stesso con `curl`.

   ```bash
   curl -fsSL https://github.com/GiampieroFederici/profilemetananni/releases/latest/download/installa_profilemetananni_linux.sh | bash
   ```

2. Rispondi alla domanda dello script e aspetta la fine (la sezione 3 dice che cosa vedrai).
3. Avvia il programma dal menu delle applicazioni (voce **ProfileMetaNanni**) oppure dal terminale:

   ```bash
   profilemetananni
   ```

   Se il terminale non trova il comando, esci dalla sessione e rientra, oppure usa il percorso intero: `~/.local/bin/profilemetananni`.

### Se preferisci non incollare un comando

1. Scarica il pacchetto per Linux dalla pagina della Release: [profilemetananni_v1.3.0_linux.tar.gz](https://github.com/GiampieroFederici/profilemetananni/releases/download/v1.3.0/profilemetananni_v1.3.0_linux.tar.gz) (1 MB). Puoi anche copiarlo da un altro computer.
2. Estrailo con il gestore dei file (clic destro sul file). La cartella può restare dov'è, con qualsiasi nome.
3. Apri il Terminale nella cartella estratta `profilemetananni` e lancia:

   ```bash
   bash installer/linux/installa_pmn.sh
   ```

In tutti e due i casi il programma viene copiato in `~/.pmn/programma` e gira da lì. Il file scaricato e la cartella estratta dopo l'installazione non servono più: puoi cancellarli.

## 3. Che cosa succede durante l'installazione

- Se manca un programma di sistema (per esempio `curl` su un Ubuntu nuovo), lo script si ferma e mostra una riga `sudo apt install ...`. Lanciala, poi avvia di nuovo l'installazione nello stesso modo.
- Prima di scaricare, lo script dice quanto scarica, quanto spazio serve e quanto tempo ci vorrà. Poi chiede `Procedo con l'installazione? (s/n)`: rispondi `s`. Se sei partito dalla cartella estratta, l'opzione `--si` salta la domanda.
- Lo scarico dura ore. Una sola riga di avanzamento si aggiorna sul posto, e il computer resta libero per altri lavori. Se la rete cade, lo script riprova da solo: sul PC fisico di prova è successo 6 volte in 3 h 23 min, e non c'è stato nulla da fare.
- Puoi interrompere con Ctrl+C. Lo script risponde con una riga sola, `Installazione interrotta`. Per continuare avvia di nuovo l'installazione nello stesso modo: riprende da dove era, senza riscaricare ciò che è già arrivato.
- Alla fine fa una prova su un piccolo campione e scrive `VERDE` se il motore funziona. Poi prepara l'app e scrive il comando e la voce di menu.
- Se mancano librerie di sistema per le finestre, lo script lo dice con un'altra riga `sudo apt install ...`: lanciala prima di avviare il programma.
- L'installazione si può avviare di nuovo quando vuoi: ciò che c'è già non si rifà. Il motore ripete solo la prova finale (alcuni minuti).

## 4. Dove stanno le cose

| Che cosa | Dove |
|---|---|
| Progetti e risultati | cartella Documenti (può chiamarsi `Documenti` o `Documents`), dentro `ProfileMetaNanni/<nome del progetto>/risultati` (il referto è in `risultati/referto`) |
| File di lavoro di un'analisi | `ProfileMetaNanni/<nome del progetto>/pmn_work` |
| Programma | `~/.pmn/programma` |
| Registri del motore e dell'installazione | `~/.pmn/log` |
| Motore, database e ambienti dei programmi | `~/.pmn` |
| Comando e voce di menu | `~/.local/bin/profilemetananni` e `~/.local/share/applications/profilemetananni.desktop` |
| Impostazioni dell'app (lingua, ultima cartella) | `~/.config/ProfileMetaNanni` |
| Impostazioni di sra-tools, il programma che scarica le read dagli archivi pubblici | `~/.ncbi` |

## 5. Aggiornare

Incolla di nuovo la riga della sezione 2: scarica il pacchetto dell'ultima Release e sostituisce il programma. Oppure scarica il pacchetto nuovo per Linux e lancia `bash installer/linux/installa_pmn.sh` dalla sua cartella. I progetti e i database già scaricati restano; la prova finale si ripete.

Su Ubuntu il pulsante **Cerca aggiornamenti** dell'app dice quando esiste una versione nuova; l'aggiornamento si fa come scritto qui.

## 6. Disinstallare

Chiudi il programma, poi cancella:

```bash
rm -rf ~/.pmn
rm -f ~/.local/bin/profilemetananni ~/.local/share/applications/profilemetananni.desktop
rm -rf ~/.config/ProfileMetaNanni
```

La prima riga toglie il programma, il motore, i database e i registri (circa 170 GB). Se non usi sra-tools per altri lavori, cancella anche le sue impostazioni:

```bash
rm -rf ~/.ncbi
```

I tuoi progetti restano in Documenti, nella cartella `ProfileMetaNanni`: cancellala solo se non ti servono più i risultati.

## 7. Se qualcosa non va

- **"L'ambiente ... non corrisponde alle versioni previste."** Non avviare di nuovo l'installazione: si fermerebbe nello stesso punto. Il messaggio indica un file di registro in `~/.pmn/log`: manda a noi quel file aprendo una segnalazione (issue) nella [pagina del progetto](https://github.com/GiampieroFederici/profilemetananni/issues).
- **Il controllo del motore nell'app è rosso.** Il pallino in alto diventa rosso, "Motore da controllare", e la pagina indica un file di registro. Se la pagina dice che il motore risulta installato, manda a noi quel file prima di reinstallare: il pulsante **Apri il registro** lo mostra.
- **Un campione pubblicato da pochi giorni non parte.** L'app dice che il campione esiste negli archivi (ENA e NCBI) ma le sue read non ci sono ancora. Il codice è giusto: riprova fra qualche giorno.
- **Hai fermato un'analisi.** Premi di nuovo **Avvia l'analisi** nello stesso progetto: i passi già finiti non si rifanno.

## 8. Tempi e memoria misurati

Misure del 10/11/2026 con la versione 1.3.0, su Ubuntu 24.04 in una macchina virtuale con 4 processori, 8 GB di memoria e 2 GB di swap, disco SSD. Il campione intero è la corsa pubblica SRR4875279 (3,24 milioni di coppie di read di un salame).

| Che cosa | Tempo | Memoria usata, massimo |
|---|---|---|
| Installazione da zero, in tutto | 6 h 2 min | 5,2 GB |
| di cui scarico dei database (linea da circa 6 MB/s) | 5 h 56 min | 0,8 GB |
| di cui prova finale | 72 s | 5,2 GB |
| Apertura dell'app fino alla prima pagina | circa 3 s | |
| Analisi del campione d'esempio (200.000 coppie) | 3 min 10 s | 4,7 GB |
| La stessa analisi lanciata dall'app | 3 min 20 s | 4,7 GB |
| Analisi del campione intero, dal codice della corsa al referto | 24 min | 5,0 GB |
| Lo stesso campione con 6 GB di memoria, senza swap | 26 min | 4,9 GB |
| Lo stesso campione con 4 GB di memoria e 1 GB di swap | 29 min 30 s | swap usato al 90 % |
| Comunità senza ospite (corsa pubblica ERR2984773, 7,9 milioni di coppie) | 2 h 34 min | 4,9 GB |

Il tempo dell'installazione è quasi tutto scarico e dipende dalla linea. Durante lo scarico il computer resta libero per altri lavori. Con 4 GB di memoria l'analisi finisce e dà gli stessi risultati, ma con poco margine: meglio 8 GB. Il tempo di Kraken cresce con le read che restano dopo aver tolto l'ospite: 7 minuti nel salame intero, 99 minuti nella comunità senza ospite.

Misure del 12/11/2026 con la versione 1.3.0, su un portatile fisico con Ubuntu 26.04 (desktop LXQt su X11, sistema in italiano): processore Intel Core i7-1165G7 (4 core, 8 thread), 15,3 GB di memoria, 0,5 GB di swap, disco NVMe.

| Che cosa | Tempo | Memoria usata, massimo |
|---|---|---|
| Scarico dei database (128 GB, linea da circa 10 MB/s) | 3 h 23 min | |
| Prova finale | da 72 a 94 s | 4,7 GB |
| Preparazione dell'app | circa 1 min | |
| Apertura dell'app fino alla prima pagina | 0,8 s | |
| Analisi del campione d'esempio, lanciata dall'app | 3 min 50 s | 5,6 GB |

Su questo PC i risultati del campione d'esempio sono stati gli stessi della [guida dell'analisi d'esempio](guida_analisi_esempio_IT.md).
