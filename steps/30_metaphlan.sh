#!/usr/bin/env bash
# steps/30_metaphlan.sh - taxonomic profiling of ONE sample with MetaPhlAn 4.
# Conda env: pmn_metaphlan (metaphlan). Idempotent: skips if the profile exists.
#
# Usage: 30_metaphlan.sh --sample NAME --in1 R1 [--in2 R2] [--db DIR] --out DIR [--threads N]
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

SAMPLE=""; IN1=""; IN2=""; DB=""; OUT=""; THREADS=4
while [ $# -gt 0 ]; do
  case "$1" in
    --sample)  SAMPLE="${2:-}"; shift 2 ;;
    --in1)     IN1="${2:-}"; shift 2 ;;
    --in2)     IN2="${2:-}"; shift 2 ;;
    --db)      DB="${2:-}"; shift 2 ;;
    --out)     OUT="${2:-}"; shift 2 ;;
    --threads) THREADS="${2:-4}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_name "$SAMPLE"    || die "Invalid sample name: $(sanitize_for_log "$SAMPLE")"
validate_path_safe "$IN1"  || die "Unsafe input path (in1)"
validate_path_safe "$OUT"  || die "Unsafe output path"
validate_uint "$THREADS"   || die "threads must be a non-negative integer"
[ -s "$IN1" ] || die "input not found or empty: $(sanitize_for_log "$IN1")"
mkdir -p "$OUT" || die "cannot create $OUT"

profile="$OUT/${SAMPLE}_profile.txt"
b2out="$OUT/${SAMPLE}.bowtie2.bz2"
if [ -s "$profile" ]; then
  ok "$(say "$SAMPLE already profiled (MetaPhlAn) -> skip" "$SAMPLE già profilato (MetaPhlAn) -> salto")"
  exit 0
fi

# MetaPhlAn accepts comma-joined paired reads.
reads="$IN1"
if [ -n "$IN2" ]; then
  validate_path_safe "$IN2" || die "Unsafe input path (in2)"
  [ -s "$IN2" ] || die "input not found or empty: $(sanitize_for_log "$IN2")"
  reads="$IN1,$IN2"
fi

args=(
  "$reads"
  --input_type fastq
  --nproc "$THREADS"
  --bowtie2out "$b2out"
  --sample_id "$SAMPLE"
  --unclassified_estimation
  -o "$profile"
)
if [ -n "$DB" ]; then
  validate_path_safe "$DB" || die "Unsafe db path"
  [ -d "$DB" ] || die "MetaPhlAn db dir not found: $(sanitize_for_log "$DB")"
  args+=(--bowtie2db "$DB")
fi

info "$(say "Profiling $SAMPLE with MetaPhlAn ..." "Profilo $SAMPLE con MetaPhlAn ...")"
metaphlan "${args[@]}" || die "metaphlan failed for $SAMPLE"

ok "$(say "$SAMPLE profiled (MetaPhlAn)." "$SAMPLE profilato (MetaPhlAn).")"
