# Lingua inglese: termini da controllare (dopo L6b)

> Sessione Lingua IT/EN, 18/10/2026, ramo `lingua-it-en`.
> L'inglese è una **prima stesura**. Questi termini si controllano **dopo la prova con 5 persone (L6b)**.
> Le traduzioni stanno in due file: `app/risorse/lingua_en.json` (app) e `motore/lingua_en.json` (motore, referto, FSSP).
> Per cambiare una traduzione: si cambia solo il testo inglese a destra, mai la frase italiana a sinistra (è la chiave).

## 1. Termini scientifici

| Italiano | Inglese (prima stesura) | Dove | Da decidere |
|---|---|---|---|
| ufc/g | CFU/g | sicurezza alimentare, referto | ok così? |
| batteri lattici | lactic acid bacteria | app, referto, FSSP | nelle note FSSP resta la sigla LAB |
| LAB | LAB | note FSSP ("Initial LAB...") | lasciare la sigla o scriverla per intero? |
| CNS (stafilococchi coagulasi-negativi) | non compare nei testi | nessuno | niente da fare oggi |
| lattobacilli psicrotolleranti | psychrotolerant lactobacilli | note FSSP, Come citare | |
| ospite (DNA dell'ospite) | host (host DNA) | tutto | |
| read, coppie di read | reads, read pairs | tutto | |
| abbondanza relativa | relative abundance | glossario del referto | |
| soglia di abbondanza | abundance threshold | scelte, referto | |
| soglia di confidenza di Kraken | Kraken confidence threshold | scelte, risultati | |
| read minime per specie (Bracken) | minimum reads per species (Bracken) | scelte, risultati | |
| % fra i taxa / % sul totale assegnato | % among the taxa / % of all assigned | referto, Excel | |
| segnalati a parte | reported separately | risultati, referto | |
| fase acquosa (sale nella fase acquosa) | water phase (salt in the water phase) | sicurezza alimentare | "water phase salt" è più comune? |
| aw (acqua libera) | aw (free water) | sicurezza alimentare | "water activity"? |
| fenoli del fumo | smoke phenols | sicurezza alimentare | |
| diacetato | diacetate | sicurezza alimentare | |
| scenari "e se" | "what if" scenarios | FSSP, referto | |
| ritardo iniziale (lag) | initial delay (lag) | sicurezza alimentare | "lag phase"? |
| campo di validità del modello | range of the model | avvisi FUORI_CAMPO | "range of applicability" come in FSSP? |
| psi (1 o più = non cresce) | psi (1 or more = no growth) | referto | |
| salume / salume di maiale | cured meat product / pork product | campioni e prodotto | |
| salame a fermentazione spontanea, giorno 7 di stagionatura | spontaneously fermented salami, day 7 of ripening | campione d'esempio | |
| bresaola, carne secca | bresaola, dried meat | campioni e prodotto | |

## 2. Nomi dei passi dell'analisi

| Italiano | Inglese |
|---|---|
| Scarico le read | Downloading the reads |
| Controllo la qualità | Checking the quality |
| Pulisco le read | Cleaning the reads |
| Tolgo il DNA dell'ospite | Removing the host DNA |
| Profilo con MetaPhlAn / con Kraken | Profile with MetaPhlAn / with Kraken |
| Preparo referto e tabelle | Preparing report and tables |
| Esito del triage: buono, da controllare, da rifare | good, to check, to redo |

## 3. Parole dell'interfaccia

| Italiano | Inglese | Nota |
|---|---|---|
| Motore | Engine | |
| referto | report | |
| Database completo / Screening rapido | Full database / Quick screening | |
| MetaPhlAn a fette (in 6 parti) | MetaPhlAn in slices (in 6 parts) | |
| Prototipo, non per decisioni. | Prototype, not for decisions. | D115 |
| VERDE / ROSSO | GREEN / RED | verifica del motore |
| Migliorato (consigliato) / Come FSSP | Improved (recommended) / As FSSP | modo di calcolo FSSP |
| Fogli Excel | ReadMe, MetaPhlAn_species, Kraken_taxa, Kraken_separate, Triage, Safety, Parameters, Tools_citations | |

## 4. Limiti noti dell'inglese (da sapere, non errori)

- **Valori del file del progetto**: nel referto inglese i valori `fette`, `completo`, `rapido` restano così (sono le
  impostazioni di `config.yaml`); accanto c'è la spiegazione in inglese.
- **Testi già salvati nei risultati**: le frasi del motore in `risultati.json` (sintesi, motivi del triage, citazioni,
  note FSSP) restano nella lingua della corsa. Se si cambia lingua dopo l'analisi, le pagine sono in inglese ma quelle
  frasi restano in italiano fino a una nuova analisi.
- **Installatore Windows** (`installer/windows/installa_pmn.ps1` e il messaggio "estrai prima" del `.cmd`) e
  **installazione del motore** (`installer/installa_motore.sh`): in italiano e in inglese dal 18/10 (B2, P12), vedi §6.
- **Nomi dei controlli** della verifica vera
  (`installer/verifica_motore.sh`): ancora solo in italiano. Il finto motore li ha in inglese.
- **Plurale "1 seconds"**: come in italiano oggi ("1 secondi"), la durata non distingue il singolare.
- **Nomi di prova** come `esempio_SF3RAt7` (cartella del progetto d'esempio) restano uguali in tutte le lingue.

## 5. Un difetto già presente (in italiano): corretto in R1 (18/10)

- `motore/system_one.py`, motivo del triage: era "poche read ... (circa 900.000**.** minimo 1.000.000)": il punto
  delle migliaia sostituiva anche la virgola prima di "minimo". Corretto in R1: il punto va solo nei numeri
  ("circa 900.000, minimo 1.000.000"); test in `tests/test_system_one.py`, fotografia dell'italiano rifatta (cambiano
  solo queste righe).

## 6. Installatore Windows (B2, P12, 18/10)

I testi stanno in una sola tabella, `$TESTI` in cima a `installer/windows/installa_pmn.ps1` (italiano e inglese uno accanto
all'altro); il messaggio "estrai prima" sta in `installer/windows/costruisci_pacchetto.py` (`ESTRAI`). Lingua: quella
di Windows (`Get-UICulture`): italiano se comincia con "it", altrimenti inglese. Con Windows in inglese l'installatore
imposta anche l'app in inglese, se la persona non ha già scelto.

| Italiano | Inglese (prima stesura) | Da decidere |
|---|---|---|
| installazione / riapri l'installazione | installation / open the installation again | "run the installer again"? |
| componente di Windows (WSL) | component of Windows (WSL) | "Windows feature"? |
| attivare WSL | turn on WSL | "enable WSL"? |
| rispondi Sì | answer Yes | |
| ambiente Linux | Linux environment | |
| disco interno adatto (NTFS) | suitable internal disk (NTFS) | |
| Procedo con l'installazione? | Shall I go ahead with the installation? | "Continue with the installation?" |
| Tutto pronto | All ready | "All set"? |
| finestra di benvenuto | welcome window | |
| Estrai tutto... / Estrai (menu di Windows) | Extract All... / Extract | sono i nomi del menu di Windows in inglese |
| Dettagli tecnici nel file | Technical details in the file | |

Installazione del motore (`installer/installa_motore.sh`): tabella `EN` in cima allo script, la frase italiana è la
chiave (come nell'app); la lingua arriva con `--lingua en` (dall'installatore Windows) o con `PMN_LINGUA` (da
`pmn-motore`). Numeri: virgola in italiano, punto in inglese.

| Italiano | Inglese (prima stesura) | Da decidere |
|---|---|---|
| gestore dei programmi (micromamba) | program manager (micromamba) | "package manager"? |
| ambiente (dei programmi) | environment | |
| catalogo dei database | database catalogue | "catalog" (americano)? |
| specchio locale | local mirror | |
| rovinato (MD5 diverso) | damaged (different MD5) | "corrupted"? |
| archivio da estrarre | archive to extract | |
| Rilancia / rilanciala | Run it again | |
| Prova finale su un piccolo campione | Final test on a small sample | |
| VERDE / ROSSO | GREEN / RED | come nell'app |

