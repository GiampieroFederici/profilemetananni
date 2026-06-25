#!/usr/bin/env bash
# steps/32_kraken_bracken.sh - k-mer profiling of ONE sample with Kraken2 + Bracken.
# Conda env: pmn_kraken (kraken2, bracken). Idempotent: skips if the Bracken output exists.
#
# Usage: 32_kraken_bracken.sh --sample NAME --in1 R1 [--in2 R2] --db DIR --out DIR
#          [--threads N] [--confidence C] [--readlen L] [--level S] [--min-reads N]
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

SAMPLE=""; IN1=""; IN2=""; DB=""; OUT=""; THREADS=4
CONFIDENCE="0.4"; READLEN="150"; LEVEL="S"; MINREADS="10"
while [ $# -gt 0 ]; do
  case "$1" in
    --sample)     SAMPLE="${2:-}"; shift 2 ;;
    --in1)        IN1="${2:-}"; shift 2 ;;
    --in2)        IN2="${2:-}"; shift 2 ;;
    --db)         DB="${2:-}"; shift 2 ;;
    --out)        OUT="${2:-}"; shift 2 ;;
    --threads)    THREADS="${2:-4}"; shift 2 ;;
    --confidence) CONFIDENCE="${2:-0.4}"; shift 2 ;;
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
validate_decimal "$CONFIDENCE" || die "confidence must be a decimal (e.g. 0.4)"
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
k2out="$OUT/${SAMPLE}.k2out"
brk="$OUT/${SAMPLE}.bracken"
if [ -s "$brk" ]; then
  ok "$(say "$SAMPLE already profiled (Bracken) -> skip" "$SAMPLE già profilato (Bracken) -> salto")"
  exit 0
fi

k2args=(--db "$DB" --threads "$THREADS" --confidence "$CONFIDENCE"
        --report "$k2report" --output "$k2out" --gzip-compression)
if [ -n "$IN2" ]; then
  validate_path_safe "$IN2" || die "Unsafe input path (in2)"
  [ -s "$IN2" ] || die "input not found or empty: $(sanitize_for_log "$IN2")"
  k2args+=(--paired "$IN1" "$IN2")
else
  k2args+=("$IN1")
fi

info "$(say "Classifying $SAMPLE with Kraken2 ..." "Classifico $SAMPLE con Kraken2 ...")"
kraken2 "${k2args[@]}" || die "kraken2 failed for $SAMPLE"

info "$(say "Estimating abundance with Bracken ..." "Stimo l'abbondanza con Bracken ...")"
bracken -d "$DB" -i "$k2report" -o "$brk" -r "$READLEN" -l "$LEVEL" -t "$MINREADS" \
  || die "bracken failed for $SAMPLE"

ok "$(say "$SAMPLE profiled (Kraken2+Bracken)." "$SAMPLE profilato (Kraken2+Bracken).")"
