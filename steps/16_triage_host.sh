#!/usr/bin/env bash
# steps/16_triage_host.sh - triage, part 2: estimate the host share of ONE sample from its
# first --reads fragments, BEFORE trimming and full host filtering.
# Conda env: pmn_hostfilter (bowtie2). Same index chain as 21_hostfilter.sh (--index repeated,
# human last), but Bowtie2 only reads the first N fragments (-u N). Raw reads may still carry
# adapters, so the estimate uses --very-sensitive-local (soft-clips them) whatever the main
# host-filter preset is. Writes <sample>.triage_host.tsv with two lines:
#   tested<TAB>N     fragments Bowtie2 actually looked at
#   nonhost<TAB>M    fragments left after all host passes
# Bowtie2 logs stay in a temp dir (deleted), so MultiQC never reports the subsample as a sample.
# Idempotent: skips if the output already exists.
#
# Usage: 16_triage_host.sh --sample NAME --in1 R1 [--in2 R2] --index PREFIX [--index ...]
#          --out DIR [--reads N] [--threads N]
set -euo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

SAMPLE=""; IN1=""; IN2=""; OUT=""; READS=100000; THREADS=4
INDEXES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --sample)  SAMPLE="${2:-}"; shift 2 ;;
    --in1)     IN1="${2:-}"; shift 2 ;;
    --in2)     IN2="${2:-}"; shift 2 ;;
    --index)   INDEXES+=("${2:-}"); shift 2 ;;
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
[ "${#INDEXES[@]}" -ge 1 ]  || die "at least one --index is required"
[ -s "$IN1" ] || die "input not found or empty: $(sanitize_for_log "$IN1")"
if [ -n "$IN2" ]; then
  validate_path_safe "$IN2" || die "Unsafe input path (in2)"
  [ -s "$IN2" ] || die "input not found or empty: $(sanitize_for_log "$IN2")"
fi
for idx in "${INDEXES[@]}"; do
  validate_path_safe "$idx" || die "Unsafe index path: $(sanitize_for_log "$idx")"
  [ -s "${idx}.1.bt2" ] || [ -s "${idx}.1.bt2l" ] || die "Bowtie2 index not found: $(sanitize_for_log "$idx")"
done
mkdir -p "$OUT" || die "cannot create $OUT"

host_tsv="$OUT/${SAMPLE}.triage_host.tsv"
if [ -s "$host_tsv" ]; then
  ok "$(say "$SAMPLE already triaged (host) -> skip" "$SAMPLE triage host già fatto -> salto")"
  exit 0
fi

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pmn_th_${SAMPLE}.XXXXXX")" || die "mktemp failed"
trap 'rm -rf "$tmp"' EXIT INT TERM

count_fq() { if [ -s "$1" ]; then gzip -dc "$1" | awk 'END { printf "%d\n", NR / 4 }'; else echo 0; fi; }

# Pass 1 reads the first N fragments (-u); later passes only see what survived, so they need no -u.
cur1="$IN1"; cur2="$IN2"; i=0
for index in "${INDEXES[@]}"; do
  i=$((i + 1))
  lim=(); [ "$i" -eq 1 ] && lim=(-u "$READS")
  info "$(say "Triage $SAMPLE: host pass $i ($(basename "$index")) ..." "Triage $SAMPLE: passo host $i ($(basename "$index")) ...")"
  if [ -n "$cur2" ]; then
    bowtie2 -x "$index" -1 "$cur1" -2 "$cur2" "${lim[@]}" -p "$THREADS" --very-sensitive-local \
      --un-conc-gz "$tmp/p${i}_%.fastq.gz" -S /dev/null 2> "$tmp/p${i}.log" \
      || { cat "$tmp/p${i}.log" >&2; die "bowtie2 triage pass $i failed for $SAMPLE"; }
    cur1="$tmp/p${i}_1.fastq.gz"; cur2="$tmp/p${i}_2.fastq.gz"
  else
    bowtie2 -x "$index" -U "$cur1" "${lim[@]}" -p "$THREADS" --very-sensitive-local \
      --un-gz "$tmp/p${i}.fastq.gz" -S /dev/null 2> "$tmp/p${i}.log" \
      || { cat "$tmp/p${i}.log" >&2; die "bowtie2 triage pass $i failed for $SAMPLE"; }
    cur1="$tmp/p${i}.fastq.gz"
  fi
  # an empty survivor set ends the chain early (nothing left for later hosts to remove)
  [ -s "$cur1" ] || break
done

# Bowtie2's summary contains "<N> reads; of these:" (N = pairs for paired input). Search for it:
# some builds print warnings first (e.g. "[WARNING] Failed to launch x86-64-v3 version").
tested="$(awk '/ reads; of these:$/ { print $1; exit }' "$tmp/p1.log")"
validate_uint "$tested" || die "cannot parse the Bowtie2 summary for $SAMPLE"
nonhost="$(count_fq "$cur1")"
printf 'tested\t%s\nnonhost\t%s\n' "$tested" "$nonhost" > "$tmp/host.tsv"
mv -f "$tmp/host.tsv" "$host_tsv" || die "cannot write $host_tsv"
ok "$(say "$SAMPLE triage host: $nonhost of $tested fragments are non-host." "$SAMPLE triage host: $nonhost di $tested frammenti non-host.")"
