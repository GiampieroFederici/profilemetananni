#!/usr/bin/env bash
# installer/installa_motore.sh - installa il motore di profilemetananni su Linux o WSL2, senza permessi di amministratore.
# Un solo comando; se si interrompe (rete, spegnimento) basta rilanciarlo: riprende da dove era rimasto (D027, D034).
# Programmi: micromamba + ambienti dal file di blocco (installer/lock/). Database: installer/catalogo.tsv, con MD5.
#
# Uso: bash installer/installa_motore.sh [--si] [--stima] [--json] [--catalogo FILE] [--specchio URL]
#   --si        non chiede conferma (la chiede l'interfaccia, D034)
#   --stima     dice peso, spazio e tempo stimato e si ferma senza scaricare (per la domanda dell'interfaccia)
#   --json      messaggi come eventi JSON, uno per riga (docs/contratto_motore.md)
#   --catalogo  altro catalogo (prova)
#   --specchio  tutte le sorgenti da un solo indirizzo, es. http://127.0.0.1:8765 (prova con lo specchio locale, D038)
#   --lingua    it (predefinita) o en: lingua dei messaggi per la persona (anche con PMN_LINGUA, come motore/lingua.py)
# Variabili: PMN_HOME (predefinita ~/.pmn), PMN_URL_PACCHETTI (dove sono pubblicati i pacchetti pmn, D035).
set -euo pipefail

PMN_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PMN_HOME=${PMN_HOME:-$HOME/.pmn}
CATALOGO=$PMN_ROOT/installer/catalogo.tsv
SPECCHIO=""; SI=0; STIMA=0; JSON=0; LINGUA=${PMN_LINGUA:-it}
MICROMAMBA_VER=2.9.0-0
MICROMAMBA_SHA256=366cd9cd8be14df1ab8ed50352a82111082a36686b2d389fdb79a92c3fafb3e3
URL_KRAKEN=https://genome-idx.s3.amazonaws.com/kraken
URL_PMN=${PMN_URL_PACCHETTI:-}
ENVS=(pmn_download pmn_qc pmn_trim pmn_hostfilter pmn_metaphlan pmn_kraken pmn_stats_r pmn_reports_py)
GB_PROGRAMMI=16   # ambienti installati + cache dei pacchetti durante l'installazione (misurati: ~11 GB + margine)

ARGOMENTI=("$@")
while [ $# -gt 0 ]; do
  case "$1" in
    --si) SI=1; shift ;;
    --stima) STIMA=1; shift ;;
    --json) JSON=1; shift ;;
    --catalogo) CATALOGO=$2; shift 2 ;;
    --specchio) SPECCHIO=${2%/}; shift 2 ;;
    --lingua) LINGUA=$2; shift 2 ;;
    *) echo "Opzione sconosciuta: $1" >&2; exit 1 ;;
  esac
