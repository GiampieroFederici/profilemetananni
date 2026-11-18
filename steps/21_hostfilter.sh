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
# --prefilter very-fast (pairs, first index only; bin/run.sh asks for it when the first genome is a host of the
# product): the first pass is done in two phases, see fase1 below.
#
# Usage: 21_hostfilter.sh --sample NAME --in1 R1 [--in2 R2] \
#          --index PREFIX [--index PREFIX2 ...] [--host-out DIR] --out DIR [--threads N] \
#          [--log-dir DIR] [--preset very-sensitive|very-sensitive-local] [--prefilter very-fast]
set -euo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

SAMPLE=""; IN1=""; IN2=""; OUT=""; HOST_OUT=""; THREADS=4; LOGDIR=""; PRESET="very-sensitive-local"; PREFILTER=""
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
    --prefilter) PREFILTER="${2:-}"; shift 2 ;;
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
# Phase 1 of the two-phase first pass: the same rule, an allowlisted keyword to ONE flag token.
case "$PREFILTER" in
  "")        BT2_PRE="" ;;
  very-fast) BT2_PRE="--very-fast" ;;
  *) die "invalid --prefilter (very-fast): $(sanitize_for_log "$PREFILTER")" ;;
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

# Progress while Bowtie2 works (13/11/2026: 2 h 24 min on a laptop with nothing on the screen). Read from outside,
# nothing is put in the pipe, so outputs and speed do not change: every PMN_AVANZAMENTO_S seconds (30), how far Bowtie2
# is in its compressed input (R1), from /proc/<pid>/fdinfo. Printed as a percentage of the whole step, one line
# "[progress] N" that the engine turns into an "avanzamento" event (docs/contratto_motore.md). The passes after the
# first read only what the pass before kept, and Bowtie2 goes through those reads about ten times faster (measured:
# 15 against 155 microseconds per pair on SRR4875279, 45 against 556 on a sample with 99 % of pig DNA): they weigh one
# tenth, on the bytes this pass is keeping (size of its output so far). Where /proc cannot be read nothing is printed.
# Two-phase first pass (18/11/2026): phase 1 weighs 3, phase 2 weighs 4, the passes after 1, for the same number of
# pairs (times of 14/11 on SRR4875279, 8 processors: phase 1 about 100 s on 2,955,015 pairs, phase 2 about 50 s on
# 1,160,921, human about 15 s on 986,045: 60, 30 and 9 % of the step). During phase 1 the share of pairs that will go
# on is read from its list: lines written over the last position written (the last line may be half written: not used).
# avanzamento <R1 of this pass> <output R1 of this pass> <weighted bytes of the passes done> <passes after this one>
#             <weight of this pass: 10 the first, 1 the others> [<list of phase 1, when this is phase 1>]
avanzamento() {
  local r1="$1" tot p c fd k v pos out dorme=""
  tot="$(stat -Lc %s "$r1" 2> /dev/null)" || return 0
  trap 'kill "$dorme" 2> /dev/null; exit 0' TERM   # stopped by ferma_avanzamento: no "Terminated" line in the log
  while kill -0 $$ 2> /dev/null; do
    sleep "${PMN_AVANZAMENTO_S:-30}" & dorme=$!
    wait "$dorme"
    pos=0
    for p in /proc/[0-9]*; do
      read -r c < "$p/comm" || continue
      case "$c" in bowtie2-align-*) ;; *) continue ;; esac
      for fd in "$p"/fd/*; do
        [ "$fd" -ef "$r1" ] || continue
        while read -r k v; do [ "$k" = pos: ] && pos="$v"; done < "$p/fdinfo/${fd##*/}"
      done
    done 2> /dev/null
    [ "$pos" -gt 0 ] || continue
    if [ -n "${6:-}" ]; then
      [ -f "$6" ] || continue
      info "[progress] $(awk -v n="$4" -v w="$5" -v p="$pos" -v t="$tot" '{ u = v; v = $1 }
                           END { x = 100 * w * p / (w * t + (u > 0 ? (4 + n) * t * (NR - 1) / u : 0))
                                 printf "%d", (x > 99 ? 99 : x) }' "$6")"
      continue
    fi
    out="$(stat -c %s "$2" 2> /dev/null || echo 0)"
    info "[progress] $(awk -v a="$3" -v n="$4" -v w="$5" -v p="$pos" -v t="$tot" -v o="$out" \
                         'BEGIN { x = 100 * (a + w * p) / (a + w * t + n * o * t / p); printf "%d", (x > 99 ? 99 : x) }')"
  done
}
mon=""
ferma_avanzamento() {
  [ -n "$mon" ] || return 0
  kill "$mon" 2> /dev/null || true; wait "$mon" 2> /dev/null || true
  mon=""
}
trap 'ferma_avanzamento; rm -rf "$tmp"' EXIT INT TERM

