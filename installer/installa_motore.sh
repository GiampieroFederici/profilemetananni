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
# Variabili: PMN_HOME (predefinita ~/.pmn), PMN_URL_PACCHETTI (dove sono pubblicati i pacchetti pmn, D035).
set -euo pipefail

PMN_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PMN_HOME=${PMN_HOME:-$HOME/.pmn}
CATALOGO=$PMN_ROOT/installer/catalogo.tsv
SPECCHIO=""; SI=0; STIMA=0; JSON=0
MICROMAMBA_VER=2.9.0-0
MICROMAMBA_SHA256=366cd9cd8be14df1ab8ed50352a82111082a36686b2d389fdb79a92c3fafb3e3
URL_KRAKEN=https://genome-idx.s3.amazonaws.com/kraken
URL_PMN=${PMN_URL_PACCHETTI:-}
ENVS=(pmn_download pmn_qc pmn_trim pmn_hostfilter pmn_metaphlan pmn_kraken pmn_stats_r pmn_reports_py)
GB_PROGRAMMI=16   # ambienti installati + cache dei pacchetti durante l'installazione (misurati: ~11 GB + margine)

while [ $# -gt 0 ]; do
  case "$1" in
    --si) SI=1; shift ;;
    --stima) STIMA=1; shift ;;
    --json) JSON=1; shift ;;
    --catalogo) CATALOGO=$2; shift 2 ;;
    --specchio) SPECCHIO=${2%/}; shift 2 ;;
    *) echo "Opzione sconosciuta: $1" >&2; exit 1 ;;
  esac
done

# --- messaggi: righe in italiano, oppure eventi JSON (docs/contratto_motore.md, paragrafo 4) ---
# avanzamento usa FATTO e TOTALE (pezzi del passo) ed ETA (secondi, o null); fine usa ESITO e RISULTATO (oggetto JSON).
PASSO=controllo; FATTO=0; TOTALE=1; ETA=null; ESITO=ok; RISULTATO='{}'
CORSA=$(date +%Y-%m-%dT%H-%M-%S)
js() { local t=${1//\\/\\\\}; printf '%s' "${t//\"/\\\"}"; }   # testo dentro una stringa JSON
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
      errore) printf '\n[PMN] ERRORE: %s\n[PMN] Cosa fare: %s\n' "$3" "${5:-}" ;;
      avviso) printf '[PMN] Attenzione: %s\n' "$3" ;;
      *) printf '[PMN] %s\n' "$3" ;;
    esac
  fi
}
fallisci() {  # codice messaggio cosa_fare
  evento errore null "$2" "$1" "$3"
  PASSO=fine; ESITO=errore; RISULTATO="{\"codice\":\"$1\"}"
  evento fine null "Installazione non completata. Rilanciala quando hai risolto: riprende da qui."
  exit 2
}
trap 'PASSO=fine; ESITO=annullata; evento fine null "Installazione interrotta. Rilancia lo stesso comando: riprende da dove era rimasta."; exit 3' INT TERM

mkdir -p "$PMN_HOME"/{bin,db,stato,tmp,log}
export TMPDIR=$PMN_HOME/tmp   # /tmp di WSL sta in RAM: download ed estrazioni su disco
LOG=$PMN_HOME/log/installazione_$(date +%Y%m%d_%H%M%S).log
evento inizio 0 "Installazione del motore di profilemetananni. Dettagli tecnici in $LOG"

# ===================== 1. controlli =====================
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] \
  || fallisci SISTEMA_NON_ADATTO "Serve Linux a 64 bit (anche dentro WSL2 su Windows)." "Usa un PC con Windows 10/11 o Linux a 64 bit."
for c in curl tar gzip md5sum sha256sum awk df; do
  command -v "$c" > /dev/null || fallisci PROGRAMMA_MANCANTE "Manca il programma di sistema '$c'." "Su Ubuntu: sudo apt install $c"
done
[ -s "$CATALOGO" ] || fallisci CONFIG_NON_VALIDA "Non trovo il catalogo dei database ($CATALOGO)." "Riscarica profilemetananni."

url_di() {  # sorgente percorso
  if [ -n "$SPECCHIO" ]; then printf '%s/%s/%s' "$SPECCHIO" "$1" "$2"
  elif [ "$1" = kraken ]; then printf '%s/%s' "$URL_KRAKEN" "$2"
  else printf '%s/%s' "$URL_PMN" "$2"
  fi
}
if [ -z "$SPECCHIO" ] && [ -z "$URL_PMN" ] && tail -n +2 "$CATALOGO" | cut -f3 | grep -qx pmn; then
  fallisci DOWNLOAD_FALLITO "I pacchetti di profilemetananni non sono ancora pubblicati." "Per ora si installa solo in prova, con lo specchio locale."
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
GB() { awk -v b="$1" 'BEGIN {printf "%.0f", b/1e9}'; }
LIBERI=$(( $(df -Pk "$PMN_HOME" | awk 'NR==2 {print $4}') * 1024 ))
SERVONO=$(( SERVONO + GB_PROGRAMMI * 1000000000 ))
evento avanzamento 1 "Da scaricare: circa $(GB "$DA_SCARICARE") GB. Spazio necessario: $(GB "$SERVONO") GB. Spazio libero: $(GB "$LIBERI") GB."
[ "$LIBERI" -gt "$SERVONO" ] \
  || fallisci SPAZIO_INSUFFICIENTE "Lo spazio libero non basta: servono $(GB "$SERVONO") GB, ce ne sono $(GB "$LIBERI")." "Libera spazio sul disco e rilancia."

