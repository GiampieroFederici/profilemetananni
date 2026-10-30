#!/usr/bin/env bash
# steps/32_kraken_bracken.sh - k-mer profiling of ONE sample with Kraken2 + Bracken.
# Conda env: pmn_kraken (kraken2, bracken). Idempotent: skips if the Bracken output exists.
# --confidence has no default: it belongs to the database (refs/kraken_profili.tsv, D022, D023).
# The database is always memory-mapped: identical output to the byte (K1), and a 16 GB PC
# cannot hold PlusPF in RAM.
#
# Usage: 32_kraken_bracken.sh --sample NAME --in1 R1 [--in2 R2] --db DIR --out DIR --confidence C
#          [--threads N] [--readlen L] [--level S] [--min-reads N]
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

SAMPLE=""; IN1=""; IN2=""; DB=""; OUT=""; THREADS=4
CONFIDENCE=""; READLEN="150"; LEVEL="S"; MINREADS="10"
while [ $# -gt 0 ]; do
  case "$1" in
    --sample)     SAMPLE="${2:-}"; shift 2 ;;
    --in1)        IN1="${2:-}"; shift 2 ;;
    --in2)        IN2="${2:-}"; shift 2 ;;
    --db)         DB="${2:-}"; shift 2 ;;
    --out)        OUT="${2:-}"; shift 2 ;;
    --threads)    THREADS="${2:-4}"; shift 2 ;;
    --confidence) CONFIDENCE="${2:-}"; shift 2 ;;
    --readlen)    READLEN="${2:-150}"; shift 2 ;;
    --level)      LEVEL="${2:-S}"; shift 2 ;;
    --min-reads)  MINREADS="${2:-10}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_name "$SAMPLE"      || die "Invalid sample name: $(sanitize_for_log "$SAMPLE")"
validate_path_safe "$IN1"    || die "Unsafe input path (in1)"
validate_path_safe "$DB"     || die "Unsafe db path"
validate_path_safe "$OUT"    || die "Unsafe output path"
validate_uint "$THREADS"     || die "threads must be a non-negative integer"
[ -n "$CONFIDENCE" ]         || die "--confidence is required (see refs/kraken_profili.tsv)"
validate_decimal "$CONFIDENCE" || die "confidence must be a decimal (e.g. 0.1)"
validate_uint "$READLEN"     || die "readlen must be an integer"
validate_uint "$MINREADS"    || die "min-reads must be an integer"
case "$LEVEL" in D|P|C|O|F|G|S) ;; *) die "level must be one of D P C O F G S" ;; esac
[ -s "$IN1" ] || die "input not found or empty: $(sanitize_for_log "$IN1")"
[ -d "$DB" ]  || die "Kraken2 db dir not found: $(sanitize_for_log "$DB")"
if [ ! -s "$DB/database${READLEN}mers.kmer_distrib" ]; then
  warn "$(say "Bracken distribution for read length ${READLEN} not found in DB; bracken may fail. Build it with: bracken-build -d $DB -l ${READLEN}" "Distribuzione Bracken per read length ${READLEN} assente nel DB; bracken potrebbe fallire. Creala con: bracken-build -d $DB -l ${READLEN}")"
fi
mkdir -p "$OUT" || die "cannot create $OUT"

k2report="$OUT/${SAMPLE}.k2report"
# Per-read output: unused by the pipeline (Bracken reads the report), up to hundreds of MB per sample.
# "-" suppresses it; PMN_KEEP_K2OUT=1 keeps it for the validation runs (D037 point 5, C4, L4, K4 grid).
k2out="-"
[ "${PMN_KEEP_K2OUT:-0}" = "1" ] && k2out="$OUT/${SAMPLE}.k2out"
brk="$OUT/${SAMPLE}.bracken"
if [ -s "$brk" ]; then
  ok "$(say "$SAMPLE already profiled (Bracken) -> skip" "$SAMPLE già profilato (Bracken) -> salto")"
  exit 0
fi

# A database larger than the RAM (PlusPF, 118 GB, on a 16 GB PC) is read from the disk piece by piece while Kraken
# classifies: it waits for the disk most of the time (R10, 30/10: 0.6 of 8 processors busy for 52 min on SF3RAt7).
# 4 threads per processor keep more disk reads in flight (150,000 pairs, 8 processors: 5:17 -> 3:49, same report).
K_THREADS=$THREADS
hash_b="$(stat -c %s "$DB/hash.k2d" 2> /dev/null || echo 0)"
ram_b="$(awk '/^MemTotal:/ { printf "%d", $2 * 1024 }' /proc/meminfo)"
[ "$hash_b" -gt "$ram_b" ] && K_THREADS=$(( THREADS * 4 ))
k2args=(--db "$DB" --memory-mapping --threads "$K_THREADS" --confidence "$CONFIDENCE"
        --report "$k2report" --output "$k2out" --gzip-compressed)
if [ -n "$IN2" ]; then
  validate_path_safe "$IN2" || die "Unsafe input path (in2)"
  [ -s "$IN2" ] || die "input not found or empty: $(sanitize_for_log "$IN2")"
  k2args+=(--paired "$IN1" "$IN2")
else
  k2args+=("$IN1")
fi

info "$(say "Classifying $SAMPLE with Kraken2 ..." "Classifico $SAMPLE con Kraken2 ...")"
kraken2 "${k2args[@]}" || die "kraken2 failed for $SAMPLE"

# Bracken keeps the taxa at the level with at least -t reads in the clade (column 2 of the report) and exits with
# "no reads found" when none is left (est_abundance.py 3.0.1): a soil with 677 classified pairs and at most 5 reads per
# species stopped the whole run (ERR2603036, 30/10). Same test here: none = an empty but valid profile, and a warning.
if ! awk -F'\t' -v l="$LEVEL" -v t="$MINREADS" '$4 == l && $2 > 0 && $2 >= t { f = 1; exit } END { exit !f }' "$k2report"; then
  case "$LEVEL" in D) lv=domains ;; P) lv=phylums ;; C) lv=classes ;; O) lv=orders ;; F) lv=families ;; G) lv=genuses ;; S) lv=species ;; esac
  : > "$OUT/${SAMPLE}_bracken_${lv}.k2report" || die "cannot write the Bracken report of $SAMPLE"
  printf 'name\ttaxonomy_id\ttaxonomy_lvl\tkraken_assigned_reads\tadded_reads\tnew_est_reads\tfraction_total_reads\n' \
    > "$brk" || die "cannot write $brk"
  warn "$(say "Kraken: no species with at least $MINREADS reads in $SAMPLE; the Kraken profile of this sample is empty (Bracken not run)." \
              "Kraken: nessuna specie con almeno $MINREADS read in $SAMPLE; il profilo di Kraken di questo campione è vuoto (Bracken non eseguito).")"
  exit 0
fi

info "$(say "Estimating abundance with Bracken ..." "Stimo l'abbondanza con Bracken ...")"
bracken -d "$DB" -i "$k2report" -o "$brk" -r "$READLEN" -l "$LEVEL" -t "$MINREADS" \
  || die "bracken failed for $SAMPLE"

ok "$(say "$SAMPLE profiled (Kraken2+Bracken)." "$SAMPLE profilato (Kraken2+Bracken).")"
