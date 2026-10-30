#!/usr/bin/env bash
# installer/installa_motore.sh - installa il motore di profilemetananni su Linux o WSL2, senza permessi di amministratore.
# Un solo comando; se si interrompe (rete, spegnimento) basta rilanciarlo: riprende da dove era rimasto (D027, D034).
# Programmi: micromamba + ambienti dal file di blocco (installer/lock/). Database: installer/catalogo.tsv, con MD5.
#
# Uso: bash installer/installa_motore.sh [--si] [--stima] [--json] [--catalogo FILE] [--specchio URL] [--connessioni N]
#   --si        non chiede conferma (la chiede l'interfaccia, D034)
#   --stima     dice peso, spazio e tempo stimato e si ferma senza scaricare (per la domanda dell'interfaccia)
#   --json      messaggi come eventi JSON, uno per riga (docs/contratto_motore.md)
#   --catalogo  altro catalogo (prova)
#   --specchio  tutte le sorgenti da un solo indirizzo, es. http://127.0.0.1:8765 (prova con lo specchio locale, D038)
#   --lingua    it (predefinita) o en: lingua dei messaggi per la persona (anche con PMN_LINGUA, come motore/lingua.py)
#   --connessioni N    connessioni insieme per i file a pezzi (indici Kraken e righe con url_alternativo), predefinita 16,
#                      anche con PMN_CONNESSIONI (D165)
#   --spazio-libero B  byte liberi veri (li passa la parte Windows: dentro WSL "df" vede il disco virtuale da 1 TB)
#   --solo-database    solo i database, senza programmi e prova finale (prove con lo specchio locale)
# Variabili: PMN_HOME (predefinita ~/.pmn), PMN_URL_PACCHETTI (dove sono pubblicati i pacchetti pmn, predefinita la Release database-v1 su GitHub).
#
# v1.1 (D165): i file della sorgente kraken (S3, velocita' limitata per connessione) si scaricano a pezzi con richieste
# Range, CONN connessioni insieme, un file <nome>.pezzo.<i> per pezzo; le sorgenti diverse lavorano insieme (kraken e
# pmn, 4 file pmn alla volta); gli archivi si estraggono mentre arrivano, con l'MD5 calcolato nello stesso passaggio.
set -euo pipefail

PMN_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PMN_HOME=${PMN_HOME:-$HOME/.pmn}
CATALOGO=$PMN_ROOT/installer/catalogo.tsv
SPECCHIO=""; SI=0; STIMA=0; JSON=0; LINGUA=${PMN_LINGUA:-it}; CONN=${PMN_CONNESSIONI:-16}; SPAZIO_VERO=""; SOLO_DB=0
MICROMAMBA_VER=2.9.0-0
MICROMAMBA_SHA256=366cd9cd8be14df1ab8ed50352a82111082a36686b2d389fdb79a92c3fafb3e3
URL_KRAKEN=https://genome-idx.s3.amazonaws.com/kraken
URL_PMN=${PMN_URL_PACCHETTI:-https://github.com/GiampieroFederici/profilemetananni/releases/download/database-v1}
ENVS=(pmn_download pmn_qc pmn_trim pmn_hostfilter pmn_metaphlan pmn_kraken pmn_stats_r pmn_reports_py)
GB_PROGRAMMI=16   # ambienti installati + cache dei pacchetti durante l'installazione (misurati: ~11 GB + margine)
PEZZO_MAX=134217728   # 128 MiB: pezzo piu' grande di un file scaricato a pezzi
FILE_INSIEME=4        # file della stessa sorgente scaricati insieme (Release GitHub), una connessione ciascuno (D165)
OGNI_S=15             # secondi fra due eventi di avanzamento durante lo scarico (contratto: al massimo 30)

ARGOMENTI=("$@")
while [ $# -gt 0 ]; do
  case "$1" in
    --si) SI=1; shift ;;
    --stima) STIMA=1; shift ;;
    --json) JSON=1; shift ;;
    --catalogo) CATALOGO=$2; shift 2 ;;
    --specchio) SPECCHIO=${2%/}; shift 2 ;;
    --lingua) LINGUA=$2; shift 2 ;;
    --connessioni) CONN=$2; shift 2 ;;
    --spazio-libero) SPAZIO_VERO=$2; shift 2 ;;
    --solo-database) SOLO_DB=1; shift ;;
    *) echo "Opzione sconosciuta: $1" >&2; exit 1 ;;
  esac
done
[[ $CONN =~ ^[1-9][0-9]?$ ]] || { echo "--connessioni (PMN_CONNESSIONI): un numero da 1 a 99, non '$CONN'" >&2; exit 1; }
[[ -z $SPAZIO_VERO || $SPAZIO_VERO =~ ^[0-9]+$ ]] || { echo "--spazio-libero: un numero di byte, non '$SPAZIO_VERO'" >&2; exit 1; }
# P41: con l'interfaccia (--json) in un gruppo di processi suo (bash, curl, tar), così "annulla --corsa" li ferma tutti
# con un solo segnale. Da un terminale lo script è già capo del suo gruppo: resta com'è (Ctrl+C funziona)
if [ "$JSON" = 1 ] && [ "$(cut -d' ' -f5 /proc/$$/stat 2> /dev/null)" != "$$" ] && command -v setsid > /dev/null; then
  exec setsid bash "$0" "${ARGOMENTI[@]}"   # stesso pid: chi ci ha lanciato ci aspetta come prima
fi