done
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
  ["I pacchetti di profilemetananni non sono ancora pubblicati."]="The profilemetananni packages are not published yet."
  ["Per ora si installa solo in prova, con lo specchio locale."]="For now it installs only in test mode, with the local mirror."
  ["Da scaricare: circa %s GB. Spazio necessario: %s GB. Spazio libero: %s GB."]="To download: about %s GB. Space needed: %s GB. Free space: %s GB."
  ["Lo spazio libero non basta: servono %s GB, ce ne sono %s."]="The free space is not enough: %s GB are needed, there are %s."
  ["Libera spazio sul disco e rilancia."]="Free some space on the disk and run it again."
  ["1 minuto"]="1 minute"
  ["%s minuti"]="%s minutes"
  ["%s ore"]="%s hours"
  ["Velocità misurata: %s MB/s. Tempo stimato per scaricare tutto: circa %s."]="Measured speed: %s MB/s. Estimated time to download everything: about %s."
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
  ["La connessione si è interrotta: riprovo fra 20 secondi (tentativo %s di 30)."]="The connection was interrupted: I try again in 20 seconds (attempt %s of 30)."
  ["Scarico %s: %s (%s GB)..."]="Downloading %s: %s (%s GB)..."
  ["Non riesco a scaricare %s."]="I cannot download %s."
  ["Il file %s scaricato è rovinato (MD5 diverso)."]="The downloaded file %s is damaged (different MD5)."
  ["Rilancia: lo riscarico da capo."]="Run it again: I download it again from the start."
  ["Scarico %s (%s GB, archivio da estrarre)..."]="Downloading %s (%s GB, archive to extract)..."
  ["L'archivio %s scaricato è rovinato (MD5 diverso)."]="The downloaded archive %s is damaged (different MD5)."
  ["Estraggo e controllo %s..."]="Extracting and checking %s..."
  ["Non riesco a estrarre %s."]="I cannot extract %s."
  ["Controlla lo spazio libero e rilancia."]="Check the free space and run it again."
  ["I file di %s non hanno l'MD5 atteso."]="The files of %s do not have the expected MD5."
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
# avanzamento usa FATTO e TOTALE (pezzi del passo) ed ETA (secondi, o null); fine usa ESITO e RISULTATO (oggetto JSON).
PASSO=controllo; FATTO=0; TOTALE=1; ETA=null; ESITO=ok; RISULTATO='{}'
CORSA=$(date +%Y-%m-%dT%H-%M-%S)
js() { local t=${1//\\/\\\\}; printf '%s' "${t//\"/\\\"}"; }   # testo dentro una stringa JSON
mb_s() { num "$1" 1e6 1; }   # B2 (P5): byte/s -> "57,2" (in inglese "57.2")
evento() {  # tipo percentuale messaggio [codice] [cosa_fare]
  if [ "$JSON" = 1 ]; then
    local extra=""
    case "$1" in
      inizio) extra=",\"corsa\":\"$CORSA\",\"log\":\"$(js "$LOG")\"" ;;
      avanzamento) extra=",\"campione\":null,\"fatto\":$FATTO,\"totale\":$TOTALE,\"eta_s\":$ETA" ;;
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
  evento errore null "$2" "$1" "$3"
  RISULTATO="{\"codice\":\"$1\",\"passo\":\"$PASSO\"}"; PASSO=fine; ESITO=errore   # contratto v0.3: {"codice", "passo"}
  evento fine null "$(T 'Installazione non completata. Rilanciala quando hai risolto: riprende da qui.')"
  exit 2
}
trap 'PASSO=fine; ESITO=annullata; evento fine null "$(T "Installazione interrotta. Rilancia lo stesso comando: riprende da dove era rimasta.")"; exit 3' INT TERM

mkdir -p "$PMN_HOME"/{bin,db,stato,tmp,log}
# P41: corsa e gruppo per annulla (pmn_motore.py lo legge), solo se il gruppo è nostro; tolto alla fine
if [ "$JSON" = 1 ] && [ "$STIMA" = 0 ] && [ "$(cut -d' ' -f5 /proc/$$/stat 2> /dev/null)" = "$$" ]; then
  printf '{"corsa":"%s","pid":%s,"pgid":%s}\n' "$CORSA" "$$" "$$" > "$PMN_HOME/stato/installa.lock"
  trap 'rm -f "$PMN_HOME/stato/installa.lock"' EXIT
fi
export TMPDIR=$PMN_HOME/tmp   # /tmp di WSL sta in RAM: download ed estrazioni su disco
LOG=$PMN_HOME/log/installazione_$(date +%Y%m%d_%H%M%S).log
evento inizio 0 "$(T 'Installazione del motore di profilemetananni. Dettagli tecnici in %s' "$LOG")"

# ===================== 1. controlli =====================
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] \
  || fallisci SISTEMA_NON_ADATTO "$(T 'Serve Linux a 64 bit (anche dentro WSL2 su Windows).')" "$(T 'Usa un PC con Windows 10/11 o Linux a 64 bit.')"
for c in curl tar gzip md5sum sha256sum awk df; do
  command -v "$c" > /dev/null || fallisci PROGRAMMA_MANCANTE "$(T "Manca il programma di sistema '%s'." "$c")" "$(T 'Su Ubuntu: sudo apt install %s' "$c")"
