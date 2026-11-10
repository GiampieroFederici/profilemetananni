# ProfileMetaNanni su Ubuntu

Questa guida installa ProfileMetaNanni su un computer con Ubuntu: il motore e l'app con le finestre, nello stesso Linux. Non servono permessi di amministratore, tranne per i programmi di sistema che Ubuntu non ha già (lo script dice quali).

Versione inglese: [guida_ubuntu_EN.md](guida_ubuntu_EN.md).

## 1. Che cosa serve

| | |
|---|---|
| Sistema | Ubuntu 24.04, processore x86_64 (64 bit) |
| Memoria | `[DA COMPLETARE DOPO LA PROVA]` |
| Disco | circa 180 GB liberi su un disco interno, nella tua cartella personale |
| Rete | per scaricare circa 139 GB di database (alcune ore) |

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
