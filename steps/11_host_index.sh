#!/usr/bin/env bash
# steps/11_host_index.sh - build a Bowtie2 index of a host genome, from NCBI (--accession) or from a
# local FASTA file (--fasta: .fa .fasta .fna, also .gz).
# Conda env: pmn_hostfilter (bowtie2, ncbi-datasets-cli, unzip).
# Idempotent: skips if the index already exists and was built from the same source. The source is written
# next to the index in NAME.origine.tsv (source, MD5 of the genome FASTA, date, Bowtie2 version): the report
# shows it. An index with a different source (same name, another accession or another FASTA) is rebuilt.
# The index files appear only when the build has finished (built in a temporary folder, then moved).
#
# Usage: 11_host_index.sh --host NAME (--accession GCF_xxxxxxxxx.x | --fasta FILE) --out DIR [--threads N]
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

HOST=""; ACC=""; FASTA=""; OUT=""; THREADS=4
while [ $# -gt 0 ]; do
  case "$1" in
    --host)       HOST="${2:-}"; shift 2 ;;
    --accession)  ACC="${2:-}"; shift 2 ;;
    --fasta)      FASTA="${2:-}"; shift 2 ;;
    --out)        OUT="${2:-}"; shift 2 ;;
    --threads)    THREADS="${2:-4}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_name "$HOST"        || die "Invalid host name: $(sanitize_for_log "$HOST")"
if [ -n "$ACC" ] && [ -n "$FASTA" ]; then die "Give --accession or --fasta, not both"; fi
if [ -n "$FASTA" ]; then
  validate_path_safe "$FASTA" || die "Unsafe FASTA path: $(sanitize_for_log "$FASTA")"
  case "$FASTA" in
    *.fa|*.fasta|*.fna|*.fa.gz|*.fasta.gz|*.fna.gz) ;;
    *) die "The genome file must end in .fa, .fasta or .fna (also .gz): $(sanitize_for_log "$FASTA")" ;;
  esac
else
  validate_accession "$ACC"  || die "Invalid assembly accession: $(sanitize_for_log "$ACC")"
fi
validate_path_safe "$OUT"    || die "Unsafe output path: $(sanitize_for_log "$OUT")"
validate_uint "$THREADS"     || die "threads must be a non-negative integer"
mkdir -p "$OUT" || die "cannot create $OUT"

idx="$OUT/$HOST"
origine="$OUT/$HOST.origine.tsv"
md5_di() { md5sum < "$1" | cut -d' ' -f1; }
leggi_origine() { awk -F'\t' -v k="$1" '$1 == k { print $2; exit }' "$origine" 2>/dev/null; }

if [ -s "${idx}.1.bt2" ] || [ -s "${idx}.1.bt2l" ]; then
  if [ ! -f "$origine" ]; then   # index built before the source was recorded: as before, it is used
    ok "$(say "Index for $HOST already exists -> skip" "Indice per $HOST già presente -> salto")"
    exit 0
  fi
  if [ -n "$ACC" ]; then
    [ "$(leggi_origine accession)" = "$ACC" ] && { ok "$(say "Index for $HOST already exists -> skip" "Indice per $HOST già presente -> salto")"; exit 0; }
  elif [ ! -f "$FASTA" ]; then   # the FASTA may be deleted once the index is built
    warn "$(say "FASTA of $HOST not found: the index already built is used" "FASTA di $HOST non trovato: uso l'indice già costruito")"
    exit 0
  elif [ "$(leggi_origine md5)" = "$(md5_di "$FASTA")" ]; then
    ok "$(say "Index for $HOST already exists -> skip" "Indice per $HOST già presente -> salto")"
    exit 0
  fi
  warn "$(say "The index of $HOST was built from another genome: rebuilding it" \
             "L'indice di $HOST è stato costruito da un altro genoma: lo ricostruisco")"
fi

if [ -n "$FASTA" ]; then
  [ -f "$FASTA" ] && [ -r "$FASTA" ] || die "FASTA file not found: $(sanitize_for_log "$FASTA")"
  case "$FASTA" in
    *.gz) primo="$(gzip -cd -- "$FASTA" 2>/dev/null | head -c 4096 | tr -d ' \t\r\n' | head -c 1)" ;;
    *)    primo="$(head -c 4096 -- "$FASTA" | tr -d ' \t\r\n' | head -c 1)" ;;
  esac
  [ "$primo" = ">" ] || die "Not a FASTA file (it must start with '>'): $(sanitize_for_log "$FASTA")"
fi

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pmn_host_${HOST}.XXXXXX")" || die "mktemp failed"
costruzione="$(mktemp -d "$OUT/.costruzione_${HOST}.XXXXXX")" || die "mktemp failed"
trap 'rm -rf "$tmp" "$costruzione"' EXIT INT TERM

if [ -n "$FASTA" ]; then
  fna="$FASTA"
else
  info "$(say "Downloading genome $ACC for $HOST ..." "Scarico il genoma $ACC per $HOST ...")"
  datasets download genome accession "$ACC" --include genome --filename "$tmp/genome.zip" \
    || die "datasets download failed for $ACC"
  unzip -q -o "$tmp/genome.zip" -d "$tmp/genome" || die "unzip failed"
  fna="$(find "$tmp/genome" -type f \( -name '*.fna' -o -name '*.fa' -o -name '*.fasta' \) | head -n1)"
  [ -n "$fna" ] || die "no genome FASTA found inside the NCBI package"
fi

info "$(say "Building Bowtie2 index for $HOST ..." "Costruisco l'indice Bowtie2 per $HOST ...")"
bowtie2-build --threads "$THREADS" "$fna" "$costruzione/$HOST" || die "bowtie2-build failed for $HOST"
for s in 1 2 3 4 rev.1 rev.2; do rm -f "$idx.$s.bt2" "$idx.$s.bt2l"; done
rm -f "$origine"
mv "$costruzione/$HOST".* "$OUT/" || die "cannot move the index into $OUT"
{
  if [ -n "$FASTA" ]; then printf 'fasta\t%s\n' "$(basename "$FASTA")"; else printf 'accession\t%s\n' "$ACC"; fi
  printf 'md5\t%s\ndate\t%s\nbowtie2\t%s\n' "$(md5_di "$fna")" "$(date +%Y-%m-%d)" \
    "$(bowtie2-build --version 2>/dev/null | awk 'NR == 1 { print $NF }')"
} > "$origine"

ok "$(say "Host index ready: $idx" "Indice host pronto: $idx")"