done
[ -s "$CATALOGO" ] || fallisci CONFIG_NON_VALIDA "$(T 'Non trovo il catalogo dei database (%s).' "$CATALOGO")" "$(T 'Riscarica profilemetananni.')"

url_di() {  # sorgente percorso
  if [ -n "$SPECCHIO" ]; then printf '%s/%s/%s' "$SPECCHIO" "$1" "$2"
  elif [ "$1" = kraken ]; then printf '%s/%s' "$URL_KRAKEN" "$2"
  else printf '%s/%s' "$URL_PMN" "$2"
  fi
}
if [ -z "$SPECCHIO" ] && [ -z "$URL_PMN" ] && tail -n +2 "$CATALOGO" | cut -f3 | grep -qx pmn; then
  fallisci DOWNLOAD_FALLITO "$(T 'I pacchetti di profilemetananni non sono ancora pubblicati.')" "$(T 'Per ora si installa solo in prova, con lo specchio locale.')"
fi
# pezzo gia' scaricato e verificato: il segnalino contiene l'MD5 della riga e il file (o la cartella) c'e' ancora
segnalino() { printf '%s/stato/%s.ok' "$PMN_HOME" "${1//\//__}"; }   # destinazione
fatto() { [ "$(cat "$(segnalino "$1")" 2>/dev/null)" = "$2" ] && [ -e "$PMN_HOME/db/$1" ]; }   # destinazione md5

# spazio: cio' che manca + il piu' grande archivio da estrarre (serve insieme ai suoi file per un momento)
read -r DA_SCARICARE SERVONO < <(
  tail -n +2 "$CATALOGO" | while IFS=$'\t' read -r g t s p b bf m d; do
    if fatto "$d" "$m"; then continue; fi
    echo "$t $b $bf"
  done | awk '{s+=$2; f+=$3; if ($1=="tar" && $2>a) a=$2} END {printf "%d %d\n", s, f+a}')
GIB=1073741824   # 22/10: GB mostrati come Esplora file e installa_pmn.ps1 (1.024^3 byte)
GB() { awk -v b="$1" -v g="$GIB" 'BEGIN {printf "%.0f", b/g}'; }
LIBERI=$(( $(df -Pk "$PMN_HOME" | awk 'NR==2 {print $4}') * 1024 ))
export MAMBA_ROOT_PREFIX=$PMN_HOME/mamba
uguale_al_blocco() {  # env: i pacchetti installati sono esattamente quelli del file di blocco?
  local d=$MAMBA_ROOT_PREFIX/envs/$1
  [ -d "$d/conda-meta" ] || return 1
  diff -q <(grep '^https://' "$PMN_ROOT/installer/lock/$1.txt" | sed 's|.*/||; s|#.*||; s|\.conda$||; s|\.tar\.bz2$||' | sort) \
          <(cd "$d/conda-meta" && ls -- *.json | sed 's|\.json$||' | sort) > /dev/null
}
for e in "${ENVS[@]}"; do   # 22/10: lo spazio dei programmi serve solo se un ambiente manca o va rifatto
  if ! uguale_al_blocco "$e"; then SERVONO=$(( SERVONO + GB_PROGRAMMI * 1000000000 )); break; fi
done
evento avanzamento 1 "$(T 'Da scaricare: circa %s GB. Spazio necessario: %s GB. Spazio libero: %s GB.' "$(GB "$DA_SCARICARE")" "$(GB "$SERVONO")" "$(GB "$LIBERI")")"
[ "$LIBERI" -gt "$SERVONO" ] \
  || fallisci SPAZIO_INSUFFICIENTE "$(T 'Lo spazio libero non basta: servono %s GB, ce ne sono %s.' "$(GB "$SERVONO")" "$(GB "$LIBERI")")" "$(T 'Libera spazio sul disco e rilancia.')"

