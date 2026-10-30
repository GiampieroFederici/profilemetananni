# Interfaccia dell'app: schermate e regole (S4, 16/10/2026)

> Documento di progetto per S5-S6 (app in PySide6). Prototipo navigabile: `docs/prototipo_interfaccia/`
> (`index.html` + `dati.js`). Tutti i numeri del prototipo sono veri: eventi registrati dal finto motore,
> risultati della corsa di SF3RAt7, sicurezza alimentare calcolata con `motore/fssp` (`costruisci_dati.py`).
> Regola che vale ovunque (D006): **l'interfaccia mostra, chiede e lancia. Non fa scienza.**

---

## 1. Che cosa abbiamo imparato da GSEA (studiato dal vivo il 16/10)

GSEA 4.4.0 (Broad Institute) è il riferimento per "un programma per biologi che guida dal file al risultato".
Provato con un file di prova sintetico (120 geni, 6 campioni), dal caricamento fino al referto.

| In GSEA | Funziona o confonde? | Regola per noi |
|---|---|---|
| Colonna a sinistra con i passi ("Load data", "Run GSEA", ...) sempre visibile | ✅ si sa sempre dove si è | Percorso a 4 passi sempre visibile a sinistra (R3) |
| Campi divisi in "Required", "Basic", "Advanced" (gli ultimi due chiusi) | ✅ chi non sa non vede nulla di pericoloso | Scelte consigliate già pronte; "Parametri per esperti" chiuso (R6) |
| Menu a tendina con spiegazione fra parentesi ("No_Collapse (use dataset 'as is')") | ✅ | Ogni scelta con una frase che dice cosa fa (R5) |
| Pulsante "Command": mostra il comando equivalente | ✅ riproducibilità | "Mostra il file del progetto" dentro i parametri per esperti |
| Referto: prima le frasi ("2/3 gene sets are upregulated in A"), poi i dettagli; citazioni in fondo | ✅ | Risultati: prima una frase di sintesi, poi schede; citazioni sempre in fondo (D036) |
| Finestra "Apri file" che parte dalla cartella del programma (`C:\Program Files\GSEA_4.4.0`) | ❌ l'utente si perde | Le finestre di scelta partono da Documenti o dall'ultima cartella usata (R10) |
| "Nome file non valido" senza dire perché | ❌ | Ogni errore dice cosa è successo e cosa fare (R8, contratto `cosa_fare`) |
| "There were warnings. See the [+] console log" e avvisi importanti solo nella barra di stato in basso | ❌ si perdono | Gli avvisi stanno nel corpo della pagina, vicino a ciò che riguardano (R9) |
| Barra di stato con tag HTML grezzi (`<br>`, `<b>`) | ❌ sembra rotto | Mai testo tecnico grezzo all'utente (R2) |
| Avviso nel referto troncato ("the number of samples in class A is") | ❌ | Si mostra solo `messaggio` del motore, completo |
| Aiuti in inglese con termini tecnici (e refusi: "seperation") | ❌ | Tutto in italiano semplice; termine tecnico tra parentesi (R2) |
| "<No Available Component>" nello storico | ❌ gergo da programmatore | Pagine vuote = invito ad agire ("Nessun progetto: premi Nuovo progetto") |
| Ogni clic apre una nuova scheda in alto, che si accumulano | ❌ | Una pagina alla volta, niente schede che si accumulano |
| Il referto si apre nel browser, fuori dal programma | ➖ comodo ma spaesante | Il referto si apre dentro l'app; PDF ed Excel con un pulsante |

Fotografie e referto di GSEA (privati): `implementazione/studio/S4_gsea/`.

---

## 2. Stile (scelta: chiaro e sobrio, con l'avatar)

