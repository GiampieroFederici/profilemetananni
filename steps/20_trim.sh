#!/usr/bin/env bash
# steps/20_trim.sh - quality/adapter trimming of ONE sample with fastp.
# Conda env: pmn_trim (fastp). Produces gzipped trimmed reads + a JSON/HTML report
# (read later by MultiQC). Paired-end if --in2 is given, otherwise single-end.
# Idempotent: skips if the trimmed output already exists.
#
# Usage: 20_trim.sh --sample NAME --in1 R1.fastq.gz [--in2 R2.fastq.gz] --out DIR [--threads N]
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

SAMPLE=""; IN1=""; IN2=""; OUT=""; THREADS=4
while [ $# -gt 0 ]; do
  case "$1" in
    --sample)  SAMPLE="${2:-}"; shift 2 ;;
    --in1)     IN1="${2:-}"; shift 2 ;;
    --in2)     IN2="${2:-}"; shift 2 ;;
    --out)     OUT="${2:-}"; shift 2 ;;
    --threads) THREADS="${2:-4}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_name "$SAMPLE"     || die "Invalid sample name: $(sanitize_for_log "$SAMPLE")"
validate_path_safe "$IN1"   || die "Unsafe input path (in1)"
validate_path_safe "$OUT"   || die "Unsafe output path"
validate_uint "$THREADS"    || die "threads must be a non-negative integer"
[ -s "$IN1" ] || die "input not found or empty: $(sanitize_for_log "$IN1")"
gzip -t "$IN1" 2>/dev/null  || die "corrupt gzip: $(sanitize_for_log "$IN1")"
mkdir -p "$OUT" || die "cannot create $OUT"

out1="$OUT/${SAMPLE}_trim_1.fastq.gz"
out2="$OUT/${SAMPLE}_trim_2.fastq.gz"
json="$OUT/${SAMPLE}_fastp.json"
html="$OUT/${SAMPLE}_fastp.html"

if [ -s "$out1" ]; then
  ok "$(say "$SAMPLE already trimmed -> skip" "$SAMPLE già rifilato -> salto")"
  exit 0
fi

args=(--thread "$THREADS" --json "$json" --html "$html")
if [ -n "$IN2" ]; then
  validate_path_safe "$IN2" || die "Unsafe input path (in2)"
  [ -s "$IN2" ] || die "input not found or empty: $(sanitize_for_log "$IN2")"
  gzip -t "$IN2" 2>/dev/null || die "corrupt gzip: $(sanitize_for_log "$IN2")"
  args=(-i "$IN1" -I "$IN2" -o "$out1" -O "$out2" "${args[@]}")
else
  args=(-i "$IN1" -o "$out1" "${args[@]}")
fi

info "$(say "Trimming $SAMPLE with fastp ..." "Rifilo $SAMPLE con fastp ...")"
fastp "${args[@]}" || die "fastp failed for $SAMPLE"

# FastQC on raw + trimmed reads (reports aggregated later by MultiQC). Non-fatal.
if command -v fastqc >/dev/null 2>&1; then
  fqc=("$IN1"); [ -n "$IN2" ] && fqc+=("$IN2")
  fqc+=("$out1"); { [ -n "$IN2" ] && [ -s "$out2" ]; } && fqc+=("$out2")
  fastqc -q -t "$THREADS" -o "$OUT" "${fqc[@]}" || warn "$(say "fastqc failed for $SAMPLE (continuing)" "fastqc fallito per $SAMPLE (continuo)")"
fi

ok "$(say "$SAMPLE trimmed." "$SAMPLE rifilato.")"