# velocita' della rete: 16 MB del primo file ancora da scaricare (D034: tempo stimato prima di partire)
v=0
if [ "$DA_SCARICARE" -gt 0 ]; then
  primo=$(tail -n +2 "$CATALOGO" | while IFS=$'\t' read -r g t s p b bf m d; do
    if ! fatto "$d" "$m"; then echo "$s $p"; break; fi; done) || true
  # 22/10: al massimo 60 s; se scade, curl dice lo stesso la velocita' misurata fin li'
  v=$(curl -fsL --max-time 60 -r 0-16777215 -o /dev/null -w '%{speed_download}' "$(url_di ${primo% *} ${primo#* })") || true
  v=${v%.*}; v=${v:-0}
  if [ "${v:-0}" -gt 0 ]; then
    min=$(awk -v b="$DA_SCARICARE" -v v="$v" 'BEGIN {printf "%d", b/v/60 + 1}')
    if [ "$min" -eq 1 ]; then t=$(T '1 minuto'); elif [ "$min" -lt 60 ]; then t=$(T '%s minuti' "$min"); else t=$(T '%s ore' "$(num "$min" 60 1)"); fi
    ETA=$((DA_SCARICARE / v)); evento avanzamento 2 "$(T 'Velocità misurata: %s MB/s. Tempo stimato per scaricare tutto: circa %s.' "$(mb_s "$v")" "$t")"
  else
    v=0; evento avviso 2 "$(T 'Non riesco a misurare la velocità della rete: proseguo senza stima del tempo.')" RETE_NON_MISURATA
  fi
fi
if [ "$STIMA" = 1 ]; then
  GB1() { awk -v b="$1" -v g="$GIB" 'BEGIN {printf "%.1f", b/g}'; }
  if [ "$v" -gt 0 ]; then vel=$(awk -v v="$v" 'BEGIN {printf "%.1f", v/1e6}'); tempo=$((DA_SCARICARE / v))
  elif [ "$DA_SCARICARE" = 0 ]; then vel=null; tempo=0
  else vel=null; tempo=null; fi
  RISULTATO=$(printf '{"da_scaricare_gb":%s,"spazio_necessario_gb":%s,"spazio_libero_gb":%s,"velocita_mb_s":%s,"tempo_stimato_s":%s}' \
    "$(GB1 "$DA_SCARICARE")" "$(GB1 "$SERVONO")" "$(GB1 "$LIBERI")" "$vel" "$tempo")
  PASSO=fine; evento fine null "$(T 'Stima pronta: non ho scaricato nulla.')"; exit 0
fi
if [ "$SI" != 1 ]; then
  read -r -p "[PMN] Procedo con l'installazione? (s/n) " r || r=n
  [ "$r" = s ] || [ "$r" = S ] || { PASSO=fine; ESITO=annullata; evento fine null "$(T 'Installazione annullata: non ho scaricato nulla.')"; exit 3; }
fi

# ===================== 2. programmi =====================
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