# One Bowtie2 pass that keeps the UNALIGNED (non-host) reads, and optionally saves the
# ALIGNED (host) reads. Args: index, r1, r2(or ""), out-basename, index-name, pairs that entered phase 1 (only when
# this is phase 2 of a two-phase pass: the Bowtie2 log is then <sample>.<index>_fase2.bowtie2.log).
# --reorder: non-host reads in the same order at every run. MetaPhlAn puts each read's position in its name
# and Bowtie2 breaks ties between equally good alignments from the name: without it the profile moves by
# ~0.001 points from one run to the next (D054).
run_pass() {
  local index="$1" r1="$2" r2="$3" obase="$4" idxname="$5" prima_fase="${6:-}"
  local log="$LOGDIR/${SAMPLE}.${idxname}${prima_fase:+_fase2}.bowtie2.log" entrate tenute
  # Little free memory: index read from the disk as needed (--mm, bin/lib/common.sh), same alignments.
  local mm=(); pmn_bt2_mm "$index" && mm=(--mm)
  avanzamento "$r1" "${obase}${r2:+_1}.fastq.gz" "$letti" "$(( ${#INDEXES[@]} - i ))" "$peso" & mon=$!
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
  ferma_avanzamento
  entrate="$(sed -n 's/^\([0-9]*\) reads; of these:$/\1/p' "$log" | head -n 1)"
  [ -n "$entrate" ] && [ -n "$tenute" ] || return 1
  printf 'entrate\ttenute\n%s\t%s\n' "${prima_fase:-$entrate}" "$tenute" > "$LOGDIR/${SAMPLE}.${idxname}.coppie.tsv" || return 1
}

# Phase 1 of a two-phase first pass (18/11/2026; measured on 14/11 on SRR4875279, 8 processors: 167-170 s against
# 370-372 s, no pair kept in more, 3 pairs out of 2,955,015 removed in more). Bowtie2 --very-fast (end-to-end) reads
# all the pairs and writes no reads: only which pairs have both reads unaligned (flags 4 and 8), as their position in
# the input (--reorder: the SAM is in the order of the input, one primary line per first read). Those pairs are then
# taken again from the input files with their whole header line: Bowtie2 draws its repeatable random choices from the
# header line too, so phase 2 (run_pass, the command of every pass) must see each pair as a single pass would see it.
# Positions, not names: Bowtie2 drops /1 and /2 from some names only, and no read name is ever compared.
# Args: index, r1, r2, index-name. Writes $tmp/f1_1.fastq and $tmp/f1_2.fastq (not compressed, as measured); sets
# entrate1 (pairs that entered) and letti, peso (progress of phase 2: its bytes counted as the bytes of R1 they were).
fase1() {
  local index="$1" r1="$2" r2="$3" idxname="$4" k tenute byte a b
  local log="$LOGDIR/${SAMPLE}.${idxname}.bowtie2.log"
  # pairs of the list (v = 0), or the others with the name only, as samtools -n writes it (v = 1); FASTQ on stdin
  local scegli='BEGIN { if ((getline n < f) <= 0) n = 0 }
    NR % 4 == 1 { p = ((NR + 3) / 4 == n); if (p && (getline n < f) <= 0) n = 0; if (v) $0 = $1 }
    p != v'
  local mm=(); pmn_bt2_mm "$index" && mm=(--mm)
  avanzamento "$r1" "" 0 "$(( ${#INDEXES[@]} - 1 ))" 3 "$tmp/f1.n" & mon=$!
  bowtie2 ${mm[@]+"${mm[@]}"} -x "$index" -1 "$r1" -2 "$r2" -p "$THREADS" "$BT2_PRE" --reorder 2> "$log" \
    | samtools view -f 64 -F 256 - \
    | awk -F '\t' 'int($2 / 4) % 2 && int($2 / 8) % 2 { print NR } END { print NR > "/dev/stderr" }' \
      > "$tmp/f1.n" 2> "$tmp/f1.viste" || return 1
  ferma_avanzamento
  # every pair must have been seen, or the positions mean nothing
  entrate1="$(sed -n 's/^\([0-9]*\) reads; of these:$/\1/p' "$log" | head -n 1)"
  [ -n "$entrate1" ] && [ "$(cat "$tmp/f1.viste")" = "$entrate1" ] || return 1
  tenute="$(wc -l < "$tmp/f1.n")" || return 1
  gzip -dcf "$r1" | awk -v f="$tmp/f1.n" -v v=0 "$scegli" > "$tmp/f1_1.fastq" & a=$!
  gzip -dcf "$r2" | awk -v f="$tmp/f1.n" -v v=0 "$scegli" > "$tmp/f1_2.fastq" & b=$!
  wait "$a" && wait "$b" || return 1
  for k in 1 2; do
    [ "$(wc -l < "$tmp/f1_$k.fastq")" -eq $((4 * tenute)) ] || return 1
  done
  if [ -n "$HOST_OUT" ]; then   # the pairs removed here; those removed by phase 2 are added after it
    gzip -dcf "$r1" | awk -v f="$tmp/f1.n" -v v=1 "$scegli" | gzip -c > "$tmp/f1_host_1.fastq.gz" & a=$!
    gzip -dcf "$r2" | awk -v f="$tmp/f1.n" -v v=1 "$scegli" | gzip -c > "$tmp/f1_host_2.fastq.gz" & b=$!
    wait "$a" && wait "$b" || return 1
  fi
  byte="$(stat -Lc %s "$r1")" || return 1
  letti=$((3 * byte))
  peso="$(awk -v t="$byte" -v k="$tenute" -v n="$entrate1" -v u="$(stat -c %s "$tmp/f1_1.fastq")" \
            'BEGIN { printf "%.9f", (n * u > 0 ? 4 * t * k / (n * u) : 0) }')"
}

