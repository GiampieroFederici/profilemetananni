#!/usr/bin/env bash
# motore/metaphlan_fette.sh - MetaPhlAn 4.2.4 + vJan25 "a fette" per i PC da 16 GB (D012, D016, D026, D028).
# Read -> Bowtie2 su ognuna delle 6 fette -> arbitro (MAPQ ricalcolato come con l'indice intero) -> MetaPhlAn da mapout.
# Stessi comandi validati in S1-bis, S2.2 e S2.3-bis (picco ~8,5 GB). Percorsi da $PMN_HOME/installazione.env.
# Uso: metaphlan_fette.sh <campione> <R1.fastq.gz> <R2.fastq.gz o ""> <cartella di uscita> [processori]
set -euo pipefail
S=$1; R1=$2; R2=$3; O=$4; TH=${5:-8}
. "${PMN_HOME:-$HOME/.pmn}/installazione.env"
M=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
MPA=$PMN_ENVS/pmn_metaphlan/bin
PY=$PMN_ENVS/pmn_reports_py/bin/python
export TMPDIR=$PMN_TMP   # /tmp di WSL sta in RAM
mkdir -p "$O"

PATH=$MPA:$PATH read_fastx.py -l 70 --split_reads 0 "$R1${R2:+,$R2}" > "$O/reads.fq" 2> "$O/nreads.txt"
for n in 1 2 3 4 5 6; do
  "$MPA/bowtie2" --seed 1992 --quiet --no-unal --very-sensitive -p "$TH" -x "$PMN_FETTE/idx$n/fetta$n" -U "$O/reads.fq" -S "$O/$n.sam"
  "$PY" "$M/arbitro_fette.py" compatta < "$O/$n.sam" > "$O/$n.tsv"; rm -f "$O/$n.sam"
done
rm -f "$O/reads.fq"
"$PY" "$M/arbitro_fette.py" unisci "$O/nreads.txt" "$O/$S.mapout" "$O"/{1,2,3,4,5,6}.tsv
rm -f "$O"/{1,2,3,4,5,6}.tsv
"$MPA/python" "$M/metaphlan_mapout.py" "$O/$S.mapout" --input_type mapout --nproc "$TH" \
  --db_dir "$PMN_MPA_DB" --index mpa_vJan25_CHOCOPhlAnSGB_202503 --offline --sample_id "$S" -o "$O/${S}_profile.txt"
