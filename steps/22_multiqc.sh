#!/usr/bin/env bash
# steps/22_multiqc.sh - aggregate QC reports (fastp, Bowtie2, etc.) into one MultiQC report.
# Conda env: pmn_qc (multiqc).
#
# Usage: 22_multiqc.sh --in DIR --out DIR [--title NAME]
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

IN=""; OUT=""; TITLE="profilemetananni"
while [ $# -gt 0 ]; do
  case "$1" in
    --in)    IN="${2:-}"; shift 2 ;;
    --out)   OUT="${2:-}"; shift 2 ;;
    --title) TITLE="${2:-profilemetananni}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_path_safe "$IN"   || die "Unsafe input path"
validate_path_safe "$OUT"  || die "Unsafe output path"
validate_name "$TITLE"     || die "Invalid title: $(sanitize_for_log "$TITLE")"
[ -d "$IN" ] || die "input directory not found: $(sanitize_for_log "$IN")"
mkdir -p "$OUT" || die "cannot create $OUT"

if ls "$OUT"/*multiqc_report.html >/dev/null 2>&1; then
  ok "$(say "MultiQC report already exists -> skip (delete it to refresh)" "Report MultiQC già presente -> salto (cancellalo per rigenerarlo)")"
  exit 0
fi

info "$(say "Running MultiQC on $IN ..." "Eseguo MultiQC su $IN ...")"
multiqc --force --title "$TITLE" --outdir "$OUT" "$IN" || die "multiqc failed"

ok "$(say "MultiQC report written to $OUT" "Report MultiQC scritto in $OUT")"