# --- B2 (P12): testi per la persona in italiano o in inglese. Come _() dell'app e del motore: la frase italiana e' la
#     chiave (%s al posto dei valori) e le traduzioni stanno tutte qui (termini: docs/lingua_termini_da_controllare.md).
declare -A EN=(
  ["Installazione non completata. Rilanciala quando hai risolto: riprende da qui."]="Installation not completed. Run it again when you have solved the problem: it resumes from here."
  ["Installazione interrotta. Rilancia lo stesso comando: riprende da dove era rimasta."]="Installation interrupted. Run the same command again: it resumes from where it stopped."
  ["Installazione del motore di profilemetananni. Dettagli tecnici in %s"]="Installation of the profilemetananni engine. Technical details in %s"
  ["Serve Linux a 64 bit (anche dentro WSL2 su Windows)."]="64-bit Linux is needed (also inside WSL2 on Windows)."
  ["Usa un PC con Windows 10/11 o Linux a 64 bit."]="Use a PC with Windows 10/11 or 64-bit Linux."
  ["Manca il programma di sistema '%s'."]="The system program '%s' is missing."
  ["Su Ubuntu: sudo apt install %s"]="On Ubuntu: sudo apt install %s"
  ["Non trovo il catalogo dei database (%s)."]="I cannot find the database catalogue (%s)."
  ["Riscarica profilemetananni."]="Download profilemetananni again."
  ["Da scaricare: circa %s GB. Spazio necessario: %s GB. Spazio libero: %s GB."]="To download: about %s GB. Space needed: %s GB. Free space: %s GB."
  ["Lo spazio libero non basta: servono %s GB, ce ne sono %s."]="The free space is not enough: %s GB are needed, there are %s."
  ["Libera spazio sul disco e rilancia."]="Free some space on the disk and run it again."
  ["1 minuto"]="1 minute"
  ["%s minuti"]="%s minutes"
  ["%s ore"]="%s hours"
  ["altri database"]="other databases"
  ["Velocità misurata: %s. Tempo stimato per scaricare tutto: circa %s."]="Measured speed: %s. Estimated time to download everything: about %s."
  ["Non riesco a misurare la velocità della rete: proseguo senza stima del tempo."]="I cannot measure the network speed: I go on without a time estimate."
  ["Stima pronta: non ho scaricato nulla."]="Estimate ready: I have not downloaded anything."
  ["Installazione annullata: non ho scaricato nulla."]="Installation cancelled: I have not downloaded anything."
  ["Scarico il gestore dei programmi (micromamba %s)..."]="Downloading the program manager (micromamba %s)..."
  ["Non riesco a scaricare micromamba."]="I cannot download micromamba."
  ["Controlla la connessione e rilancia."]="Check the connection and run it again."
  ["Il file di micromamba scaricato è rovinato."]="The downloaded micromamba file is damaged."
  ["Rilancia l'installazione."]="Run the installation again."
  ["Installo i programmi: ambiente %s di %s (%s)..."]="Installing the programs: environment %s of %s (%s)..."
  ["Non riesco a installare l'ambiente %s."]="I cannot install the environment %s."
  ["L'ambiente %s non corrisponde alle versioni previste."]="The environment %s does not match the expected versions."
  ["Programmi installati (%s ambienti, MetaPhlAn %s)."]="Programs installed (%s environments, MetaPhlAn %s)."
  ["La connessione si è interrotta: riprovo fra %s secondi (tentativo %s di 30)."]="The connection was interrupted: I try again in %s seconds (attempt %s of 30)."
  ["Scarico %s: %s (%s GB)..."]="Downloading %s: %s (%s GB)..."
  ["Non riesco a scaricare %s."]="I cannot download %s."
  ["Il file %s scaricato è rovinato (MD5 diverso)."]="The downloaded file %s is damaged (different MD5)."
  ["Ho già riscaricato una volta. Riapri l'installazione più tardi; se si ripete, manda a noi il file %s."]="I have already downloaded it again once. Open the installation again later; if it happens again, send us the file %s."
  ["Scarico %s (%s GB, archivio da estrarre)..."]="Downloading %s (%s GB, archive to extract)..."
  ["L'archivio %s scaricato è rovinato (MD5 diverso)."]="The downloaded archive %s is damaged (different MD5)."
  ["Estraggo e controllo %s..."]="Extracting and checking %s..."
  ["Non riesco a estrarre %s."]="I cannot extract %s."
  ["Controlla lo spazio libero e rilancia."]="Check the free space and run it again."
  ["I file di %s non hanno l'MD5 atteso."]="The files of %s do not have the expected MD5."
  ["Scarico i database: %s di %s GB (%s)."]="Downloading the databases: %s of %s GB (%s)."
  ["Spazio stretto: estraggo gli archivi mentre arrivano e cancello ogni pezzo appena letto. Se l'installazione si interrompe, l'archivio in corso riparte da capo."]="Little space: I extract the archives while they arrive and delete every piece as soon as it is read. If the installation stops, the archive in progress starts again from the beginning."
  ["Database scaricati e controllati."]="Databases downloaded and checked."
  ["Prova finale su un piccolo campione (alcuni minuti)..."]="Final test on a small sample (a few minutes)..."
  ["VERDE: il motore è installato e funziona."]="GREEN: the engine is installed and works."
  ["ROSSO: la prova finale non ha dato il risultato atteso."]="RED: the final test did not give the expected result."
  ["Manda a noi il file %s."]="Send us the file %s."
  ["ERRORE"]="ERROR"
  ["Cosa fare"]="What to do"
  ["Attenzione"]="Warning"
)
T() { local f=$1; shift; if [ "$LINGUA" = en ] && [ -n "${EN[$f]+x}" ]; then f=${EN[$f]}; fi; printf -- "$f" "$@"; }
num() { awk -v x="$1" -v d="$2" -v c="$3" -v l="$LINGUA" 'BEGIN {s = sprintf("%." c "f", x / d); if (l != "en") sub(/\./, ",", s); print s}'; }   # valore divisore cifre

# --- messaggi: righe in italiano, oppure eventi JSON (docs/contratto_motore.md, paragrafo 4) ---
# avanzamento usa FATTO e TOTALE (pezzi del passo) ed ETA (secondi, o null), piu' AV_EXTRA (campi nuovi facoltativi
# v1.1: byte_fatti, byte_totali, velocita_mb_s, sorgente, sorgenti); fine usa ESITO e RISULTATO (oggetto JSON).
PASSO=controllo; FATTO=0; TOTALE=1; ETA=null; ESITO=ok; RISULTATO='{}'; AV_EXTRA=""
CORSA=$(date +%Y-%m-%dT%H-%M-%S)
js() { local t=${1//\\/\\\\}; printf '%s' "${t//\"/\\\"}"; }   # testo dentro una stringa JSON
mb_s() { num "$1" 1e6 1; }   # B2 (P5): byte/s -> "57,2" (in inglese "57.2")
evento() {  # tipo percentuale messaggio [codice] [cosa_fare]
  if [ "$JSON" = 1 ]; then
    local extra=""
    case "$1" in
      inizio) extra=",\"corsa\":\"$CORSA\",\"log\":\"$(js "$LOG")\"" ;;
      avanzamento) extra=",\"campione\":null,\"fatto\":$FATTO,\"totale\":$TOTALE,\"eta_s\":$ETA$AV_EXTRA" ;;
      avviso) extra=",\"codice\":\"$4\"" ;;
      errore) extra=",\"codice\":\"$4\",\"cosa_fare\":\"$(js "$5")\"" ;;
      fine) extra=",\"esito\":\"$ESITO\",\"risultato\":$RISULTATO" ;;
    esac
    printf '{"tipo":"%s","ora":"%s","comando":"installa","passo":"%s","percentuale":%s,"messaggio":"%s"%s}\n' \
      "$1" "$(date -Iseconds)" "$PASSO" "${2:-null}" "$(js "$3")" "$extra"
  else
    case "$1" in
      errore) printf '\n[PMN] %s: %s\n[PMN] %s: %s\n' "$(T 'ERRORE')" "$3" "$(T 'Cosa fare')" "${5:-}" ;;
      avviso) printf '[PMN] %s: %s\n' "$(T 'Attenzione')" "$3" ;;
      *) printf '[PMN] %s\n' "$3" ;;
    esac
  fi
}
fallisci() {  # codice messaggio cosa_fare
  if [ "$BASHPID" != "$$" ]; then   # dentro una coda di scarico: lo dice il ciclo principale, che ferma tutto
    printf '%s\t%s\t%s\n' "$1" "$2" "$3" > "$ST/errore.$BASHPID"; exit 1
  fi
  evento errore null "$2" "$1" "$3"
  RISULTATO="{\"codice\":\"$1\",\"passo\":\"$PASSO\"}"; PASSO=fine; ESITO=errore   # contratto v0.3: {"codice", "passo"}
  evento fine null "$(T 'Installazione non completata. Rilanciala quando hai risolto: riprende da qui.')"
  exit 2
}
# v1.1 (R6): all'uscita, per qualunque motivo, si fermano anche le code di scarico, curl e tar nati da questo script:
# nessuno resta a scaricare da solo. Se nessuno legge piu' gli eventi (la finestra di Windows e' stata chiusa a forza)
# il prossimo evento (al massimo OGNI_S secondi) da' SIGPIPE: si esce allo stesso modo.
discendenti() {  # pid: tutti i processi nati da pid (figli, nipoti...)
  ps -e -o pid=,ppid= | awk -v r="$1" '{p[$1] = $2} END {for (x in p) {y = x; n = 0; while ((y in p) && y != r && y > 1 && n++ < 64) y = p[y]; if (y == r && x != r) print x}}'
}
ferma_figli() { local l; l=$(discendenti "$$") || true; if [ -n "$l" ]; then kill $l 2> /dev/null || true; fi; }
BLOCCO=""
alla_fine() { ferma_figli; rm -rf "${ST:-}"; if [ -n "$BLOCCO" ]; then rm -f "$BLOCCO"; fi; }
trap alla_fine EXIT
trap 'PASSO=fine; ESITO=annullata; evento fine null "$(T "Installazione interrotta. Rilancia lo stesso comando: riprende da dove era rimasta.")"; exit 3' INT TERM
trap 'exit 3' PIPE HUP

