#!/usr/bin/env bash
# motore/metaphlan_da_mapout.sh - MetaPhlAn 4.2.4 + vJan25 da un mapout già fatto, senza l'indice Bowtie2 intero (D028).
# E' l'ultimo passo di metaphlan_fette.sh, da solo: serve alla diversità a profondità uguale (R1), che rifà MetaPhlAn
# sul sottocampione delle read scritto da steps/42_alpha_equal_depth.py. Percorsi da $PMN_HOME/installazione.env.
# Uso: metaphlan_da_mapout.sh <campione> <file.mapout> <cartella di uscita> [processori]
#      metaphlan_da_mapout.sh --lotto <cartella dei mapout> <cartella di uscita> <processori> <campione>...
# --lotto (F3, L3): i profili di tutti i campioni in un solo processo, il .pkl letto una volta sola; per ogni campione
# gli stessi argomenti della chiamata singola (stesso profilo, intestazione compresa).
set -euo pipefail
. "${PMN_HOME:-$HOME/.pmn}/installazione.env"
M=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export TMPDIR=$PMN_TMP   # /tmp di WSL sta in RAM
if [ "$1" = --lotto ]; then
  D=$2; O=$3; TH=$4; shift 4
  E=$(mktemp "$PMN_TMP/pmn_lotto.XXXXXX")
  trap 'rm -f "$E"' EXIT
  for S in "$@"; do
    rm -f "$O/${S}_profile.txt"
    printf '%s\t%s\t%s\n' "$D/$S.mapout" "$S" "$O/${S}_profile.txt" >> "$E"
  done
  "$PMN_ENVS/pmn_metaphlan/bin/python" "$M/metaphlan_mapout.py" --lotto "$E" --input_type mapout --nproc "$TH" \
    --db_dir "$PMN_MPA_DB" --index mpa_vJan25_CHOCOPhlAnSGB_202503 --offline
  exit 0
fi
S=$1; IN=$2; O=$3; TH=${4:-8}
rm -f "$O/${S}_profile.txt"
"$PMN_ENVS/pmn_metaphlan/bin/python" "$M/metaphlan_mapout.py" "$IN" --input_type mapout --nproc "$TH" \
  --db_dir "$PMN_MPA_DB" --index mpa_vJan25_CHOCOPhlAnSGB_202503 --offline --sample_id "$S" -o "$O/${S}_profile.txt"
