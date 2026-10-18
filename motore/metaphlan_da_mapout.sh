#!/usr/bin/env bash
# motore/metaphlan_da_mapout.sh - MetaPhlAn 4.2.4 + vJan25 da un mapout già fatto, senza l'indice Bowtie2 intero (D028).
# E' l'ultimo passo di metaphlan_fette.sh, da solo: serve alla diversità a profondità uguale (R1), che rifà MetaPhlAn
# sul sottocampione delle read scritto da steps/42_alpha_equal_depth.py. Percorsi da $PMN_HOME/installazione.env.
# Uso: metaphlan_da_mapout.sh <campione> <file.mapout> <cartella di uscita> [processori]
set -euo pipefail
S=$1; IN=$2; O=$3; TH=${4:-8}
. "${PMN_HOME:-$HOME/.pmn}/installazione.env"
M=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export TMPDIR=$PMN_TMP   # /tmp di WSL sta in RAM
rm -f "$O/${S}_profile.txt"
"$PMN_ENVS/pmn_metaphlan/bin/python" "$M/metaphlan_mapout.py" "$IN" --input_type mapout --nproc "$TH" \
  --db_dir "$PMN_MPA_DB" --index mpa_vJan25_CHOCOPhlAnSGB_202503 --offline --sample_id "$S" -o "$O/${S}_profile.txt"