| Elemento | Scelta | Perché |
|---|---|---|
| Fondo | `#EEF2F0` (bancone del laboratorio), pannelli bianchi `#FFFFFF`, bordi `#CBD5D1` | chiaro, riposante, non "carta antica" |
| Testo | `#1C2B27` (verde ardesia), secondario `#52625D` | contrasto alto |
| Azione principale | verde agar `#1E7A4C` (scuro `#155C39`) | richiama il verde dell'avatar, ma leggibile sul bianco |
| Avvisi / errori / informazioni | ambra `#9A5A00`, rosso `#A8251C`, acciaio `#2F5D7C`, ognuno con fondo chiaro | si distinguono anche per la forma (barra laterale) |
| Carattere | **Atkinson Hyperlegible** (licenza OFL, da includere nell'app), 18 px di base | progettato per la massima leggibilità: aiuta chi vede poco e chi è DSA |
| Avatar (D046) | piastra scura con i "baffi" microbici verde neon: **all'avvio saltella e si ferma**; in alto a sinistra sempre presente; **durante l'analisi "respira"** (si illumina piano) e si ferma alla fine | è l'unico elemento animato: si nota senza disturbare |
| Movimento | solo avatar; niente animazioni sugli altri elementi; rispettare "riduci movimento" di Windows | |
| Contrasto | verificato con la formula WCAG: tutte le coppie testo/fondo fra 5,3:1 (bianco sul verde del pulsante) e 13,4:1 | soglia AA = 4,5:1 |

File: `docs/prototipo_interfaccia/avatar_512.png` (avvio), `avatar_baffi.png` (testata). Originale: `ProfileMetaNanni-Avatar.png`.

---

## 3. Le schermate

Fotografie (1366 x 860): `docs/prototipo_interfaccia/schermate/`.
Struttura fissa di ogni pagina: **testata** (avatar, nome del progetto, menu "I miei progetti / Motore / Come citare"),
**percorso** a sinistra, **contenuto** al centro, **barra delle azioni** in basso con **un solo pulsante principale**, sempre a destra.

| # | Schermata | Scopo | Pulsante principale | Foto |
|---|---|---|---|---|
| 0 | Avvio | avatar che saltella; intanto `info` | (nessuno, 2-3 s) | `00_avvio.png` |
| H | I miei progetti | ritrovare e aprire | Nuovo progetto | `01_home.png` |
| 1 | Campioni e prodotto | da dove vengono le read; che prodotto è | Avanti: scelte dell'analisi | `02_progetto.png` |
| 2 | Scelte dell'analisi | consigliate già pronte; stima prima di partire | Avvia l'analisi | `03_scelte.png`, `04_scelte_tempo_lungo.png` |
| 3 | Analisi in corso | barra, tempo che manca, passi | Ferma l'analisi (con conferma) | `05_esecuzione.png`, `06_esecuzione_finita.png`, `07_errore_db_mancante.png` |
| 4 | Risultati | sintesi, MetaPhlAn e Kraken **separati**, referto, citazioni | Prevedi la sicurezza alimentare | `08_risultati.png`, `08b_risultati_lunga.png` |
| + | Sicurezza alimentare | scenari di *Listeria* con FSSP | Aggiungi al referto | `09_sicurezza.png`, `09c_salame_fuori_campo.png`, `09d_salsiccia_con_lab.png` |
| M | Motore | stato, database, controlla, installa | Controlla il motore | `10_motore.png` |
| C | Come citare | tutte le fonti (D036) | Torna ai progetti | |

### 3.1 Campioni e prodotto
- Due scelte grandi: "Sul mio computer" (cartella con i `.fastq.gz`, coppie R1/R2 trovate da sole) oppure "In un archivio pubblico" (codici SRR, uno per riga, con conteggio dei codici validi).
- **Prodotto → ospite** (System One v0, regola): salume di maiale → maiale + uomo; bovino → bovino + uomo; pecora → pecora + uomo; altro → solo uomo, con avviso. La frase dice **perché** si toglie il DNA dell'ospite.
- Gli indici disponibili sono i 4 di D021; il pollo (in `refs/hosts.tsv`) non è nel motore installato: non si propone.

### 3.2 Scelte dell'analisi
- Prima frase: "Ho già preparato le scelte consigliate per questo computer (15,6 GB, 8 processori). Puoi partire subito." (da `info.modo_consigliato`).
- "Quanto a fondo cercare le specie rare?": database completo (consigliato, D023) o screening rapido, con il tempo stimato per **questo** progetto e il limite dichiarato (D023).
- "Che cosa cerco?": batteri, archei e lieviti sempre; **virus** come opzione con riquadro ambra "Sperimentale, non validata" (D017, D033).
- "Parametri per esperti" (chiuso): confidenza Kraken, abbondanza minima, Bracken `-t` e `-r`, ognuno con il consigliato preselezionato e la **fonte accanto** (D022); "Mostra il file del progetto".
- "Prima di partire": risultato di `stima` (campioni, coppie, tempo per passo, spazio). Il riassunto sta **anche nella barra delle azioni**, accanto ad "Avvia" (lezione GSEA: gli avvisi lontani non si leggono). Con `TEMPO_LUNGO` il riassunto diventa ambra e c'è il pulsante "Passa allo screening rapido".

### 3.3 Analisi in corso
- Il messaggio del motore così com'è; barra da `percentuale`; "tempo che manca" da `eta_s`; elenco dei 7 passi del contratto con ✓, ●, ○.
- "Puoi usare il computer per altro. Se lo spegni, alla riaccensione l'analisi riparte dai passi non finiti." (`esegui` è riprendibile).
- "Ferma l'analisi" chiede conferma: "I passi già finiti restano salvati. Quello a metà si rifà quando riparti." Dopo: "Riprendi l'analisi".
- Errore: titolo "L'analisi si è fermata", riquadro rosso con `messaggio` + `cosa_fare`, e il pulsante principale porta dove si risolve (DB_MANCANTE → Motore; READ_NON_TROVATE → Campioni; GIA_IN_CORSO → Progetti).
- "Dettagli tecnici" (chiuso) mostra solo il percorso del registro da mandarci.

### 3.4 Risultati
- Una frase di sintesi in cima (**da preparare nel motore**, vedi §6), poi i pulsanti del referto (HTML nell'app, PDF, Excel, cartella).
- Schede: "Specie trovate con MetaPhlAn", "Specie trovate con Kraken", "Come è stata fatta l'analisi". **Mai una tabella che fonde i due metodi**; la scheda Kraken lo dice ("metodo diverso: i numeri non si confrontano uno a uno").
- MetaPhlAn: dichiara la parte **non assegnata** (53,7 % in SF3RAt7) e perché è normale.
- Kraken: i residui non microbici (*Homo sapiens*, *Leishmania mexicana*) fuori dal profilo, in un riquadro a parte (D023).
- In fondo, sempre: "Strumenti e database usati" con le citazioni della corsa (D036).

### 3.5 Pannello "Sicurezza alimentare" (FSSP, D019, D048-D050)
- Domanda in chiaro: "Che cosa succederebbe alla *Listeria monocytogenes*, se ci fosse, durante la conservazione?"
- Riquadro fisso: "Il profilo dice chi c'è, non quanti sono per grammo" → scenari 1 e 100 ufc/g; conta dei lattici in piastra facoltativa.
- Ingressi del prodotto: temperatura, giorni, sale nella parte acquosa **oppure** aw, pH, nitrito, conta dei batteri lattici; "Altri ingredienti e opzioni" (acidi, CO₂, fenoli, lag, modalità "come FSSP" o "migliorata").
- Uscita, così come arriva dal motore:
  - **avvisi "fuori campo" in alto**, in ambra, prima dei numeri;
  - una scheda per scenario, con una frase: "Dopo 21 giorni arriverebbe a 10^2,5 ufc/g (circa 300 ufc/g). Si moltiplica per 100 in circa 17 giorni." Numeri arrotondati a 2 cifre (niente "30.023 ufc/g");
  - colore della scheda: ambra se cresce, verde se non cresce, **grigio tratteggiato se non cresce ma fuori campo** ("non è una garanzia"): mai un verde rassicurante su un'estrapolazione;
  - grafico log ufc/g nel tempo (scala spiegata in una riga);
  - "Che cosa ho usato del profilo": *Listeria* trovata o no ("non trovata non vuol dire assente"), lattici del modello trovati, lattici per cui il modello non è adatto (*Leuconostoc*, *Weissella*), specie senza modello;
  - citazione dei modelli FSSP sotto.
- Casi veri nel prototipo: salsiccia 5 °C 21 giorni (senza e con 10^6 ufc/g di lattici: da 10^4,5 a 10^2,6 per lo scenario 100 ufc/g); salame aw 0,90 pH 5,2 (fuori campo per sale e pH, "non cresce" ma grigio).

### 3.6 Motore
- Stato (pallino verde/rosso anche nella testata), database installati con peso, PC (RAM, processori, spazio), versioni.
- "Controlla il motore" (`verifica`, VERDE/ROSSO con i controlli), "Installa o completa" (`installa`, con barra).

---

## 4. Regole "a prova di boomer" (D027), verificabili

| # | Regola | Come si controlla in S5-S6 |
|---|---|---|
| R1 | **Un solo pulsante principale** per pagina, sempre in basso a destra, con un verbo che dice cosa succede ("Avvia l'analisi", non "OK") | revisione di ogni pagina; test che conta i pulsanti principali |
| R2 | Tutto in italiano semplice. Un termine tecnico solo con la spiegazione accanto o tra parentesi. Mai testo tecnico grezzo (inglese del log, HTML, percorsi) fuori da "Dettagli tecnici" | lettura di ogni testo; ricerca di parole inglesi nelle stringhe dell'interfaccia |
| R3 | Il percorso (4 passi) è sempre visibile e dice dove si è | foto di ogni pagina |
| R4 | Le scelte consigliate sono **già selezionate**: si può arrivare ai risultati premendo solo il pulsante principale | prova: da Nuovo progetto ai risultati solo con "Avanti" (codici SRR a parte) |
| R5 | Ogni opzione ha una frase che dice cosa fa e quando conviene | revisione |
| R6 | I parametri tecnici stanno in "Parametri per esperti", chiusi, ognuno con valore consigliato e **fonte** (D022) | revisione |
| R7 | Ogni attesa lunga ha barra, percentuale e tempo che manca; si può fermare | prova con il finto motore (`--velocita`) |
| R8 | Ogni errore dice **cosa è successo** e **cosa fare**, e il pulsante principale porta dove si risolve | prova di tutti gli scenari del finto motore |
| R9 | Gli avvisi stanno vicino a ciò che riguardano e prima dei numeri (mai solo in una barra di stato) | revisione |
| R10 | Le finestre di scelta file partono da Documenti o dall'ultima cartella usata | prova |
| R11 | L'interfaccia non calcola: testi, numeri e soglie arrivano dal motore (contratto); l'interfaccia formatta solo (virgola decimale, arrotondamento a 2 cifre) | revisione del codice: niente formule scientifiche nella GUI |
| R12 | MetaPhlAn e Kraken mai fusi in una tabella o in un numero | revisione |
| R13 | Opzioni non validate (virus) sempre con il riquadro ambra "sperimentale" (D017, D033) | revisione |
| R14 | Fonti in fondo a ogni referto e nella pagina "Come citare" (D036) | revisione |
| R15 | Caratteri grandi (18 px di base), contrasto alto, comandi da tastiera, "riduci movimento" rispettato | controllo contrasto; prova con Tab |

---

## 5. Collegamento al motore: schermata → comando → eventi

Ogni pulsante corrisponde a un comando di `pmn-motore` (contratto `docs/contratto_motore.md`); da Windows:
`wsl.exe -d pmn -u pmn -e /home/pmn/.pmn/bin/pmn-motore <comando>` (come `app/motore.py`). La GUI legge **solo** stdout (JSON Lines).

| Schermata / azione | Comando | Eventi usati | Che cosa mostra | Provato col finto motore |
|---|---|---|---|---|
| Avvio, testata, Motore | `info` | `fine.risultato` | RAM, processori, spazio, `modo_consigliato`, database | ✅ |
| Motore: Controlla | `verifica` | `avanzamento`, `fine.risultato.controlli`, `errore` | VERDE/ROSSO e i controlli | ✅ (ok, DB_MANCANTE) |
| Motore: Installa | `installa` | `avanzamento` (passi del contratto), `avviso`, `fine` | barra e messaggi | ✅ |
| Scelte: Prima di partire | `stima --progetto` | `avviso TEMPO_LUNGO`, `fine.risultato` | tempo per passo, spazio | ✅ (ok, TEMPO_LUNGO) |
| Scelte: Avvia | (la GUI scrive `config.yaml`) poi `esegui --progetto` | `inizio.corsa`, `inizio.log`, `avanzamento`, `avviso`, `errore`, `fine` | barra, passi, errori | ✅ (ok, DB_MANCANTE, READ_NON_TROVATE, annullata, GIA_IN_CORSO) |
| Esecuzione: Ferma | `annulla --corsa <id di inizio>` | `fine.esito = annullata` | "Analisi fermata", "Riprendi" | ✅ |
| Risultati | (nessun comando) legge `risultati/risultati.json` e `risultati/referto/` | | sintesi, schede, citazioni | ✅ (dati di SF3RAt7) |
| Sicurezza: Calcola | `sicurezza` (filone motore, contratto v0.2) | `avviso FUORI_CAMPO`, `fine.risultato` | avvisi, schede, grafico, ponte | ✅ su `steps/45` (3 casi veri) |

Lettura degli eventi in PySide6: `QProcess` con `readyReadStandardOutput`, una riga = un evento; codice di uscita come nel contratto (0, 1, 2, 3, 4).

---

## 6. Che cosa serve dal motore (mandato al filone "Motore, seconda parte")

> **Stato al 16/10, dopo l'unione (`31e954e`):** fatti 1, 2, 3, 5, 6, 7, 8 e il campo `modello` del punto 4; il prototipo li usa
> (passo dell'errore segnato con ✗, frasi di sintesi dal motore, Kraken "fra i soli microbi" letto con `motore/referto.py`,
> avvisi FSSP presi dagli eventi del comando `sicurezza`). **Ancora aperti:** i numeri negli avvisi FSSP sono all'inglese
> ("13.9875", "0.7-9": testo di `motore/fssp/validita.py`); nel finto motore `stima` conta Kraken completo (51 min) mentre
> `esegui` usa i dati dello screening rapido (17 min).

1. `errore` con il campo `passo` (oggi non si sa in quale passo si è fermato).
2. `cosa_fare`: "Apri la pagina Motore e premi Installa o completa." (nell'app non esiste una pagina "Impostazioni").
3. `esegui` vero: `eta_s` oggi sempre null; calcolarlo con le regole di `stima`.
4. FSSP: avvisi fuori campo con il campo `modello` (oggi escono doppi, Listeria e lattici, con campi diversi) e numeri all'italiana (oggi "13.9875").
5. Finto motore: messaggi "database completo" ma dati PlusPF-8 (rapido): allineare.
6. Residui non microbici di Kraken separati dal motore (D023), non dalla GUI.
7. Frase di sintesi per campione e parte non assegnata di MetaPhlAn pronte nel `risultati.json`/referto (la GUI mostra, non calcola).
8. Lettere accentate vere nei testi per l'utente (oggi "com'e'", "qualita'", "C'e' gia'").

---

## 7. Scheletro comune e piano S5-S6 in parallelo (D056)

Perché S5 e S6 girino insieme serve prima uno scheletro comune, piccolo, fatto da una sessione sola (**S5a**, ~mezza sessione):

```
app/
  main.py                 # avvio: finestra, avatar che saltella, info
  finestra.py             # testata + percorso + area centrale (QStackedWidget) + barra delle azioni
  motore.py               # MotoreClient: QProcess, una riga JSON = un segnale evento(dict); annulla
  progetto.py             # scrive e legge config.yaml del progetto (yaml.safe_dump)
  stile.qss               # i colori e le misure del §2
  risorse/                # avatar_512.png, avatar_baffi.png, AtkinsonHyperlegible-*.ttf (OFL)
  pagine/
    base.py               # Pagina: titolo, pulsante principale, testo d'aiuto (interfaccia comune)
    home.py  progetto.py  scelte.py            # S5b
    esecuzione.py  risultati.py  sicurezza.py  # S6
    motore.py  crediti.py                      # S5b
tests/test_app_*.py       # pytest-qt contro il finto motore (--velocita 0, --scenario)
```

- **S5a (prima, da sola):** scheletro, stile, `MotoreClient` provato col finto motore, `Pagina` base, navigazione. Criterio: l'app si apre, mostra l'avatar, va da una pagina vuota all'altra, `info` arriva dal finto motore.
- **Poi in parallelo, ognuna nel suo worktree:** **S5b** (Progetti, Campioni e prodotto, Scelte, Motore, Come citare) e **S6** (Esecuzione, Risultati, Sicurezza alimentare). Non toccano gli stessi file: solo `pagine/` diverse. `finestra.py`, `motore.py`, `stile.qss` si cambiano solo in S5a.
- ~~PySide6 non è installato sul PC~~ → deciso il 16/10 (D072): Python 3.11 di Windows con un ambiente dedicato `app/.venv` (fuori da git), versioni in `app/requirements.txt` (PySide6 6.12.0); il pacchetto per gli utenti si fa in S13.

### 7.1 Lo scheletro fatto (S5a, 16/10): come lo usano S5b e S6

**Avvio:** `app\.venv\Scripts\python -m app.main` dalla cartella del progetto. Col finto motore: `set PMN_MOTORE=finto`
(e, se serve, `set PMN_FINTO_OPZIONI=--velocita 0 --scenario DB_MANCANTE`). Test: `app\.venv\Scripts\python -m pytest tests/test_app_*.py`.

| File | Che cosa dà alle pagine | Chi lo cambia |
|---|---|---|
| `app/pagine/base.py` | `Pagina` (sotto), `Contesto` (`info` = ultimo `info` del motore, `progetto` = progetto aperto, `avvia_analisi` = passaggio da Scelte ad Analisi in corso, `progetto_in_analisi` = progetto della corsa che gira), `etichetta(testo, nome)`, `riquadro(titolo, testo, livello)` (info, avviso, errore), `numero(x, cifre)` (virgola all'italiana, R11), `Scelta`, `riga_di_scelte`, `pannello(titolo=None)`, `svuota(layout)` | solo S5a |
| `app/motore.py` | `MotoreClient`: `avvia(comando, *argomenti)`, segnali `evento(dict)` e `finito(codice_uscita, evento_fine)`, `annulla()`, `in_corso()`, `corsa`, `diagnostica`; `percorso_per_motore(p)` (Windows → `/mnt/c/...` per il motore vero) | solo S5a |
| `app/finestra.py`, `app/stile.qss`, `app/main.py` | testata, percorso (✓ dallo stato del progetto), barra delle azioni, avvio con l'avatar, avatar che respira, ordine del Tab e tasto Invio, "riduci movimento"; tutto lo stile (anche schede, pannelli, campi); immagini dello stile con `url(risorse:nome)` | solo S5a |
| `app/progetto.py` | `Progetto` (`config`, `risultati`, `leggi()`, `scrivi(dati)` con `yaml.safe_dump`, tutto o niente), `nuovo(nome)`, `elenco()`, `cartella_progetti()` = Documenti\ProfileMetaNanni | S5b (S6 lo usa, non lo cambia) |
| `app/pagine/home.py progetto.py scelte.py motore.py crediti.py` | pagine vere (fatte il 16/10, `tests/test_app_s5b.py`) | **S5b** |
| `app/pagine/esecuzione.py risultati.py sicurezza.py` | pagine vere (fatte il 16/10, `tests/test_app_s6.py`) | **S6** |

**Come si scrive una pagina** (sottoclasse di `Pagina`, costruttore `(contesto, parent=None)`):
- contenuto in `self.corpo` (un `QVBoxLayout`, il titolo c'è già se si mette `titolo`); la finestra la mette da sola dentro una zona che scorre;
- barra delle azioni: `testo_principale`, `azione_principale()` (predefinito: va a `destinazione`), `principale_attivo`, `principale_pericolo` (True: bianco col bordo rosso, per "Ferma"), `aiuto` e `aiuto_livello = "avviso"`, `secondari = [(testo, funzione)]`; dopo ogni cambio `self.azioni_cambiate.emit()`;
- segnali: `vai.emit("risultati")` per cambiare pagina, `respira.emit(True/False)` per l'avatar durante un lavoro lungo, `info_cambiata.emit()` dopo aver cambiato `contesto.info` (pallino della testata);
- `mostrata()` si chiama a ogni ingresso nella pagina: lì si rilegge `self.contesto`;
- chiavi delle pagine: `home`, `campioni`, `scelte`, `esecuzione`, `risultati`, `sicurezza`, `motore`, `crediti`.
- **da Scelte (S5b) ad Analisi in corso (S6):** "Avvia l'analisi" scrive `config.yaml`, mette `contesto.progetto` e `contesto.avvia_analisi = True`, poi `vai("esecuzione")`; la pagina Esecuzione, in `mostrata()`, lancia `esegui --progetto` solo se `avvia_analisi` è True e lo rimette a False (entrare dal percorso non fa partire nulla).

**Garanzia del `MotoreClient`:** ogni corsa finisce con un solo evento `fine` e poi `finito`. Se il motore non parte
(per esempio la WSL `pmn` non c'è) arriva un `errore` con codice **`MOTORE_NON_AVVIATO`** e `cosa_fare` "Apri la pagina Motore
e premi Controlla il motore."; se si chiude dopo `inizio` senza `fine`, un `errore` **`ERRORE_INTERNO`** (D077). Sono codici
dell'interfaccia, non del motore. Righe non JSON e stderr vanno in `diagnostica`, mai all'utente (R2).

**S5b e S6 (16/10 sera):** fatte in parallelo e unite in locale (`f0616ea`, `f4c432d`); 44 test dell'app verdi; giro completo da Nuovo progetto alla sicurezza alimentare col finto motore. Decisioni D078-D096 (AMBIENTE); richieste allo scheletro e al motore in AMBIENTE "PROBLEMI APERTI".

**Rifinitura (16/10 sera):** richieste di S5b e S6 allo scheletro fatte (sopra); un progetto alla volta durante un'analisi (D097); tastiera (R15): Tab in ordine di lettura (testata, percorso, pagina dall'alto, barra con il principale per ultimo), Invio preme il pulsante col fuoco, fuoco sempre visibile, `tests/test_app_tastiera.py` su tutte le 8 pagine (D099); "riduci movimento" di Windows letto a ogni animazione, spente anche le animazioni di Qt (D100). 62 test dell'app verdi.

**Criteri di S5a, verificati il 16/10:** l'app si apre, l'avatar saltella e si ferma (fotografie a 0,5 s e 2 s), le pagine vuote
si navigano col solo pulsante principale, `info` arriva dal finto motore ("15,6 GB di memoria, 8 processori"); 12 test
`tests/test_app_scheletro.py` verdi; 166 test del motore in WSL invariati.

---

## 8. Domande di progetto: risposte del 16/10 (intervista di S5a)

1. **Soglia di legge nel grafico:** no, come D060 (D074).
2. **Dove gira la GUI:** Python di Windows con PySide6 in `app/.venv` (D072).
3. **Prodotti del passo 1:** bastano maiale, bovino, pecora, altro (D074).
4. **"Aggiungi al referto":** sezione nello stesso referto (D076).
5. **Ponte FSSP con la conta totale:** lattici = conta × % MetaPhlAn **sul totale delle read** (come oggi, D075).