# velocita' della rete: 16 MB del primo file ancora da scaricare (D034: tempo stimato prima di partire)
v=0
if [ "$DA_SCARICARE" -gt 0 ]; then
  primo=$(tail -n +2 "$CATALOGO" | while IFS=$'\t' read -r g t s p b bf m d; do
    if ! fatto "$d" "$m"; then echo "$s $p"; break; fi; done) || true
  v=$(curl -fsL -r 0-16777215 -o /dev/null -w '%{speed_download}' "$(url_di ${primo% *} ${primo#* })" || echo 0)
  v=${v%.*}
  if [ "${v:-0}" -gt 0 ]; then
    min=$(awk -v b="$DA_SCARICARE" -v v="$v" 'BEGIN {printf "%d", b/v/60 + 1}')
    if [ "$min" -eq 1 ]; then t="1 minuto"; elif [ "$min" -lt 60 ]; then t="$min minuti"; else t="$(awk -v m="$min" 'BEGIN {printf "%.1f", m/60}') ore"; fi
    ETA=$((DA_SCARICARE / v)); evento avanzamento 2 "Velocita' misurata: $(awk -v v="$v" 'BEGIN {printf "%.1f", v/1e6}') MB/s. Tempo stimato per scaricare tutto: circa $t."
  else
    v=0; evento avviso 2 "Non riesco a misurare la velocita' della rete: proseguo senza stima del tempo." RETE_NON_MISURATA
  fi
fi
if [ "$STIMA" = 1 ]; then
  GB1() { awk -v b="$1" 'BEGIN {printf "%.1f", b/1e9}'; }
  if [ "$v" -gt 0 ]; then vel=$(awk -v v="$v" 'BEGIN {printf "%.1f", v/1e6}'); tempo=$((DA_SCARICARE / v))
  elif [ "$DA_SCARICARE" = 0 ]; then vel=null; tempo=0
  else vel=null; tempo=null; fi
  RISULTATO=$(printf '{"da_scaricare_gb":%s,"spazio_necessario_gb":%s,"spazio_libero_gb":%s,"velocita_mb_s":%s,"tempo_stimato_s":%s}' \
    "$(GB1 "$DA_SCARICARE")" "$(GB1 "$SERVONO")" "$(GB1 "$LIBERI")" "$vel" "$tempo")
  PASSO=fine; evento fine null "Stima pronta: non ho scaricato nulla."; exit 0
fi
if [ "$SI" != 1 ]; then
  read -r -p "[PMN] Procedo con l'installazione? (s/n) " r || r=n
  [ "$r" = s ] || [ "$r" = S ] || { PASSO=fine; ESITO=annullata; evento fine null "Installazione annullata: non ho scaricato nulla."; exit 3; }
fi

