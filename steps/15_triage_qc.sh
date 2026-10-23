#!/usr/bin/env bash
# steps/15_triage_qc.sh - triage, part 1: yield + quality of ONE sample, BEFORE trimming.
# Conda env: pmn_trim (fastp). Writes into --out:
#   <sample>.triage_reads.txt  total fragments in the full input (reads, or read pairs)
#   <sample>.triage_qc.json    fastp report on the FIRST --reads fragments only (no reads written)
# MultiQC recognises fastp JSON by content, so 22_multiqc.sh ignores "*.triage_*" files:
# the subsample must not show up as (or overwrite) a real trimming run.
# Idempotent: skips if both outputs already exist.
#
# Usage: 15_triage_qc.sh --sample NAME --in1 R1.fastq.gz [--in2 R2.fastq.gz] --out DIR
#          [--reads N] [--threads N]
set -euo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

SAMPLE=""; IN1=""; IN2=""; OUT=""; READS=100000; THREADS=4
while [ $# -gt 0 ]; do
  case "$1" in
    --sample)  SAMPLE="${2:-}"; shift 2 ;;
    --in1)     IN1="${2:-}"; shift 2 ;;
    --in2)     IN2="${2:-}"; shift 2 ;;
    --out)     OUT="${2:-}"; shift 2 ;;
    --reads)   READS="${2:-}"; shift 2 ;;
    --threads) THREADS="${2:-4}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_name "$SAMPLE"     || die "Invalid sample name: $(sanitize_for_log "$SAMPLE")"
validate_path_safe "$IN1"   || die "Unsafe input path (in1)"
validate_path_safe "$OUT"   || die "Unsafe output path"
validate_uint "$READS"      || die "reads must be a positive integer"
[ "$READS" -gt 0 ]          || die "reads must be a positive integer"
validate_uint "$THREADS"    || die "threads must be a non-negative integer"
[ -s "$IN1" ] || die "input not found or empty: $(sanitize_for_log "$IN1")"
if [ -n "$IN2" ]; then
  validate_path_safe "$IN2" || die "Unsafe input path (in2)"
  [ -s "$IN2" ] || die "input not found or empty: $(sanitize_for_log "$IN2")"
fi
mkdir -p "$OUT" || die "cannot create $OUT"

reads_txt="$OUT/${SAMPLE}.triage_reads.txt"
qc_json="$OUT/${SAMPLE}.triage_qc.json"
if [ -s "$reads_txt" ] && [ -s "$qc_json" ]; then
  ok "$(say "$SAMPLE already triaged (QC) -> skip" "$SAMPLE triage QC già fatto -> salto")"
  exit 0
fi

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pmn_tq_${SAMPLE}.XXXXXX")" || die "mktemp failed"
trap 'rm -rf "$tmp"' EXIT INT TERM

# Yield: count the FULL input (one pass of decompression; R1 is enough for pairs).
info "$(say "Triage $SAMPLE: counting reads ..." "Triage $SAMPLE: conto le reads ...")"
gzip -dc "$IN1" | awk 'END { printf "%d\n", NR / 4 }' > "$tmp/reads.txt" \
  || die "cannot read $(sanitize_for_log "$IN1")"

# Quality: fastp on the first N fragments only, report only (no -o/-O = no reads written).
info "$(say "Triage $SAMPLE: fastp on the first $READS fragments ..." "Triage $SAMPLE: fastp sui primi $READS frammenti ...")"
args=(-i "$IN1" --reads_to_process "$READS" --thread "$THREADS" --json "$tmp/qc.json" --html "$tmp/qc.html")
[ -n "$IN2" ] && args+=(-I "$IN2")
fastp "${args[@]}" 2> "$tmp/fastp.log" || { cat "$tmp/fastp.log" >&2; die "fastp failed for $SAMPLE"; }

mv -f "$tmp/reads.txt" "$reads_txt" && mv -f "$tmp/qc.json" "$qc_json" || die "cannot write triage outputs"
ok "$(say "$SAMPLE triage QC done ($(cat "$reads_txt") fragments)." "$SAMPLE triage QC fatto ($(cat "$reads_txt") frammenti).")"