mkdir -p "$PMN_HOME"/{bin,db,stato,tmp,log}
ST=$PMN_HOME/tmp/scarico_$$   # stato delle code di scarico di questa corsa (tolto alla fine)
# P41: corsa e gruppo per annulla (pmn_motore.py lo legge), solo se il gruppo è nostro; tolto alla fine
if [ "$JSON" = 1 ] && [ "$STIMA" = 0 ] && [ "$(cut -d' ' -f5 /proc/$$/stat 2> /dev/null)" = "$$" ]; then
  printf '{"corsa":"%s","pid":%s,"pgid":%s}\n' "$CORSA" "$$" "$$" > "$PMN_HOME/stato/installa.lock"
  BLOCCO=$PMN_HOME/stato/installa.lock
fi
export TMPDIR=$PMN_HOME/tmp   # /tmp di WSL sta in RAM: download ed estrazioni su disco
LOG=$PMN_HOME/log/installazione_$(date +%Y%m%d_%H%M%S).log
evento inizio 0 "$(T 'Installazione del motore di profilemetananni. Dettagli tecnici in %s' "$LOG")"

# ===================== 1. controlli =====================
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] \
  || fallisci SISTEMA_NON_ADATTO "$(T 'Serve Linux a 64 bit (anche dentro WSL2 su Windows).')" "$(T 'Usa un PC con Windows 10/11 o Linux a 64 bit.')"
for c in curl tar gzip md5sum sha256sum awk df ps mkfifo; do
  command -v "$c" > /dev/null || fallisci PROGRAMMA_MANCANTE "$(T "Manca il programma di sistema '%s'." "$c")" "$(T 'Su Ubuntu: sudo apt install %s' "$c")"
done
[ -s "$CATALOGO" ] || fallisci CONFIG_NON_VALIDA "$(T 'Non trovo il catalogo dei database (%s).' "$CATALOGO")" "$(T 'Riscarica profilemetananni.')"

url_di() {  # sorgente percorso
  if [ -n "$SPECCHIO" ]; then printf '%s/%s/%s' "$SPECCHIO" "$1" "$2"
  elif [ "$1" = kraken ]; then printf '%s/%s' "$URL_KRAKEN" "$2"
  else printf '%s/%s' "$URL_PMN" "${2//\//__}"   # E1: la Release di GitHub vuole nomi piatti, "/" diventa "__"
  fi
}
# pezzo gia' scaricato e verificato: il segnalino contiene l'MD5 della riga e il file (o la cartella) c'e' ancora
segnalino() { printf '%s/stato/%s.ok' "$PMN_HOME" "${1//\//__}"; }   # destinazione
fatto() { [ "$(cat "$(segnalino "$1")" 2>/dev/null)" = "$2" ] && [ -e "$PMN_HOME/db/$1" ]; }   # destinazione md5
connessioni() { if [ "$1" = kraken ] || [ -n "${2:-}" ]; then echo "$CONN"; else echo 1; fi; }   # sorgente url_alternativo
dim_pezzo() {  # byte connessioni: almeno 8 pezzi per connessione (pochi pezzi in volo quando si cancellano), 1-128 MiB
  local d=$(( ($1 + 8 * $2 - 1) / (8 * $2) ))
  [ "$d" -ge 1048576 ] || d=1048576; [ "$d" -le "$PEZZO_MAX" ] || d=$PEZZO_MAX; echo "$d"
}
righe() { tail -n +2 "$CATALOGO" | while IFS=$'\t' read -r g t s p b bf m d alt; do printf '%s\t' "$g" "$t" "$s" "$p" "$b" "$bf" "$m" "$d"; printf '%s\n' "${alt:-}"; done; }
dim() { stat -c %s -- "$1" 2> /dev/null || echo 0; }
scrivi() { echo "$2" > "$1.t" && mv -f "$1.t" "$1"; }   # file numero: scritto tutto insieme (chi legge non lo vede a meta')
leggi() { cat "$1" 2> /dev/null || echo 0; }
base_di() { if [ "$1" = tar ]; then printf '%s/tmp/%s' "$PMN_HOME" "$(basename "$2")"; else printf '%s/db/%s' "$PMN_HOME" "$3"; fi; }   # tipo percorso destinazione
sul_disco() {  # tipo percorso byte md5 destinazione: byte gia' scaricati e ancora sul disco (pezzi e .parziale), al massimo byte
  local base
  if fatto "$5" "$4"; then echo "$3"; return; fi
  base=$(base_di "$1" "$2" "$5")
  { stat -c %s -- "$base.parziale" "$base".pezzo.* 2> /dev/null || true; } | awk -v b="$3" '{s += $1} END {printf "%.0f\n", (s > b ? b : s)}'
}
# A6 (VM 30/10): il primo giro fermato con "wsl --terminate" non passa da alla_fine e lascia scarico_<pid>: si toglie
# alla corsa dopo, se quel processo non c'e' piu' (una corsa ancora viva, per esempio una --stima, non si tocca)
for d in "$PMN_HOME"/tmp/scarico_*; do
  if [ -d "$d" ] && [ ! -e "/proc/${d##*_}" ]; then rm -rf "$d"; fi
done

