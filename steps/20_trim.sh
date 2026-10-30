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
mkdir -p "$OUT" || die "cannot create $OUT"

out1="$OUT/${SAMPLE}_trim_1.fastq.gz"
out2="$OUT/${SAMPLE}_trim_2.fastq.gz"
json="$OUT/${SAMPLE}_fastp.json"
html="$OUT/${SAMPLE}_fastp.html"

if [ -n "$IN2" ]; then
  validate_path_safe "$IN2" || die "Unsafe input path (in2)"
  [ -s "$IN2" ] || die "input not found or empty: $(sanitize_for_log "$IN2")"
fi

if [ -s "$out1" ]; then
  ok "$(say "$SAMPLE already trimmed -> skip fastp" "$SAMPLE già rifilato -> salto fastp")"
else
  # gzip integrity only when fastp really runs (a rerun skips it), R1 and R2 at the same time
  gzip -t "$IN1" 2>/dev/null & g1=$!
  g2=""; if [ -n "$IN2" ]; then gzip -t "$IN2" 2>/dev/null & g2=$!; fi
  wait "$g1" || die "corrupt gzip: $(sanitize_for_log "$IN1")"
  [ -z "$g2" ] || wait "$g2" || die "corrupt gzip: $(sanitize_for_log "$IN2")"
  # fastp writes hidden .part files next to the outputs, renamed (same folder = atomic) only when it has finished:
  # a run stopped half-way leaves no _trim_1, so the skip above never takes truncated reads. _trim_1 goes last.
  # The names end in .fastq.gz: fastp compresses only an output named *.gz.
  p1="$OUT/.${SAMPLE}_trim_1.part.fastq.gz"; p2="$OUT/.${SAMPLE}_trim_2.part.fastq.gz"
  rm -f "$p1" "$p2"
  args=(--thread "$THREADS" --json "$json" --html "$html")
  if [ -n "$IN2" ]; then
    args=(-i "$IN1" -I "$IN2" -o "$p1" -O "$p2" "${args[@]}")
  else
    args=(-i "$IN1" -o "$p1" "${args[@]}")
  fi
  info "$(say "Trimming $SAMPLE with fastp ..." "Rifilo $SAMPLE con fastp ...")"
  fastp "${args[@]}" || die "fastp failed for $SAMPLE"
  if [ -n "$IN2" ]; then mv -f "$p2" "$out2" || die "cannot write $out2"; fi
  mv -f "$p1" "$out1" || die "cannot write $out1"
fi

# FastQC on raw + trimmed reads (reports aggregated later by MultiQC, and copied into the results).
# FastQC 0.13.0 has no "-o" (only --outdir). A missing report is an error, not a warning nobody sees;
# a rerun redoes only the missing reports (fastp above is skipped).
if command -v fastqc >/dev/null 2>&1; then
  fqc=("$IN1"); [ -n "$IN2" ] && fqc+=("$IN2")
  fqc+=("$out1"); [ -n "$IN2" ] && fqc+=("$out2")
  manca=()
  for f in "${fqc[@]}"; do
    b="$(basename "$f")"; b="${b%.gz}"; b="${b%.fastq}"; b="${b%.fq}"
    [ -s "$OUT/${b}_fastqc.html" ] || manca+=("$f")
  done
  if [ "${#manca[@]}" -gt 0 ]; then
    info "$(say "FastQC on $SAMPLE (${#manca[@]} files) ..." "FastQC su $SAMPLE (${#manca[@]} file) ...")"
    # FastQC reads the gz in small pieces, and every read from the Windows disk (/mnt/c, v9fs) waits on WSL: one raw
    # file of SF3RAt7 took 84 s from there, 18 s from a copy on the WSL disk (R10, 30/10). Files on v9fs are copied to
    # TMPDIR first (same names, so the same reports), removed at the end.
    # FastQC 0.13.0 with a list of files reads them one after the other on one core: one FastQC per file, up to
    # --threads at the same time.
    fq_tmp="$(mktemp -d "${TMPDIR:-/tmp}/pmn_fqc_${SAMPLE}.XXXXXX")" || die "mktemp failed"
    trap 'rm -rf "$fq_tmp"' EXIT
    da=()
    for f in "${manca[@]}"; do
      if [ "$(stat -f -c %T "$f")" = v9fs ]; then
        cp "$f" "$fq_tmp/" || die "cannot copy $(sanitize_for_log "$f") to $fq_tmp"
        da+=("$fq_tmp/$(basename "$f")")
      else
        da+=("$f")
      fi
    done
    printf '%s\0' "${da[@]}" | xargs -0 -n 1 -P "$(( THREADS > 0 ? THREADS : 1 ))" fastqc -q -t 1 --outdir "$OUT" \
      || die "fastqc failed for $SAMPLE"
    rm -rf "$fq_tmp"
    for f in "${manca[@]}"; do
      b="$(basename "$f")"; b="${b%.gz}"; b="${b%.fastq}"; b="${b%.fq}"
      [ -s "$OUT/${b}_fastqc.html" ] || die "fastqc wrote no report for $(sanitize_for_log "$b")"
    done
  fi
else
  warn "$(say "fastqc not installed: no FastQC report for $SAMPLE" "fastqc non installato: nessun report FastQC per $SAMPLE")"
fi

ok "$(say "$SAMPLE trimmed." "$SAMPLE rifilato.")"