cur1="$IN1"; cur2="$IN2"; i=0; letti=0; peso=10
for index in "${INDEXES[@]}"; do
  i=$((i + 1))
  # for the progress: weighted bytes of R1 read by the passes before this one (the first weighs 10, the others 1)
  [ "$i" -eq 1 ] || { letti="$(awk -v a="$letti" -v w="$peso" -v b="$(stat -Lc %s "$prima")" 'BEGIN { printf "%.0f", a + w * b }')"; peso=1; }
  prima="$cur1"
  idxname="$(basename "$index")"
  info "$(say "Host filtering $SAMPLE: pass $i ($idxname) ..." "Filtro host di $SAMPLE: passo $i ($idxname) ...")"
  if [ "$paired" -eq 1 ] && [ "$i" -eq 1 ] && [ -n "$BT2_PRE" ]; then
    info "$(say "Host filtering $SAMPLE: pass $i, phase 1 of 2 (Bowtie2 $BT2_PRE on all the pairs) ..." \
                "Filtro host di $SAMPLE: passo $i, fase 1 di 2 (Bowtie2 $BT2_PRE su tutte le coppie) ...")"
    fase1 "$index" "$cur1" "$cur2" "$idxname" || die "bowtie2 pass $i ($idxname), phase 1, failed"
    info "$(say "Host filtering $SAMPLE: pass $i, phase 2 of 2 (Bowtie2 $BT2_PRESET on the pairs left) ..." \
                "Filtro host di $SAMPLE: passo $i, fase 2 di 2 (Bowtie2 $BT2_PRESET sulle coppie rimaste) ...")"
    prima="$tmp/f1_1.fastq"
    run_pass "$index" "$tmp/f1_1.fastq" "$tmp/f1_2.fastq" "$tmp/p${i}" "$idxname" "$entrate1" \
      || die "bowtie2 pass $i ($idxname), phase 2, failed"
    if [ -n "$HOST_OUT" ]; then   # removed by phase 1, then removed by phase 2: one file per read, as in a single pass
      for k in 1 2; do
        cat "$HOST_OUT/${SAMPLE}.${idxname}_$k.fastq.gz" >> "$tmp/f1_host_$k.fastq.gz" \
          && mv -f "$tmp/f1_host_$k.fastq.gz" "$HOST_OUT/${SAMPLE}.${idxname}_$k.fastq.gz" || die "cannot write the host reads"
      done
    fi
    cur1="$tmp/p${i}_1.fastq.gz"; cur2="$tmp/p${i}_2.fastq.gz"
  elif [ "$paired" -eq 1 ]; then
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
trap 'ferma_avanzamento; rm -rf "$tmp"; rm -f "$final1.part" ${final2:+"$final2.part"}' EXIT INT TERM
if [ "$paired" -eq 1 ]; then
  mv -f "$cur2" "$final2.part" && mv -f "$final2.part" "$final2" || die "cannot write non-host R2"
fi
mv -f "$cur1" "$final1.part" && mv -f "$final1.part" "$final1" || die "cannot write $final1"

ok "$(say "$SAMPLE host-filtered (${#INDEXES[@]} host pass(es))." "$SAMPLE filtrato dall'host (${#INDEXES[@]} passi).")"
