#!/usr/bin/env bash
# steps/12_kraken_db.sh - build a Kraken2 database (+ Bracken k-mer distribution).
# Conda env: pmn_kraken (kraken2, bracken, ncbi-datasets-cli, unzip).
# Idempotent: skips if the database (hash.k2d) is already built.
#
# Two modes:
#   --mode standard : kraken2-build --standard (RefSeq bacteria/archaea/viral/human, ~100s of GB)
#   --mode custom   : build from a user-supplied list of NCBI assembly accessions (--genomes FILE)
#
# This is a VERY LARGE / long operation. It is only run when profiling.auto_install_db: true,
# i.e. the user has explicitly confirmed the build.
#
# Usage:
#   12_kraken_db.sh --out DIR --mode standard [--threads N] [--readlen L]
#   12_kraken_db.sh --out DIR --mode custom --genomes FILE [--threads N] [--readlen L]
# FILE = one NCBI assembly accession (GCF_/GCA_) per line; '#' comments allowed.
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

OUT=""; MODE="standard"; GENOMES=""; THREADS=4; READLEN="150"
while [ $# -gt 0 ]; do
  case "$1" in
    --out)     OUT="${2:-}"; shift 2 ;;
    --mode)    MODE="${2:-standard}"; shift 2 ;;
    --genomes) GENOMES="${2:-}"; shift 2 ;;
    --threads) THREADS="${2:-4}"; shift 2 ;;
    --readlen) READLEN="${2:-150}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_path_safe "$OUT" || die "Unsafe output path: $(sanitize_for_log "$OUT")"
validate_db_mode "$MODE"  || die "mode must be standard|custom"
validate_uint "$THREADS"  || die "threads must be a non-negative integer"
validate_uint "$READLEN"  || die "readlen must be an integer"
mkdir -p "$OUT" || die "cannot create $OUT"

# Idempotency: a finished Kraken2 db has hash.k2d + taxo.k2d + opts.k2d.
if [ -s "$OUT/hash.k2d" ] && [ -s "$OUT/taxo.k2d" ]; then
  ok "$(say "Kraken2 database already built in $OUT -> skip" "Database Kraken2 già costruito in $OUT -> salto")"
  # Still ensure the Bracken distribution for this read length exists.
  if [ ! -s "$OUT/database${READLEN}mers.kmer_distrib" ]; then
    info "$(say "Building Bracken distribution for read length $READLEN ..." \
                "Costruisco la distribuzione Bracken per read length $READLEN ...")"
    bracken-build -d "$OUT" -t "$THREADS" -l "$READLEN" || die "bracken-build failed"
  fi
  exit 0
fi

# --- 1. taxonomy (shared by both modes) ---
info "$(say "Downloading NCBI taxonomy for the Kraken2 DB ..." "Scarico la tassonomia NCBI per il DB Kraken2 ...")"
kraken2-build --download-taxonomy --db "$OUT" || die "kraken2-build --download-taxonomy failed"

if [ "$MODE" = "standard" ]; then
  # --- 2a. standard RefSeq libraries + build ---
  info "$(say "Building the STANDARD Kraken2 database (very large, long) ..." \
              "Costruisco il database STANDARD di Kraken2 (molto grande, lungo) ...")"
  kraken2-build --standard --threads "$THREADS" --db "$OUT" || die "kraken2-build --standard failed"
else
  # --- 2b. custom: download each genome from NCBI and add to the library ---
  validate_path_safe "$GENOMES" || die "Unsafe genomes list path"
  [ -s "$GENOMES" ] || die "custom mode requires --genomes FILE (non-empty): $(sanitize_for_log "$GENOMES")"
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/pmn_krkdb.XXXXXX")" || die "mktemp failed"
  trap 'rm -rf "$tmp"' EXIT INT TERM

  n_add=0
  while IFS= read -r raw || [ -n "$raw" ]; do
    acc="$(printf '%s' "$raw" | tr -d '\r' | sed 's/[[:space:]]//g')"
    [ -n "$acc" ] || continue
    case "$acc" in \#*) continue ;; esac
    validate_accession "$acc" || die "Invalid accession in genomes list: $(sanitize_for_log "$acc")"

    info "$(say "Fetching $acc ..." "Scarico $acc ...")"
    datasets download genome accession "$acc" --include genome --filename "$tmp/g.zip" \
      || die "datasets download failed for $acc"
    rm -rf "$tmp/g"; mkdir -p "$tmp/g"
    unzip -q -o "$tmp/g.zip" -d "$tmp/g" || die "unzip failed for $acc"
    while IFS= read -r fna; do
      [ -n "$fna" ] || continue
      kraken2-build --add-to-library "$fna" --db "$OUT" || die "add-to-library failed for $fna"
      n_add=$((n_add + 1))
    done < <(find "$tmp/g" -type f \( -name '*.fna' -o -name '*.fa' -o -name '*.fasta' \))
  done < "$GENOMES"

  [ "$n_add" -gt 0 ] || die "no genomes were added to the library (check the accession list)"
  info "$(say "Added $n_add genome file(s); building the database ..." \
              "Aggiunti $n_add file genoma; costruisco il database ...")"
  kraken2-build --build --threads "$THREADS" --db "$OUT" || die "kraken2-build --build failed"
fi

[ -s "$OUT/hash.k2d" ] || die "Kraken2 build finished but hash.k2d is missing in $OUT"

# --- 3. Bracken k-mer distribution for the chosen read length ---
info "$(say "Building Bracken distribution for read length $READLEN ..." \
            "Costruisco la distribuzione Bracken per read length $READLEN ...")"
bracken-build -d "$OUT" -t "$THREADS" -l "$READLEN" || die "bracken-build failed"

ok "$(say "Kraken2 + Bracken database ready in $OUT" "Database Kraken2 + Bracken pronto in $OUT")"
