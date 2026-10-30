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
# File di passaggio (read preparate, ~1 GB per 1,5 M di coppie, lette 6 volte; SAM e tabelle delle fette) nel disco
# della WSL, non nella cartella del progetto: questa sta su Windows (/mnt/c), dove scriverle costava ~1 minuto a
# campione (R10, misura del 30/10). Stessi file, stesso contenuto; tolti anche se la corsa si ferma.
T=$(mktemp -d "$PMN_TMP/pmn_mpa_$S.XXXXXX")
trap 'rm -rf "$T"' EXIT

PATH=$MPA:$PATH read_fastx.py -l 70 --split_reads 0 "$R1${R2:+,$R2}" > "$T/reads.fq" 2> "$T/nreads.txt"
for n in 1 2 3 4 5 6; do
  "$MPA/bowtie2" --seed 1992 --quiet --no-unal --very-sensitive -p "$TH" -x "$PMN_FETTE/idx$n/fetta$n" -U "$T/reads.fq" -S "$T/$n.sam"
  "$PY" "$M/arbitro_fette.py" compatta < "$T/$n.sam" > "$T/$n.tsv"; rm -f "$T/$n.sam"
done
rm -f "$T/reads.fq"
"$PY" "$M/arbitro_fette.py" unisci "$T/nreads.txt" "$O/$S.mapout" "$T"/{1,2,3,4,5,6}.tsv
rm -f "$T"/{1,2,3,4,5,6}.tsv
"$MPA/python" "$M/metaphlan_mapout.py" "$O/$S.mapout" --input_type mapout --nproc "$TH" \
  --db_dir "$PMN_MPA_DB" --index mpa_vJan25_CHOCOPhlAnSGB_202503 --offline --sample_id "$S" -o "$O/${S}_profile.txt"