# ===================== 2. programmi =====================
PASSO=programmi; FATTO=0; TOTALE=${#ENVS[@]}; ETA=null
MM=$PMN_HOME/bin/micromamba
if ! { [ -x "$MM" ] && echo "$MICROMAMBA_SHA256  $MM" | sha256sum -c --status; }; then
  evento avanzamento 5 "Scarico il gestore dei programmi (micromamba $MICROMAMBA_VER)..."
  curl -fsSL --retry 10 --retry-delay 5 -o "$MM.parziale" \
    "https://github.com/mamba-org/micromamba-releases/releases/download/$MICROMAMBA_VER/micromamba-linux-64" >> "$LOG" 2>&1 \
    || fallisci DOWNLOAD_FALLITO "Non riesco a scaricare micromamba." "Controlla la connessione e rilancia."
  echo "$MICROMAMBA_SHA256  $MM.parziale" | sha256sum -c --status \
    || { rm -f "$MM.parziale"; fallisci DB_ROVINATO "Il file di micromamba scaricato e' rovinato." "Rilancia l'installazione."; }
  chmod +x "$MM.parziale"; mv "$MM.parziale" "$MM"
fi
export MAMBA_ROOT_PREFIX=$PMN_HOME/mamba
uguale_al_blocco() {  # env: i pacchetti installati sono esattamente quelli del file di blocco?
  local d=$MAMBA_ROOT_PREFIX/envs/$1
  [ -d "$d/conda-meta" ] || return 1
  diff -q <(grep '^https://' "$PMN_ROOT/installer/lock/$1.txt" | sed 's|.*/||; s|#.*||; s|\.conda$||; s|\.tar\.bz2$||' | sort) \
          <(cd "$d/conda-meta" && ls -- *.json | sed 's|\.json$||' | sort) > /dev/null
}
i=0
for e in "${ENVS[@]}"; do
  i=$((i + 1))
  if uguale_al_blocco "$e"; then continue; fi
  FATTO=$((i - 1)); evento avanzamento $((5 + i * 2)) "Installo i programmi: ambiente $i di ${#ENVS[@]} ($e)..."
  rm -rf "${MAMBA_ROOT_PREFIX:?}/envs/$e"
  "$MM" create -y -q -n "$e" -f "$PMN_ROOT/installer/lock/$e.txt" >> "$LOG" 2>&1 \
    || fallisci DOWNLOAD_FALLITO "Non riesco a installare l'ambiente $e." "Controlla la connessione e rilancia."
  uguale_al_blocco "$e" || fallisci DB_ROVINATO "L'ambiente $e non corrisponde alle versioni previste." "Rilancia l'installazione."
done
"$MM" clean -a -y >> "$LOG" 2>&1 || true   # la cache dei pacchetti non serve piu'
FATTO=${#ENVS[@]}; evento avanzamento 22 "Programmi installati (${#ENVS[@]} ambienti, MetaPhlAn $(ls "$MAMBA_ROOT_PREFIX/envs/pmn_metaphlan/conda-meta" | sed -n 's/^metaphlan-\([0-9.]*\)-.*/\1/p'))."

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
    evento avviso "$(pct)" "La connessione si e' interrotta: riprovo fra 20 secondi (tentativo $n di 30)." RETE_INTERROTTA
    sleep 20
  done
}
while IFS=$'\t' read -r g t s p b bf m d; do
  if fatto "$d" "$m"; then FATTI=$((FATTI + b)); FATTO=$((FATTO + 1)); continue; fi
  url=$(url_di "$s" "$p"); ETA=$(eta)
  if [ "$t" = file ]; then
    f=$PMN_HOME/db/$d; mkdir -p "$(dirname "$f")"
    evento avanzamento "$(pct)" "Scarico $g: $(basename "$d") ($(awk -v b="$b" 'BEGIN {printf "%.2f", b/1e9}') GB)..."
    scarica "$url" "$f.parziale" "$b" || fallisci DOWNLOAD_FALLITO "Non riesco a scaricare $(basename "$d")." "Controlla la connessione e rilancia."
    if [ "$(md5sum < "$f.parziale" | cut -d' ' -f1)" != "$m" ]; then
      rm -f "$f.parziale"; fallisci DB_ROVINATO "Il file $(basename "$d") scaricato e' rovinato (MD5 diverso)." "Rilancia: lo riscarico da capo."
    fi
    mv "$f.parziale" "$f"
  else
    a=$PMN_HOME/tmp/$(basename "$p").parziale; dir=$PMN_HOME/db/$d
    evento avanzamento "$(pct)" "Scarico $g ($(awk -v b="$b" 'BEGIN {printf "%.1f", b/1e9}') GB, archivio da estrarre)..."
    scarica "$url" "$a" "$b" || fallisci DOWNLOAD_FALLITO "Non riesco a scaricare $(basename "$p")." "Controlla la connessione e rilancia."
    if [ "$(md5sum < "$a" | cut -d' ' -f1)" != "$m" ]; then
      rm -f "$a"; fallisci DB_ROVINATO "L'archivio $(basename "$p") scaricato e' rovinato (MD5 diverso)." "Rilancia: lo riscarico da capo."
    fi
    ETA=$(eta "$b"); evento avanzamento "$(pct)" "Estraggo e controllo $g..."
    rm -rf "$dir"; mkdir -p "$dir"
    tar -xzf "$a" -C "$dir" >> "$LOG" 2>&1 || fallisci DB_ROVINATO "Non riesco a estrarre $(basename "$p")." "Controlla lo spazio libero e rilancia."
    (cd "$dir" && md5sum -c --quiet "$PMN_ROOT/installer/md5/$g.md5") >> "$LOG" 2>&1 \
      || fallisci DB_ROVINATO "I file di $g non hanno l'MD5 atteso." "Rilancia l'installazione."
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

# ===================== 5. prova finale =====================
PASSO=verifica; FATTO=0; TOTALE=1; ETA=null
evento avanzamento 93 "Prova finale su un piccolo campione (alcuni minuti)..."
if PMN_HOME=$PMN_HOME bash "$PMN_ROOT/installer/verifica_motore.sh" >> "$LOG" 2>&1; then
  gruppi=$(tail -n +2 "$CATALOGO" | cut -f1 | awk '!visto[$0]++ {printf "%s\"%s\"", (n++ ? "," : ""), $0}')
  RISULTATO="{\"programmi\":${#ENVS[@]},\"database\":[$gruppi],\"verifica\":\"verde\"}"
  PASSO=fine; evento fine 100 "VERDE: il motore e' installato e funziona."
else
  fallisci VERIFICA_ROSSA "ROSSO: la prova finale non ha dato il risultato atteso." "Manda a noi il file $LOG."
fi
