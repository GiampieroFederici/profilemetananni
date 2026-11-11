#!/usr/bin/env bash
# steps/21_hostfilter.sh - remove host reads from ONE sample with Bowtie2.
# Conda env: pmn_hostfilter (bowtie2, samtools). Keeps reads that DO NOT map to the
# host index(es); --index may be repeated to chain several hosts (human is usually last).
# Pairs follow the "strict" rule of KneadData 0.12.5 (--decontaminate-pairs strict, its default: "remove both
# R1+R2 if either align"), at every pass: a pair is kept only if NEITHER read aligns (samtools -f 12 -F 256).
# Single reads: a read that aligns is removed. Next to each Bowtie2 log, <sample>.<index>.coppie.tsv gives the
# pairs (or single reads) that entered the pass and those kept by it (QC of the report, motore/pmn_motore.py).
# Optionally saves the reads that DID map to the host(s) (--host-out DIR): the removed pairs, both reads.
# Idempotent: skips if the non-host output already exists.
#
# Usage: 21_hostfilter.sh --sample NAME --in1 R1 [--in2 R2] \
#          --index PREFIX [--index PREFIX2 ...] [--host-out DIR] --out DIR [--threads N] \
#          [--log-dir DIR] [--preset very-sensitive|very-sensitive-local]
set -euo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

SAMPLE=""; IN1=""; IN2=""; OUT=""; HOST_OUT=""; THREADS=4; LOGDIR=""; PRESET="very-sensitive-local"
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
    --log-dir)  LOGDIR="${2:-}"; shift 2 ;;
    --preset)   PRESET="${2:-}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

# Bowtie2 sensitivity preset: map an allowlisted keyword to ONE flag token (no untrusted
# string ever reaches the bowtie2 command line).
case "$PRESET" in
  very-sensitive)       BT2_PRESET="--very-sensitive" ;;
  very-sensitive-local) BT2_PRESET="--very-sensitive-local" ;;
  *) die "invalid --preset (very-sensitive|very-sensitive-local): $(sanitize_for_log "$PRESET")" ;;
esac

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

# Where Bowtie2's per-pass alignment summary is written (MultiQC's bowtie2 module parses it).
# Defaults next to the outputs; run.sh points it under work_dir so MultiQC always finds it.
if [ -n "$LOGDIR" ]; then
  validate_path_safe "$LOGDIR" || die "Unsafe log-dir path"
fi
LOGDIR="${LOGDIR:-$OUT}"
mkdir -p "$LOGDIR" || die "cannot create log dir"

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
# --reorder: non-host reads in the same order at every run. MetaPhlAn puts each read's position in its name
# and Bowtie2 breaks ties between equally good alignments from the name: without it the profile moves by
# ~0.001 points from one run to the next (D054).
run_pass() {
  local index="$1" r1="$2" r2="$3" obase="$4" idxname="$5"
  local log="$LOGDIR/${SAMPLE}.${idxname}.bowtie2.log" entrate tenute
  # Little free memory: index read from the disk as needed (--mm, bin/lib/common.sh), same alignments.
  local mm=(); pmn_bt2_mm "$index" && mm=(--mm)
  if [ -n "$r2" ]; then
    # Strict: from Bowtie2's SAM only the pairs with both reads unaligned (flag 4 = read unaligned, 8 = mate
    # unaligned; 256 = secondary, never a read of its own). Unaligned reads keep their sequence and qualities as
    # they came in; samtools -n writes the name without /1 /2 (as Bowtie2 reads it, the comment is dropped).
    # The removed pairs (any read aligned) go to the host BAM with -U, only when they are kept.
    local u=() fq_err="$tmp/${idxname}.samtools_fastq.err"
    [ -n "$HOST_OUT" ] && u=(-U "$tmp/${idxname}.host.bam")
    bowtie2 ${mm[@]+"${mm[@]}"} -x "$index" -1 "$r1" -2 "$r2" -p "$THREADS" "$BT2_PRESET" --reorder 2> "$log" \
      | samtools view -u -f 12 -F 256 ${u[@]+"${u[@]}"} - \
      | samtools fastq -@ "$THREADS" -n -1 "${obase}_1.fastq.gz" -2 "${obase}_2.fastq.gz" -0 /dev/null -s /dev/null - \
        2> "$fq_err" || return 1
    if [ -n "$HOST_OUT" ]; then
      samtools fastq -@ "$THREADS" -n -F 256 -1 "$HOST_OUT/${SAMPLE}.${idxname}_1.fastq.gz" \
        -2 "$HOST_OUT/${SAMPLE}.${idxname}_2.fastq.gz" -0 /dev/null -s /dev/null "$tmp/${idxname}.host.bam" \
        2> /dev/null || return 1
      rm -f "$tmp/${idxname}.host.bam"
    fi
    # samtools: "[M::bam2fq_mainloop] processed N reads" = reads written (two per kept pair)
    tenute="$(sed -n 's/^\[M::bam2fq_mainloop\] processed \([0-9]*\) reads$/\1/p' "$fq_err")"
    [ -n "$tenute" ] && tenute=$((tenute / 2))
  else
    local al=()
    [ -n "$HOST_OUT" ] && al=(--al-gz "$HOST_OUT/${SAMPLE}.${idxname}.fastq.gz")
    # ${al[@]+"${al[@]}"} expands safely even when 'al' is empty under set -u (bash < 4.4).
    bowtie2 ${mm[@]+"${mm[@]}"} -x "$index" -U "$r1" -p "$THREADS" "$BT2_PRESET" --reorder \
      --un-gz "${obase}.fastq.gz" ${al[@]+"${al[@]}"} -S /dev/null 2> "$log" || return 1
    tenute="$(sed -n 's/^ *\([0-9]*\) ([0-9.]*%) aligned 0 times$/\1/p' "$log" | head -n 1)"
  fi
  entrate="$(sed -n 's/^\([0-9]*\) reads; of these:$/\1/p' "$log" | head -n 1)"
  [ -n "$entrate" ] && [ -n "$tenute" ] || return 1
  printf 'entrate\ttenute\n%s\t%s\n' "$entrate" "$tenute" > "$LOGDIR/${SAMPLE}.${idxname}.coppie.tsv" || return 1
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

# Publish the final non-host reads: copy next to the target under a temporary name, then rename
# (same filesystem = atomic; $tmp is on another disk, where mv copies onto the final name).
# Mate 1 last: run.sh resumes by looking at nonhost_1 only.
trap 'rm -rf "$tmp"; rm -f "$final1.part" ${final2:+"$final2.part"}' EXIT INT TERM
if [ "$paired" -eq 1 ]; then
  mv -f "$cur2" "$final2.part" && mv -f "$final2.part" "$final2" || die "cannot write non-host R2"
fi
mv -f "$cur1" "$final1.part" && mv -f "$final1.part" "$final1" || die "cannot write $final1"

ok "$(say "$SAMPLE host-filtered (${#INDEXES[@]} host pass(es))." "$SAMPLE filtrato dall'host (${#INDEXES[@]} passi).")"