# --- spazio (v1.1, R3: l'unica regola, la legge anche installa_pmn.ps1 dal risultato di --stima) ---
# servono: i byte finali di cio' che manca + pochi pezzi in volo dell'archivio piu' grande (estratto mentre arriva,
# ogni pezzo cancellato appena letto) + i programmi se un ambiente manca. Se c'e' spazio anche per l'archivio intero
# i pezzi si tengono fino all'MD5 giusto (ripresa completa); se no si cancellano appena letti (RISPARMIO=1).
read -r DA_SCARICARE FINALI MARGINE ARCHIVIO < <(
  righe | while IFS=$'\t' read -r g t s p b bf m d alt; do
    if fatto "$d" "$m"; then continue; fi   # A6: da scaricare = cio' che manca, senza i pezzi gia' sul disco
    c=$(connessioni "$s" "$alt"); echo "$t $b $bf $(dim_pezzo "$b" "$c") $c $(sul_disco "$t" "$p" "$b" "$m" "$d")"
  done | awk '{s += $2 - $6; f += $3; if ($1 == "tar") {w = 2 * $5 * $4; if (w > $2) w = $2; if (w > m) m = w; if ($2 > a) a = $2}}
              END {printf "%.0f %.0f %.0f %.0f\n", s, f, m, a}')
SERVONO=$((FINALI + MARGINE))
GIB=1073741824   # 22/10: GB mostrati come Esplora file e installa_pmn.ps1 (1.024^3 byte)
GB() { awk -v b="$1" -v g="$GIB" 'BEGIN {printf "%.0f", b/g}'; }
LIBERI=$(( $(df -Pk "$PMN_HOME" | awk 'NR==2 {print $4}') * 1024 ))
if [ -n "$SPAZIO_VERO" ] && [ "$SPAZIO_VERO" -lt "$LIBERI" ]; then LIBERI=$SPAZIO_VERO; fi
export MAMBA_ROOT_PREFIX=$PMN_HOME/mamba
uguale_al_blocco() {  # env: i pacchetti installati sono esattamente quelli del file di blocco?
  local d=$MAMBA_ROOT_PREFIX/envs/$1
  [ -d "$d/conda-meta" ] || return 1
  diff -q <(grep '^https://' "$PMN_ROOT/installer/lock/$1.txt" | sed 's|.*/||; s|#.*||; s|\.conda$||; s|\.tar\.bz2$||' | sort) \
          <(cd "$d/conda-meta" && ls -- *.json | sed 's|\.json$||' | sort) > /dev/null
}
if [ "$SOLO_DB" = 0 ]; then
  for e in "${ENVS[@]}"; do   # 22/10: lo spazio dei programmi serve solo se un ambiente manca o va rifatto
    if ! uguale_al_blocco "$e"; then SERVONO=$(( SERVONO + GB_PROGRAMMI * 1000000000 )); break; fi
  done
fi
RISPARMIO=0; [ "$LIBERI" -gt $(( SERVONO - MARGINE + ARCHIVIO )) ] || RISPARMIO=1
evento avanzamento 1 "$(T 'Da scaricare: circa %s GB. Spazio necessario: %s GB. Spazio libero: %s GB.' "$(GB "$DA_SCARICARE")" "$(GB "$SERVONO")" "$(GB "$LIBERI")")"
[ "$LIBERI" -gt "$SERVONO" ] \
  || fallisci SPAZIO_INSUFFICIENTE "$(T 'Lo spazio libero non basta: servono %s GB, ce ne sono %s.' "$(GB "$SERVONO")" "$(GB "$LIBERI")")" "$(T 'Libera spazio sul disco e rilancia.')"

# --- velocita' della rete per sorgente (v1.1, R4): come si scarichera' davvero, le sorgenti insieme (D034) ---
durata() {  # secondi -> "12 minuti", "8,1 ore"
  local min=$(( $1 / 60 + 1 ))
  if [ "$min" -eq 1 ]; then T '1 minuto'; elif [ "$min" -lt 60 ]; then T '%s minuti' "$min"; else T '%s ore' "$(num "$min" 60 1)"; fi
}
etichetta() { if [ "$1" = kraken ]; then printf 'Kraken'; else T 'altri database'; fi; }
prova_range() {  # url: codice HTTP di una richiesta Range di 1 byte (206 = il server da' i pezzi)
  curl -fsL --connect-timeout 30 --max-time 60 -r 0-0 -o /dev/null -w '%{http_code}' "$1" 2>> "$LOG" || true
}
misura_una() { curl -fsL --connect-timeout 15 --max-time "$3" -r "$2" -o /dev/null -w '%{speed_download}\n' "$1" 2> /dev/null || true; }   # url intervallo secondi
misura() {  # sorgente secondi: byte/s con le connessioni vere (kraken: CONN pezzi dello stesso file; altre: i primi file insieme)
  local s=$1 g t s2 p b bf m d alt n k=0 u
  rm -f "$ST/misura.$s".*
  while IFS=$'\t' read -r g t s2 p b bf m d alt; do
    [ "$s2" = "$s" ] && ! fatto "$d" "$m" || continue
    u=$(url_di "$s2" "$p"); n=$(connessioni "$s2" "$alt")
    if [ "$n" -gt 1 ]; then
      [ "$(prova_range "$u")" = 206 ] || n=1
      for ((k = 0; k < n; k++)); do misura_una "$u" "$(( b * k / n ))-$(( b * k / n + 8388607 ))" "$2" > "$ST/misura.$s.$k" & done
      break
    fi
    misura_una "$u" 0-8388607 "$2" > "$ST/misura.$s.$k" &
    k=$((k + 1)); [ "$k" -lt "$FILE_INSIEME" ] || break
  done < <(righe)
  wait
  cat "$ST/misura.$s".* 2> /dev/null | awk '{v += $1} END {printf "%.0f\n", v}'
}
# B1 (VM 30/10): le sorgenti scaricano insieme e il limite puo' essere la linea del PC (finito Kraken, GitHub e' passato
# da 1,1 a 7 MB/s) oppure ogni singola connessione (prova del 29/10: S3 0,17 MB/s per connessione). simula riceve per
# ogni sorgente "nome resto velocita_insieme velocita_da_sola" e calcola quando finisce: le sorgenti vanno alla velocita'
# misurata insieme; quando una finisce, la banda della linea (la somma insieme, o la piu' veloce da sola se e' di piu')
# si divide fra quelle rimaste in proporzione, ma nessuna supera la sua velocita' da sola. Stampa "totale nome:fine ..."
# in secondi, oppure "null" se una velocita' manca.
simula() {
  awk '$2 > 0 {n++; s[n] = $1; r[n] = $2; j[n] = $3; a[n] = ($4 > $3 ? $4 : $3)}
       END {
         if (n == 0) {print 0; exit}
         c = 0; for (i = 1; i <= n; i++) {if (j[i] <= 0) {print "null"; exit}; c += j[i]}
         for (i = 1; i <= n; i++) if (a[i] > c) c = a[i]
         t = 0; vivi = n
         while (vivi > 0) {
           sj = 0; for (i = 1; i <= n; i++) if (r[i] > 0) sj += j[i]
           dt = -1
           for (i = 1; i <= n; i++) if (r[i] > 0) {v[i] = j[i] * c / sj; if (v[i] > a[i]) v[i] = a[i]; x = r[i] / v[i]; if (dt < 0 || x < dt) dt = x}
           t += dt
           for (i = 1; i <= n; i++) if (r[i] > 0) {r[i] -= v[i] * dt; if (r[i] <= v[i] * 0.001) {r[i] = 0; vivi--; f[i] = t}}
         }
         printf "%.0f", t; for (i = 1; i <= n; i++) printf " %s:%.0f", s[i], f[i]; print ""
       }'
}
declare -A RESTA=() V0=() SOLA=() FINE_S=()   # per sorgente: byte da scaricare, velocita' misurata (insieme, da sola) in byte/s, fine simulata
while IFS=$'\t' read -r g t s p b bf m d alt; do
  if fatto "$d" "$m"; then continue; fi
  RESTA[$s]=$(( ${RESTA[$s]:-0} + b - $(sul_disco "$t" "$p" "$b" "$m" "$d") ))
done < <(righe)
rm -rf "$ST"; mkdir -p "$ST"
if [ "$DA_SCARICARE" -gt 0 ]; then
  FONTI=$(for s in "${!RESTA[@]}"; do if [ "${RESTA[$s]}" -gt 0 ]; then echo "$s"; fi; done | sort)
  if [ "$(echo "$FONTI" | wc -l)" -gt 1 ]; then   # ogni sorgente da sola per pochi secondi, poi tutte insieme
    for s in $FONTI; do SOLA[$s]=$(misura "$s" 6); done
    for s in $FONTI; do misura "$s" 10 > "$ST/v.$s" & done
    wait
    for s in $FONTI; do V0[$s]=$(cat "$ST/v.$s" 2> /dev/null || echo 0); done
  else
    for s in $FONTI; do V0[$s]=$(misura "$s" 15); SOLA[$s]=${V0[$s]}; done
  fi
  SIM=""; VTOT=0
  for s in $FONTI; do V0[$s]=${V0[$s]:-0}; SIM="$SIM$s ${RESTA[$s]} ${V0[$s]} ${SOLA[$s]:-0}"$'\n'; VTOT=$(( VTOT + V0[$s] )); done
  echo "$(date -Iseconds) velocita' (byte/s) sorgente resto insieme da_sola:"$'\n'"$SIM" >> "$LOG"
  read -r TEMPO FINE <<< "$(printf '%s' "$SIM" | simula)"
  for x in $FINE; do FINE_S[${x%%:*}]=${x##*:}; done
  PARTI=""
  if [ "$TEMPO" != null ]; then
    for s in $FONTI; do PARTI="$PARTI${PARTI:+, }$(etichetta "$s") $(mb_s "${V0[$s]}") MB/s ($(durata "${FINE_S[$s]}"))"; done
  fi
  if [ "$TEMPO" != null ]; then
    ETA=$TEMPO; evento avanzamento 2 "$(T 'Velocità misurata: %s. Tempo stimato per scaricare tutto: circa %s.' "$PARTI" "$(durata "$TEMPO")")"
  else
    evento avviso 2 "$(T 'Non riesco a misurare la velocità della rete: proseguo senza stima del tempo.')" RETE_NON_MISURATA
  fi
fi
if [ "$STIMA" = 1 ]; then
  GB1() { awk -v b="$1" -v g="$GIB" 'BEGIN {printf "%.1f", b/g}'; }
  vel=null; tempo=null; sorgenti=""
  if [ "$DA_SCARICARE" = 0 ]; then tempo=0
  elif [ "$TEMPO" != null ]; then vel=$(awk -v v="$VTOT" 'BEGIN {printf "%.1f", v/1e6}'); tempo=$TEMPO; fi
  for s in $(printf '%s\n' "${!RESTA[@]}" | sort); do
    v=null; ts=null; vs=null
    if [ "${V0[$s]:-0}" -gt 0 ]; then v=$(awk -v v="${V0[$s]}" 'BEGIN {printf "%.1f", v/1e6}'); fi
    if [ "${SOLA[$s]:-0}" -gt 0 ]; then vs=$(awk -v v="${SOLA[$s]}" 'BEGIN {printf "%.1f", v/1e6}'); fi
    if [ "$tempo" != null ]; then ts=${FINE_S[$s]:-0}; fi
    sorgenti="$sorgenti${sorgenti:+,}{\"sorgente\":\"$s\",\"da_scaricare_gb\":$(GB1 "${RESTA[$s]}"),\"da_scaricare_byte\":${RESTA[$s]},\"velocita_mb_s\":$v,\"velocita_da_sola_mb_s\":$vs,\"tempo_stimato_s\":$ts}"
  done
  RISULTATO=$(printf '{"da_scaricare_gb":%s,"spazio_necessario_gb":%s,"spazio_libero_gb":%s,"velocita_mb_s":%s,"tempo_stimato_s":%s,"spazio_necessario_byte":%s,"spazio_libero_byte":%s,"da_scaricare_byte":%s,"sorgenti":[%s]}' \
    "$(GB1 "$DA_SCARICARE")" "$(GB1 "$SERVONO")" "$(GB1 "$LIBERI")" "$vel" "$tempo" "$SERVONO" "$LIBERI" "$DA_SCARICARE" "$sorgenti")
  PASSO=fine; evento fine null "$(T 'Stima pronta: non ho scaricato nulla.')"; exit 0
fi
if [ "$SI" != 1 ]; then
  read -r -p "[PMN] Procedo con l'installazione? (s/n) " r || r=n
  [ "$r" = s ] || [ "$r" = S ] || { PASSO=fine; ESITO=annullata; evento fine null "$(T 'Installazione annullata: non ho scaricato nulla.')"; exit 3; }
fi

# ===================== 2. programmi =====================
if [ "$SOLO_DB" = 0 ]; then
PASSO=programmi; FATTO=0; TOTALE=${#ENVS[@]}; ETA=null
MM=$PMN_HOME/bin/micromamba
if ! { [ -x "$MM" ] && echo "$MICROMAMBA_SHA256  $MM" | sha256sum -c --status; }; then
  evento avanzamento 5 "$(T 'Scarico il gestore dei programmi (micromamba %s)...' "$MICROMAMBA_VER")"
  curl -fsSL --retry 10 --retry-delay 5 -o "$MM.parziale" \
    "https://github.com/mamba-org/micromamba-releases/releases/download/$MICROMAMBA_VER/micromamba-linux-64" >> "$LOG" 2>&1 \
    || fallisci DOWNLOAD_FALLITO "$(T 'Non riesco a scaricare micromamba.')" "$(T 'Controlla la connessione e rilancia.')"
  echo "$MICROMAMBA_SHA256  $MM.parziale" | sha256sum -c --status \
    || { rm -f "$MM.parziale"; fallisci DB_ROVINATO "$(T 'Il file di micromamba scaricato è rovinato.')" "$(T "Rilancia l'installazione.")"; }
  chmod +x "$MM.parziale"; mv "$MM.parziale" "$MM"
fi
i=0
for e in "${ENVS[@]}"; do
  i=$((i + 1))
  if uguale_al_blocco "$e"; then continue; fi
  FATTO=$((i - 1)); evento avanzamento $((5 + i * 2)) "$(T 'Installo i programmi: ambiente %s di %s (%s)...' "$i" "${#ENVS[@]}" "$e")"
  rm -rf "${MAMBA_ROOT_PREFIX:?}/envs/$e"
  "$MM" create -y -q -n "$e" -f "$PMN_ROOT/installer/lock/$e.txt" >> "$LOG" 2>&1 \
    || fallisci DOWNLOAD_FALLITO "$(T "Non riesco a installare l'ambiente %s." "$e")" "$(T 'Controlla la connessione e rilancia.')"
  uguale_al_blocco "$e" || fallisci DB_ROVINATO "$(T "L'ambiente %s non corrisponde alle versioni previste." "$e")" "$(T "Rilancia l'installazione.")"
done
"$MM" clean -a -y >> "$LOG" 2>&1 || true   # la cache dei pacchetti non serve piu'
FATTO=${#ENVS[@]}; evento avanzamento 22 "$(T 'Programmi installati (%s ambienti, MetaPhlAn %s).' "${#ENVS[@]}" "$(ls "$MAMBA_ROOT_PREFIX/envs/pmn_metaphlan/conda-meta" | sed -n 's/^metaphlan-\([0-9.]*\)-.*/\1/p')")"
fi

# ===================== 3. database =====================
# Una coda per sorgente, tutte insieme (R2): kraken un file alla volta a CONN connessioni, le altre FILE_INSIEME file
# alla volta. Le code annunciano cosa iniziano; il ciclo principale conta i byte sul disco ogni OGNI_S secondi e manda
# l'avanzamento con velocita' (media degli ultimi ~60 s) e tempo che manca per sorgente (R4).
PASSO=database; FATTO=0; TOTALE=$(righe | wc -l); ETA=null
TOT=$(righe | awk -F'\t' '{s+=$5} END {printf "%.0f", s}')
echo "22 null 0" > "$ST/stato"
# A6: i pezzi gia' letti e cancellati da un giro interrotto si riscaricano (il lettore riparte dal primo): il loro conto
# non vale piu'. flusso() lo rimette a 0 quando parte; tolto anche qui, cosi' il primo avanzamento non li conta.
find "$PMN_HOME/tmp" "$PMN_HOME/db" -name '*.consumati' -type f -delete 2> /dev/null || true
annuncia() {  # messaggio: avanzamento da una coda, con percentuale, tempo e file fatti dell'ultimo conto
  local p e f; read -r p e f < "$ST/stato" || { p=22; e=null; f=0; }
  FATTO=$f; ETA=$e; AV_EXTRA=""; evento avanzamento "$p" "$1"
}
scarica() {  # url file byte: riprende i pezzi gia' scaricati; ritenta se la rete cade (una connessione, come in v1.0)
  local n=0 have s
  while :; do
    have=$(dim "$2")
    [ "$have" -ge "$3" ] && return 0
    curl -fsSL -C - --connect-timeout 30 --speed-limit 1024 --speed-time 120 -o "$2" "$1" >> "$LOG" 2>&1 || true
    have=$(dim "$2")
    [ "$have" -ge "$3" ] && return 0
    n=$((n + 1)); [ "$n" -lt 30 ] || return 1
    s=$(attesa "$n"); evento avviso "$(cut -d' ' -f1 "$ST/stato")" "$(T 'La connessione si è interrotta: riprovo fra %s secondi (tentativo %s di 30).' "$s" "$n")" RETE_INTERROTTA
    sleep "$s"
  done
}
attesa() { local s=$(( 5 << ($1 < 5 ? $1 - 1 : 4) )); [ "$s" -le 60 ] || s=60; echo "$s"; }   # 5, 10, 20, 40, 60, 60... s
prepara_pezzi() {  # base byte connessioni url: divide il file in pezzi una volta sola ($base.pezzi resta per la ripresa)
  local base=$1 b=$2 l=0 x c="" n=0 dp
  if [ -s "$base.pezzi" ] && [ "$(tail -n 1 "$base.pezzi" | cut -d' ' -f2)" = $((b - 1)) ]; then return 0; fi
  rm -f "$base".pezzo.* "$base.pezzi" "$base.senza_range"
  while [ "$n" -lt 3 ]; do c=$(prova_range "$4"); [ "$c" = 000 ] || break; n=$((n + 1)); sleep "$(attesa "$n")"; done
  case "$c" in
    206) ;;
    200) echo "$(date -Iseconds) $4: il server non da' i pezzi (Range): una connessione" >> "$LOG"   # come v1.0
         if [ -e "$base.parziale" ]; then mv "$base.parziale" "$base.pezzo.0"; fi
         touch "$base.senza_range"; echo "0 $((b - 1))" > "$base.pezzi"; return 0 ;;
    *) echo "$(date -Iseconds) $4: codice HTTP $c" >> "$LOG"; return 1 ;;
  esac
  if [ -s "$base.parziale" ]; then   # lo scarico di una v1.0 interrotta diventa il primo pezzo: niente buttato
    l=$(dim "$base.parziale")
    if [ "$l" -le "$b" ]; then mv "$base.parziale" "$base.pezzo.0"; else rm -f "$base.parziale"; l=0; fi
  fi
  dp=$(dim_pezzo $((b - l)) "$3")
  { if [ "$l" -gt 0 ]; then echo "0 $((l - 1))"; fi
    for ((x = l; x < b; x += dp)); do echo "$x $(( x + dp < b ? x + dp - 1 : b - 1 ))"; done; } > "$base.pezzi.t"
  mv "$base.pezzi.t" "$base.pezzi"
}
scarica_pezzo() {  # base i inizio fine url [url_alternativo]: riprende dal byte dove era arrivato
  local f=$1.pezzo.$2 a=$3 z=$4 want=$(( $4 - $3 + 1 )) n=0 have u s urls=("$5")
  if [ -n "${6:-}" ]; then urls+=("$6"); fi
  while :; do
    have=$(dim "$f")
    [ "$have" -eq "$want" ] && return 0
    if [ "$have" -gt "$want" ]; then rm -f "$f"; have=0; fi
    u=${urls[$(( ($2 + n) % ${#urls[@]} ))]}   # D166: i pezzi (e i nuovi tentativi) si dividono fra le sorgenti
    if [ -e "$1.senza_range" ]; then
      curl -fsSL --connect-timeout 30 --speed-limit 1024 --speed-time 120 -o "$f" "$u" 2>> "$LOG" || true
    else
      curl -fsSL --connect-timeout 30 --speed-limit 1024 --speed-time 120 -r "$((a + have))-$z" "$u" >> "$f" 2>> "$LOG" || true
    fi
    [ "$(dim "$f")" -eq "$want" ] && return 0
    n=$((n + 1)); [ "$n" -lt 30 ] || return 1
    s=$(attesa "$n"); evento avviso "$(cut -d' ' -f1 "$ST/stato")" "$(T 'La connessione si è interrotta: riprovo fra %s secondi (tentativo %s di 30).' "$s" "$n")" RETE_INTERROTTA
    sleep "$s"
  done
}
lavoratori() {  # base connessioni url [url_alternativo]: il processo w prende i pezzi w, w+n, w+2n...
  local base=$1 n=$2 w
  [ -e "$base.senza_range" ] && n=1
  for ((w = 0; w < n; w++)); do
    ( i=0
      while read -r a z; do
        if [ $((i % n)) = "$w" ]; then
          # in risparmio un pezzo parte solo se il lettore e' a meno di 2n pezzi: pochi pezzi sul disco
          while [ "$RISPARMIO" = 1 ] && [ "$i" -ge $(( $(leggi "$base.letti") + 2 * n )) ]; do sleep 0.5; done
          scarica_pezzo "$base" "$i" "$a" "$z" "$3" "${4:-}" || { touch "$base.fallito"; exit 1; }
        fi
        i=$((i + 1))
      done < "$base.pezzi" ) &
  done
  wait
}
leggi_pezzi() {  # base: i pezzi in ordine su stdout, appena completi; in risparmio ognuno si cancella appena letto
  local base=$1 i=0 a z f
  while read -r a z; do
    f=$base.pezzo.$i
    until [ "$(dim "$f")" = $((z - a + 1)) ]; do
      [ ! -e "$base.fallito" ] || return 1
      sleep 0.5
    done
    cat "$f"
    if [ "$RISPARMIO" = 1 ]; then rm -f "$f"; scrivi "$base.consumati" $(( $(leggi "$base.consumati") + z - a + 1 )); fi
    i=$((i + 1)); scrivi "$base.letti" "$i"
  done < "$base.pezzi"
}
flusso() {  # base byte connessioni url alt comando...: scarica a pezzi e passa il file al comando mentre arriva,
  # con l'MD5 calcolato nello stesso passaggio (in $base.md5). Torna 0 se il comando ha letto tutto senza errori.
  local base=$1 b=$2 c=$3 u=$4 alt=$5 ok=0 pl pm; shift 5
  rm -f "$base.fallito" "$base.md5"; scrivi "$base.letti" 0; scrivi "$base.consumati" 0
  lavoratori "$base" "$c" "$u" "$alt" & pl=$!
  rm -f "$base.fifo"; mkfifo "$base.fifo"
  md5sum < "$base.fifo" | cut -d' ' -f1 > "$base.md5" & pm=$!
  if leggi_pezzi "$base" | tee "$base.fifo" | "$@"; then ok=1; fi
  wait "$pm" || true; rm -f "$base.fifo"
  [ ! -e "$base.fallito" ] || return 2                                # scarico fallito
  [ "$(leggi "$base.letti")" = "$(wc -l < "$base.pezzi")" ] || return 3   # il comando si e' fermato prima della fine
  wait "$pl" || true
  [ "$ok" = 1 ] || return 4
}
via_pezzi() { rm -f "$1".pezzo.* "$1".pezzi "$1".senza_range "$1".letti "$1".consumati "$1".md5 "$1".fallito; }
uno() {  # gruppo tipo sorgente percorso byte md5 destinazione url_alternativo: scarica e controlla una riga
  # R18: un MD5 sbagliato si riscarica da solo una volta; alla seconda si ferma e dice cosa fare
  local g=$1 t=$2 s=$3 p=$4 b=$5 m=$6 d=$7 alt=$8 url f base dir c r prova nome
  url=$(url_di "$s" "$p"); c=$(connessioni "$s" "$alt")
  local rifai; rifai=$(T "Ho già riscaricato una volta. Riapri l'installazione più tardi; se si ripete, manda a noi il file %s." "$LOG")
  if [ "$t" = file ]; then
    f=$PMN_HOME/db/$d; nome=$(basename "$d"); mkdir -p "$(dirname "$f")"
    for prova in 1 2; do
      annuncia "$(T 'Scarico %s: %s (%s GB)...' "$g" "$nome" "$(num "$b" "$GIB" 2)")"
      if [ "$c" = 1 ]; then
        scarica "$url" "$f.parziale" "$b" || fallisci DOWNLOAD_FALLITO "$(T 'Non riesco a scaricare %s.' "$nome")" "$(T 'Controlla la connessione e rilancia.')"
        [ "$(md5sum < "$f.parziale" | cut -d' ' -f1)" = "$m" ] && break
        rm -f "$f.parziale"
      else
        prepara_pezzi "$f" "$b" "$c" "$url" || fallisci DOWNLOAD_FALLITO "$(T 'Non riesco a scaricare %s.' "$nome")" "$(T 'Controlla la connessione e rilancia.')"
        r=0; flusso "$f" "$b" "$c" "$url" "$alt" dd of="$f.parziale" bs=1M status=none || r=$?
        [ "$r" != 2 ] || fallisci DOWNLOAD_FALLITO "$(T 'Non riesco a scaricare %s.' "$nome")" "$(T 'Controlla la connessione e rilancia.')"
        [ "$r" = 0 ] || fallisci DB_ROVINATO "$(T 'Non riesco a estrarre %s.' "$nome")" "$(T 'Controlla lo spazio libero e rilancia.')"
        if [ "$(cat "$f.md5")" = "$m" ]; then via_pezzi "$f"; break; fi
        rm -f "$f.parziale"; via_pezzi "$f"
      fi
      echo "$(date -Iseconds) $nome: MD5 diverso (tentativo $prova)" >> "$LOG"
      [ "$prova" = 1 ] || fallisci DB_ROVINATO "$(T 'Il file %s scaricato è rovinato (MD5 diverso).' "$nome")" "$rifai"
    done
    mv "$f.parziale" "$f"
  else
    base=$PMN_HOME/tmp/$(basename "$p"); dir=$PMN_HOME/db/$d; nome=$(basename "$p")
    for prova in 1 2; do
      annuncia "$(T 'Scarico %s (%s GB, archivio da estrarre)...' "$g" "$(num "$b" "$GIB" 1)")"
      prepara_pezzi "$base" "$b" "$c" "$url" || fallisci DOWNLOAD_FALLITO "$(T 'Non riesco a scaricare %s.' "$nome")" "$(T 'Controlla la connessione e rilancia.')"
      rm -rf "$dir"; mkdir -p "$dir"
      r=0; flusso "$base" "$b" "$c" "$url" "$alt" tar -xz -C "$dir" || r=$?
      [ "$r" != 2 ] || fallisci DOWNLOAD_FALLITO "$(T 'Non riesco a scaricare %s.' "$nome")" "$(T 'Controlla la connessione e rilancia.')"
      if [ "$r" = 3 ] || [ "$(cat "$base.md5")" = "$m" ]; then break; fi
      rm -rf "$dir"; via_pezzi "$base"   # MD5 sbagliato: via l'estratto e i pezzi, si riscarica
      echo "$(date -Iseconds) $nome: MD5 diverso (tentativo $prova)" >> "$LOG"
      [ "$prova" = 1 ] || fallisci DB_ROVINATO "$(T "L'archivio %s scaricato è rovinato (MD5 diverso)." "$nome")" "$rifai"
    done
    [ "$r" = 0 ] || fallisci DB_ROVINATO "$(T 'Non riesco a estrarre %s.' "$nome")" "$(T 'Controlla lo spazio libero e rilancia.')"
    annuncia "$(T 'Estraggo e controllo %s...' "$g")"
    (cd "$dir" && md5sum -c --quiet "$PMN_ROOT/installer/md5/$g.md5") >> "$LOG" 2>&1 \
      || fallisci DB_ROVINATO "$(T "I file di %s non hanno l'MD5 atteso." "$g")" "$(T "Rilancia l'installazione.")"
    via_pezzi "$base"
  fi
  echo "$m" > "$(segnalino "$d")"
}
coda() {  # sorgente: le righe di una sorgente, nell'ordine del catalogo
  local s=$1 max=$FILE_INSIEME n=0 g t s2 p b bf m d alt
  [ "$s" != kraken ] || max=1
  while IFS=$'\t' read -r g t s2 p b bf m d alt; do
    [ "$s2" = "$s" ] && ! fatto "$d" "$m" || continue
    uno "$g" "$t" "$s2" "$p" "$b" "$m" "$d" "$alt" &
    n=$((n + 1)); if [ "$n" -ge "$max" ]; then wait -n || exit 1; n=$((n - 1)); fi
  done < <(righe)
  while [ "$n" -gt 0 ]; do wait -n || exit 1; n=$((n - 1)); done
}
presenti() {  # tipo percorso byte md5 destinazione: byte gia' sul disco per questa riga
  local base c
  if fatto "$5" "$4"; then echo "$3"; return; fi
  if [ "$1" = tar ]; then base=$PMN_HOME/tmp/$(basename "$2"); else base=$PMN_HOME/db/$5; fi
  c=$(leggi "$base.consumati")
  { stat -c %s -- "$base.parziale" "$base".pezzo.* 2> /dev/null || true; } | awk -v c="$c" -v b="$3" '{s += $1} END {s += c; printf "%.0f\n", (s > b ? b : s)}'
}
declare -A STORIA=(); PMAX=22
conta() {  # ogni OGNI_S secondi: byte per sorgente sul disco, velocita' (media degli ultimi ~60 s), tempo che manca
  local adesso fatti=0 nf=0 g t s p b bf m d alt x v r eta lenta parti="" sorg="" vtot=0 sim="" fine
  declare -A F=() B=()
  adesso=$(date +%s)
  while IFS=$'\t' read -r g t s p b bf m d alt; do
    x=$(presenti "$t" "$p" "$b" "$m" "$d"); F[$s]=$(( ${F[$s]:-0} + x )); B[$s]=$(( ${B[$s]:-0} + b ))
    fatti=$(( fatti + x )); if fatto "$d" "$m"; then nf=$((nf + 1)); fi
  done < <(righe)
  for s in $(printf '%s\n' "${!B[@]}" | sort); do
    STORIA[$s]=$(echo "${STORIA[$s]:-} $adesso:${F[$s]}" | awk '{n = NF > 5 ? NF - 4 : 1; for (i = n; i <= NF; i++) printf "%s%s", $i, (i < NF ? " " : "")}')
    v=$(echo "${STORIA[$s]}" | awk '{split($1, a, ":"); split($NF, z, ":"); v = z[1] > a[1] ? (z[2] - a[2]) / (z[1] - a[1]) : 0; printf "%.0f", (v > 0 ? v : 0)}')
    r=$(( B[$s] - F[$s] ))
    [ "$r" -gt 0 ] || v=0
    vtot=$(( vtot + v ))
    sorg="$sorg${sorg:+,}{\"sorgente\":\"$s\",\"byte_fatti\":${F[$s]},\"byte_totali\":${B[$s]},\"velocita_mb_s\":$(awk -v v="$v" 'BEGIN {printf "%.2f", v/1e6}')}"
    if [ "$r" -gt 0 ]; then
      parti="$parti${parti:+, }$(etichetta "$s") $(mb_s "$v") MB/s"
      [ "$v" -gt 0 ] || v=${V0[$s]:-0}   # non ancora partita o ferma: la velocita' misurata all'inizio
      sim="$sim$s $r $v ${SOLA[$s]:-0}"$'\n'
    fi
  done
  # B1: stesso calcolo della stima iniziale (simula), con le velocita' vere degli ultimi ~60 s
  read -r eta fine <<< "$(printf '%s' "$sim" | simula)"
  lenta=$(printf '%s\n' $fine | awk -F: '$2 > m {m = $2; s = $1} END {print (s == "" ? "null" : "\"" s "\"")}')
  P=$(awk -v f="$fatti" -v t="$TOT" 'BEGIN {printf "%d", 22 + 70 * (t > 0 ? f / t : 1)}')
  [ "$P" -ge "$PMAX" ] || P=$PMAX; PMAX=$P   # la barra non torna indietro (un MD5 sbagliato toglie byte gia' contati)
  echo "$P $eta $nf" > "$ST/stato.t" && mv -f "$ST/stato.t" "$ST/stato"
  FATTO=$nf; ETA=$eta
  AV_EXTRA=",\"byte_fatti\":$fatti,\"byte_totali\":$TOT,\"velocita_mb_s\":$(awk -v v="$vtot" 'BEGIN {printf "%.2f", v/1e6}'),\"sorgente\":$lenta,\"sorgenti\":[$sorg]"
  if [ -n "$parti" ]; then evento avanzamento "$P" "$(T 'Scarico i database: %s di %s GB (%s).' "$(num "$fatti" "$GIB" 1)" "$(num "$TOT" "$GIB" 1)" "$parti")"; fi
  AV_EXTRA=""
}
if [ "$RISPARMIO" = 1 ] && [ "$ARCHIVIO" -gt 0 ]; then
  echo "$(date -Iseconds) risparmio: liberi $LIBERI, servono $SERVONO (con l'archivio intero $(( SERVONO - MARGINE + ARCHIVIO )))" >> "$LOG"
  annuncia "$(T "Spazio stretto: estraggo gli archivi mentre arrivano e cancello ogni pezzo appena letto. Se l'installazione si interrompe, l'archivio in corso riparte da capo.")"
fi
CODE=()
for s in $(righe | cut -f3 | awk '!visto[$0]++'); do coda "$s" & CODE+=($!); done
prossimo=0
while :; do
  if compgen -G "$ST/errore.*" > /dev/null; then break; fi
  adesso=$(date +%s)
  if [ "$adesso" -ge "$prossimo" ]; then conta; prossimo=$(( adesso + OGNI_S )); fi
  [ -n "$(jobs -rp)" ] || break
  sleep 1
done
e=$(ls "$ST"/errore.* 2> /dev/null | head -n 1) || true
if [ -n "$e" ]; then IFS=$'\t' read -r c msg cf < "$e"; fallisci "$c" "$msg" "$cf"; fi
for p in "${CODE[@]}"; do
  wait "$p" || fallisci DOWNLOAD_FALLITO "$(T 'Non riesco a scaricare %s.' "$(basename "$CATALOGO")")" "$(T 'Manda a noi il file %s.' "$LOG")"
done
conta
FATTO=$TOTALE; ETA=null; evento avanzamento 92 "$(T 'Database scaricati e controllati.')"
if [ "$SOLO_DB" = 1 ]; then
  gruppi=$(righe | cut -f1 | awk '!visto[$0]++ {printf "%s\"%s\"", (n++ ? "," : ""), $0}')
  RISULTATO="{\"database\":[$gruppi]}"; PASSO=fine; evento fine 100 "$(T 'Database scaricati e controllati.')"; exit 0
fi

# ===================== 4. impostazioni =====================
cat > "$PMN_HOME/installazione.env" <<EOF
# scritto da installer/installa_motore.sh il $(date -Iseconds)
PMN_ROOT=$PMN_ROOT
PMN_ENVS=$MAMBA_ROOT_PREFIX/envs
PMN_MPA_DB=$PMN_HOME/db/metaphlan
PMN_FETTE=$PMN_HOME/db/fette
PMN_KRAKEN_COMPLETO=$PMN_HOME/db/kraken/k2_pluspf_20260626
PMN_KRAKEN_RAPIDO=$PMN_HOME/db/kraken/k2_pluspf_08gb_20260626
PMN_OSPITE=$PMN_HOME/db/ospite
PMN_PROVA=$PMN_HOME/db/prova
PMN_TMP=$PMN_HOME/tmp
EOF
chmod +x "$PMN_ROOT/motore/pmn-motore"
ln -sfn "$PMN_ROOT/motore/pmn-motore" "$PMN_HOME/bin/pmn-motore"   # il comando unico (docs/contratto_motore.md §1)

# ===================== 5. prova finale =====================
PASSO=verifica; FATTO=0; TOTALE=1; ETA=null
evento avanzamento 93 "$(T 'Prova finale su un piccolo campione (alcuni minuti)...')"
if PMN_HOME=$PMN_HOME bash "$PMN_ROOT/installer/verifica_motore.sh" >> "$LOG" 2>&1; then
  gruppi=$(righe | cut -f1 | awk '!visto[$0]++ {printf "%s\"%s\"", (n++ ? "," : ""), $0}')
  RISULTATO="{\"programmi\":${#ENVS[@]},\"database\":[$gruppi],\"verifica\":\"verde\"}"
  PASSO=fine; evento fine 100 "$(T 'VERDE: il motore è installato e funziona.')"
else
  fallisci VERIFICA_ROSSA "$(T 'ROSSO: la prova finale non ha dato il risultato atteso.')" "$(T 'Manda a noi il file %s.' "$LOG")"
fi
