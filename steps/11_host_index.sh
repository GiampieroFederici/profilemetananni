#!/usr/bin/env bash
# steps/11_host_index.sh - download a host genome from NCBI and build a Bowtie2 index.
# Conda env: pmn_hostfilter (bowtie2, ncbi-datasets-cli, unzip).
# Idempotent: skips if the index already exists.
#
# Usage: 11_host_index.sh --host NAME --accession GCF_xxxxxxxxx.x --out DIR [--threads N]
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

HOST=""; ACC=""; OUT=""; THREADS=4
while [ $# -gt 0 ]; do
  case "$1" in
    --host)       HOST="${2:-}"; shift 2 ;;
    --accession)  ACC="${2:-}"; shift 2 ;;
    --out)        OUT="${2:-}"; shift 2 ;;
    --threads)    THREADS="${2:-4}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_name "$HOST"        || die "Invalid host name: $(sanitize_for_log "$HOST")"
validate_accession "$ACC"    || die "Invalid assembly accession: $(sanitize_for_log "$ACC")"
validate_path_safe "$OUT"    || die "Unsafe output path: $(sanitize_for_log "$OUT")"
validate_uint "$THREADS"     || die "threads must be a non-negative integer"
mkdir -p "$OUT" || die "cannot create $OUT"

idx="$OUT/$HOST"
if [ -s "${idx}.1.bt2" ] || [ -s "${idx}.1.bt2l" ]; then
  ok "$(say "Index for $HOST already exists -> skip" "Indice per $HOST già presente -> salto")"
  exit 0
fi

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pmn_host_${HOST}.XXXXXX")" || die "mktemp failed"
trap 'rm -rf "$tmp"' EXIT INT TERM

info "$(say "Downloading genome $ACC for $HOST ..." "Scarico il genoma $ACC per $HOST ...")"
datasets download genome accession "$ACC" --include genome --filename "$tmp/genome.zip" \
  || die "datasets download failed for $ACC"
unzip -q -o "$tmp/genome.zip" -d "$tmp/genome" || die "unzip failed"

fna="$(find "$tmp/genome" -type f \( -name '*.fna' -o -name '*.fa' -o -name '*.fasta' \) | head -n1)"
[ -n "$fna" ] || die "no genome FASTA found inside the NCBI package"

info "$(say "Building Bowtie2 index for $HOST ..." "Costruisco l'indice Bowtie2 per $HOST ...")"
bowtie2-build --threads "$THREADS" "$fna" "$idx" || die "bowtie2-build failed for $HOST"

ok "$(say "Host index ready: $idx" "Indice host pronto: $idx")"