# ===================== 3. database =====================
PASSO=database; FATTO=0; TOTALE=$(tail -n +2 "$CATALOGO" | wc -l)
TOT=$(tail -n +2 "$CATALOGO" | awk -F'\t' '{s+=$5} END {print s}')
FATTI=0
pct() { awk -v f="$FATTI" -v t="$TOT" 'BEGIN {printf "%d", 22 + 70 * f / t}'; }
eta() {  # secondi per scaricare cio' che manca (meno $1 byte gia' scaricati), con la velocita' misurata all'inizio
  if [ "$v" -gt 0 ]; then echo $(( (TOT - FATTI - ${1:-0}) / v )); else echo null; fi
}
scarica() {  # url file byte: riprende i pezzi gia' scaricati; ritenta se la rete cade
  local n=0 have
  while :; do
    have=$(stat -c %s "$2" 2>/dev/null || echo 0)
    [ "$have" -ge "$3" ] && return 0
    curl -fsSL -C - --connect-timeout 30 --speed-limit 1024 --speed-time 120 -o "$2" "$1" >> "$LOG" 2>&1 || true
    have=$(stat -c %s "$2" 2>/dev/null || echo 0)
    [ "$have" -ge "$3" ] && return 0
    n=$((n + 1)); [ "$n" -lt 30 ] || return 1
    evento avviso "$(pct)" "$(T 'La connessione si è interrotta: riprovo fra 20 secondi (tentativo %s di 30).' "$n")" RETE_INTERROTTA
    sleep 20
  done
}
while IFS=$'\t' read -r g t s p b bf m d; do
  if fatto "$d" "$m"; then FATTI=$((FATTI + b)); FATTO=$((FATTO + 1)); continue; fi
  url=$(url_di "$s" "$p"); ETA=$(eta)
  if [ "$t" = file ]; then
    f=$PMN_HOME/db/$d; mkdir -p "$(dirname "$f")"
    evento avanzamento "$(pct)" "$(T 'Scarico %s: %s (%s GB)...' "$g" "$(basename "$d")" "$(num "$b" "$GIB" 2)")"
    scarica "$url" "$f.parziale" "$b" || fallisci DOWNLOAD_FALLITO "$(T 'Non riesco a scaricare %s.' "$(basename "$d")")" "$(T 'Controlla la connessione e rilancia.')"
    if [ "$(md5sum < "$f.parziale" | cut -d' ' -f1)" != "$m" ]; then
      rm -f "$f.parziale"; fallisci DB_ROVINATO "$(T 'Il file %s scaricato è rovinato (MD5 diverso).' "$(basename "$d")")" "$(T 'Rilancia: lo riscarico da capo.')"
    fi
    mv "$f.parziale" "$f"
  else
    a=$PMN_HOME/tmp/$(basename "$p").parziale; dir=$PMN_HOME/db/$d
    evento avanzamento "$(pct)" "$(T 'Scarico %s (%s GB, archivio da estrarre)...' "$g" "$(num "$b" "$GIB" 1)")"
    scarica "$url" "$a" "$b" || fallisci DOWNLOAD_FALLITO "$(T 'Non riesco a scaricare %s.' "$(basename "$p")")" "$(T 'Controlla la connessione e rilancia.')"
    if [ "$(md5sum < "$a" | cut -d' ' -f1)" != "$m" ]; then
      rm -f "$a"; fallisci DB_ROVINATO "$(T "L'archivio %s scaricato è rovinato (MD5 diverso)." "$(basename "$p")")" "$(T 'Rilancia: lo riscarico da capo.')"
    fi
    ETA=$(eta "$b"); evento avanzamento "$(pct)" "$(T 'Estraggo e controllo %s...' "$g")"
    rm -rf "$dir"; mkdir -p "$dir"
    tar -xzf "$a" -C "$dir" >> "$LOG" 2>&1 || fallisci DB_ROVINATO "$(T 'Non riesco a estrarre %s.' "$(basename "$p")")" "$(T 'Controlla lo spazio libero e rilancia.')"
    (cd "$dir" && md5sum -c --quiet "$PMN_ROOT/installer/md5/$g.md5") >> "$LOG" 2>&1 \
      || fallisci DB_ROVINATO "$(T "I file di %s non hanno l'MD5 atteso." "$g")" "$(T "Rilancia l'installazione.")"
    rm -f "$a"
  fi
  echo "$m" > "$(segnalino "$d")"; FATTI=$((FATTI + b)); FATTO=$((FATTO + 1))
done < <(tail -n +2 "$CATALOGO")

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
  gruppi=$(tail -n +2 "$CATALOGO" | cut -f1 | awk '!visto[$0]++ {printf "%s\"%s\"", (n++ ? "," : ""), $0}')
  RISULTATO="{\"programmi\":${#ENVS[@]},\"database\":[$gruppi],\"verifica\":\"verde\"}"
  PASSO=fine; evento fine 100 "$(T 'VERDE: il motore è installato e funziona.')"
else
  fallisci VERIFICA_ROSSA "$(T 'ROSSO: la prova finale non ha dato il risultato atteso.')" "$(T 'Manda a noi il file %s.' "$LOG")"
fi
