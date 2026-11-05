#!/usr/bin/env bash
# motore/metaphlan_fette_lotto.sh - prototipo N3 (F3), NON usato da run.sh: serve il sì di Giampiero.
# Come metaphlan_fette.sh solo_mapout, ma "prima la fetta, poi i campioni": ogni fetta (3,6 GB) si legge una volta per
# tutti i campioni invece che una volta per campione. Stessi comandi per ogni read: Bowtie2 rifà il suo generatore
# casuale per ogni read, dal nome, dalla sequenza, dalle qualità e da --seed (manuale, "Randomness in Bowtie 2"),
# quindi il risultato di una read non dipende dalle altre read né dall'ordine dei campioni.
# PMN_BT2_MM=1 aggiunge --mm (indice in memory mapping, condiviso nella cache del disco: manuale di Bowtie2).
# Uso: metaphlan_fette_lotto.sh <cartella di uscita> <processori> <campione> <R1> <R2 o ""> [<campione> <R1> <R2> ...]
set -euo pipefail
O=$1; TH=$2; shift 2
. "${PMN_HOME:-$HOME/.pmn}/installazione.env"
M=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MPA=$PMN_ENVS/pmn_metaphlan/bin
PY=$PMN_ENVS/pmn_reports_py/bin/python
export TMPDIR=$PMN_TMP
mkdir -p "$O"
T=$(mktemp -d "$PMN_TMP/pmn_mpa_lotto.XXXXXX")
trap 'rm -rf "$T"' EXIT
MM=(); [ "${PMN_BT2_MM:-0}" = 1 ] && MM=(--mm)
CAMP=()
while [ $# -gt 0 ]; do
  S=$1; R1=$2; R2=$3; shift 3
  CAMP+=("$S"); mkdir -p "$T/$S"
  IN=()
  for f in "$R1" ${R2:+"$R2"}; do   # read su /mnt/c (v9fs): copia nel disco della WSL, come metaphlan_fette.sh
    if [ "$(stat -f -c %T "$f")" = v9fs ]; then cp "$f" "$T/$S/"; IN+=("$T/$S/$(basename "$f")"); else IN+=("$f"); fi
  done
  PATH=$MPA:$PATH read_fastx.py -l 70 --split_reads 0 "$(IFS=,; echo "${IN[*]}")" > "$T/$S/reads.fq" 2> "$T/$S/nreads.txt"
  for f in "${IN[@]}"; do case "$f" in "$T"/*) rm -f "$f" ;; esac; done
done
for n in 1 2 3 4 5 6; do
  for S in "${CAMP[@]}"; do
    "$MPA/bowtie2" --seed 1992 --quiet --no-unal --very-sensitive ${MM[@]+"${MM[@]}"} -p "$TH" -x "$PMN_FETTE/idx$n/fetta$n" \
      -U "$T/$S/reads.fq" -S "$T/$S/$n.sam"
    "$PY" "$M/arbitro_fette.py" compatta < "$T/$S/$n.sam" > "$T/$S/$n.tsv"; rm -f "$T/$S/$n.sam"
  done
done
for S in "${CAMP[@]}"; do
  rm -f "$T/$S/reads.fq"
  "$PY" "$M/arbitro_fette.py" unisci "$T/$S/nreads.txt" "$O/.$S.mapout.parziale" "$T/$S"/{1,2,3,4,5,6}.tsv
  mv -f "$O/.$S.mapout.parziale" "$O/$S.mapout"
done
