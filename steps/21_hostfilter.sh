#!/usr/bin/env bash
# steps/21_hostfilter.sh - remove host reads from ONE sample with Bowtie2.
# Conda env: pmn_hostfilter (bowtie2, samtools). Keeps reads that DO NOT map to the
# host index(es); --index may be repeated to chain several hosts (human is usually last).
# Optionally saves the reads that DID map to the host(s) (--host-out DIR).
# Idempotent: skips if the non-host output already exists.
#
# Usage: 21_hostfilter.sh --sample NAME --in1 R1 [--in2 R2] \
#          --index PREFIX [--index PREFIX2 ...] [--host-out DIR] --out DIR [--threads N]
set -euo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

SAMPLE=""; IN1=""; IN2=""; OUT=""; HOST_OUT=""; THREADS=4
INDEXES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --sample)   SAMPLE="${2:-}"; shift 2 ;;
    --in1)      IN1="${2:-}"; shift 2 ;;
    --in2)      IN2="${2:-}"; shift 2 ;;
    --index)    INDEXES+=("${2:-}"); shift 2 ;;
    --host-out) HOST_OUT="${2:-}"; shift 2 ;;
    --out)      OUT="${2:-}"; shift 2 ;;
    --threads)  THREADS="${2:-4}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_name "$SAMPLE"     || die "Invalid sample name: $(sanitize_for_log "$SAMPLE")"
validate_path_safe "$IN1"   || die "Unsafe input path (in1)"
validate_path_safe "$OUT"   || die "Unsafe output path"
validate_uint "$THREADS"    || die "threads must be a non-negative integer"
[ "${#INDEXES[@]}" -ge 1 ]  || die "at least one --index is required"
[ -s "$IN1" ] || die "input not found or empty: $(sanitize_for_log "$IN1")"
for idx in "${INDEXES[@]}"; do
  validate_path_safe "$idx" || die "Unsafe index path: $(sanitize_for_log "$idx")"
  [ -s "${idx}.1.bt2" ] || [ -s "${idx}.1.bt2l" ] || die "Bowtie2 index not found: $(sanitize_for_log "$idx")"
done
mkdir -p "$OUT" || die "cannot create $OUT"

paired=0
if [ -n "$IN2" ]; then
  validate_path_safe "$IN2" || die "Unsafe input path (in2)"
  [ -s "$IN2" ] || die "input not found or empty: $(sanitize_for_log "$IN2")"
  paired=1
fi
if [ -n "$HOST_OUT" ]; then
  validate_path_safe "$HOST_OUT" || die "Unsafe host-out path"
  mkdir -p "$HOST_OUT" || die "cannot create host-out dir"
fi

# final outputs
final2=""
if [ "$paired" -eq 1 ]; then
  final1="$OUT/${SAMPLE}_nonhost_1.fastq.gz"
  final2="$OUT/${SAMPLE}_nonhost_2.fastq.gz"
else
  final1="$OUT/${SAMPLE}_nonhost.fastq.gz"
fi
# idempotent skip only when ALL expected outputs exist (both mates for paired-end)
if [ -s "$final1" ] && { [ "$paired" -eq 0 ] || [ -s "$final2" ]; }; then
  ok "$(say "$SAMPLE already host-filtered -> skip" "$SAMPLE già filtrato dall'host -> salto")"
  exit 0
fi

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pmn_hf_${SAMPLE}.XXXXXX")" || die "mktemp failed"
trap 'rm -rf "$tmp"' EXIT INT TERM

# One Bowtie2 pass that keeps the UNALIGNED (non-host) reads, and optionally saves the
# ALIGNED (host) reads. Args: index, r1, r2(or ""), out-basename, index-name.
run_pass() {
  local index="$1" r1="$2" r2="$3" obase="$4" idxname="$5"
  local al=()
  if [ -n "$HOST_OUT" ]; then
    if [ -n "$r2" ]; then
      al=(--al-conc-gz "$HOST_OUT/${SAMPLE}.${idxname}_%.fastq.gz")
    else
      al=(--al-gz "$HOST_OUT/${SAMPLE}.${idxname}.fastq.gz")
    fi
  fi
  # ${al[@]+"${al[@]}"} expands safely even when 'al' is empty under set -u (bash < 4.4).
  if [ -n "$r2" ]; then
    bowtie2 -x "$index" -1 "$r1" -2 "$r2" -p "$THREADS" --very-sensitive \
      --un-conc-gz "${obase}_%.fastq.gz" ${al[@]+"${al[@]}"} -S /dev/null || return 1
  else
    bowtie2 -x "$index" -U "$r1" -p "$THREADS" --very-sensitive \
      --un-gz "${obase}.fastq.gz" ${al[@]+"${al[@]}"} -S /dev/null || return 1
  fi
}

cur1="$IN1"; cur2="$IN2"; i=0
for index in "${INDEXES[@]}"; do
  i=$((i + 1))
  idxname="$(basename "$index")"
  info "$(say "Host filtering $SAMPLE: pass $i ($idxname) ..." "Filtro host di $SAMPLE: passo $i ($idxname) ...")"
  if [ "$paired" -eq 1 ]; then
    run_pass "$index" "$cur1" "$cur2" "$tmp/p${i}" "$idxname" || die "bowtie2 pass $i ($idxname) failed"
    cur1="$tmp/p${i}_1.fastq.gz"; cur2="$tmp/p${i}_2.fastq.gz"
  else
    run_pass "$index" "$cur1" "" "$tmp/p${i}" "$idxname" || die "bowtie2 pass $i ($idxname) failed"
    cur1="$tmp/p${i}.fastq.gz"
  fi
done

# Publish the final non-host reads.
mv -f "$cur1" "$final1" || die "cannot write $final1"
if [ "$paired" -eq 1 ]; then
  mv -f "$cur2" "$final2" || die "cannot write non-host R2"
fi

ok "$(say "$SAMPLE host-filtered (${#INDEXES[@]} host pass(es))." "$SAMPLE filtrato dall'host (${#INDEXES[@]} passi).")"
