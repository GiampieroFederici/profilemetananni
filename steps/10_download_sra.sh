#!/usr/bin/env bash
# steps/10_download_sra.sh - download ONE SRA run and convert it to gzipped FASTQ.
# Conda env: pmn_download (sra-tools, pigz).
# Idempotent: skips if the output already exists.
#
# Usage: 10_download_sra.sh --srr SRRxxxxxxx --out DIR [--threads N]
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

SRR=""; OUT=""; THREADS=4
while [ $# -gt 0 ]; do
  case "$1" in
    --srr)     SRR="${2:-}"; shift 2 ;;
    --out)     OUT="${2:-}"; shift 2 ;;
    --threads) THREADS="${2:-4}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_srr "$SRR"        || die "Invalid SRA accession: $(sanitize_for_log "$SRR")"
validate_path_safe "$OUT"  || die "Unsafe output path: $(sanitize_for_log "$OUT")"
validate_uint "$THREADS"   || die "threads must be a non-negative integer"
mkdir -p "$OUT" || die "cannot create $OUT"

# Idempotency: single- or paired-end output already present.
if [ -s "$OUT/${SRR}_1.fastq.gz" ] || [ -s "$OUT/${SRR}.fastq.gz" ]; then
  ok "$(say "$SRR already downloaded -> skip" "$SRR già scaricato -> salto")"
  exit 0
fi

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pmn_dl_${SRR}.XXXXXX")" || die "mktemp failed"
trap 'rm -rf "$tmp"' EXIT INT TERM

info "$(say "Prefetching $SRR ..." "Prefetch di $SRR ...")"
prefetch --max-size u -O "$tmp" "$SRR" || die "prefetch failed for $SRR"

info "$(say "Converting to FASTQ ..." "Converto in FASTQ ...")"
if ! fasterq-dump --split-files --threads "$THREADS" -O "$tmp" "$tmp/$SRR/$SRR.sra" 2>/dev/null; then
  fasterq-dump --split-files --threads "$THREADS" -O "$tmp" "$SRR" || die "fasterq-dump failed for $SRR"
fi

# Compress whatever was produced (paired _1/_2 or single).
shopt -s nullglob
produced=0
for f in "$tmp/${SRR}"*.fastq; do
  pigz -p "$THREADS" -c "$f" > "$OUT/$(basename "$f").gz" || die "pigz failed on $f"
  produced=1
done
shopt -u nullglob
[ "$produced" -eq 1 ] || die "no FASTQ produced for $SRR"

ok "$(say "$SRR downloaded." "$SRR scaricato.")"
