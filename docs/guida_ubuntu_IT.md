# ProfileMetaNanni su Ubuntu

Questa guida installa ProfileMetaNanni su un computer con Ubuntu: il motore e l'app con le finestre, nello stesso Linux. Non servono permessi di amministratore, tranne per i programmi di sistema che Ubuntu non ha già (lo script dice quali).

Versione inglese: [guida_ubuntu_EN.md](guida_ubuntu_EN.md).

## 1. Che cosa serve

| | |
|---|---|
| Sistema | Ubuntu 24.04, processore x86_64 (64 bit) |
| Memoria | 8 GB o più. Lo script si ferma prima di scaricare se memoria e swap insieme sono meno di 4,75 GB |
| Disco | circa 180 GB liberi su un disco interno, nella tua cartella personale |
| Rete | per scaricare circa 130 GB di database (circa 6 ore con una linea da 6 MB/s) |

## 2. I tre comandi

1. Scarica la cartella di ProfileMetaNanni dalla pagina del progetto su GitHub ed estraila, oppure copiala da un altro computer. Mettila in un posto fisso, per esempio `~/profilemetananni`: il programma gira da lì, quindi dopo l'installazione non va spostata né cancellata.
2. Apri il terminale nella cartella e lancia l'installazione:

   ```bash
   cd ~/profilemetananni
   bash installer/linux/installa_pmn.sh
   ```

3. Avvia il programma dal menu delle applicazioni (voce **ProfileMetaNanni**) oppure dal terminale:

   ```bash
   profilemetananni
   ```

   Se il terminale non trova il comando, esci dalla sessione e rientra, oppure usa il percorso intero: `~/.local/bin/profilemetananni`.

## 3. Che cosa succede durante l'installazione

- Se manca un programma di sistema, lo script si ferma e mostra una riga `sudo apt install ...`. Lanciala, poi rilancia lo script.
- Prima di scaricare, lo script dice quanto scarica, quanto spazio serve e quanto tempo ci vorrà. Poi chiede `Procedo con l'installazione? (s/n)`: rispondi `s`. Con l'opzione `--si` non chiede nulla.
- Lo scarico dura ore. Si può interrompere con Ctrl+C: rilanciando lo stesso comando riprende da dove era, senza riscaricare.
- Alla fine fa una prova su un piccolo campione e scrive `VERDE` se il motore funziona. Poi prepara l'app e scrive il comando e la voce di menu.
- Se mancano librerie di sistema per le finestre, lo script lo dice con un'altra riga `sudo apt install ...`: lanciala prima di avviare il programma.
- Lo script si può rilanciare quando vuoi: ciò che c'è già non si rifà. Il motore ripete solo la prova finale (alcuni minuti).

## 4. Dove stanno le cose

| Che cosa | Dove |
|---|---|
| Progetti e risultati | cartella Documenti, dentro `ProfileMetaNanni/<nome del progetto>/risultati` (il referto è in `risultati/referto`) |
| File di lavoro di un'analisi | `ProfileMetaNanni/<nome del progetto>/pmn_work` |
| Registri del motore e dell'installazione | `~/.pmn/log` |
| Motore, database e ambienti dei programmi | `~/.pmn` |
| Comando e voce di menu | `~/.local/bin/profilemetananni` e `~/.local/share/applications/profilemetananni.desktop` |
| Impostazioni dell'app (lingua, ultima cartella) | `~/.config/ProfileMetaNanni` |

## 5. Aggiornare

Scarica la cartella della versione nuova e, da quella cartella, lancia di nuovo `bash installer/linux/installa_pmn.sh`. I progetti e i database già scaricati restano.

## 6. Disinstallare

Chiudi il programma, poi cancella:

```bash
rm -rf ~/.pmn
rm -f ~/.local/bin/profilemetananni ~/.local/share/applications/profilemetananni.desktop
rm -rf ~/.config/ProfileMetaNanni
```

Poi cancella la cartella del programma (per esempio `~/profilemetananni`). I tuoi progetti restano in Documenti, nella cartella `ProfileMetaNanni`: cancellala solo se non ti servono più i risultati.

## 7. Tempi e memoria misurati

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
