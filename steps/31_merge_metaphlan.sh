#!/usr/bin/env bash
# steps/31_merge_metaphlan.sh - merge per-sample MetaPhlAn profiles into one table.
# Conda env: pmn_metaphlan (provides merge_metaphlan_tables.py).
#
# Usage: 31_merge_metaphlan.sh --in DIR --out FILE
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

IN=""; OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --in)  IN="${2:-}"; shift 2 ;;
    --out) OUT="${2:-}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_path_safe "$IN"  || die "Unsafe input path"
validate_path_safe "$OUT" || die "Unsafe output path"
[ -d "$IN" ] || die "input directory not found: $(sanitize_for_log "$IN")"

shopt -s nullglob
profiles=("$IN"/*_profile.txt)
shopt -u nullglob
[ "${#profiles[@]}" -gt 0 ] || die "no *_profile.txt found in $IN"

# Always redone (P07): a few seconds, same result for the same profiles; a skip kept the old samples after
# the project changed, while the Kraken matrix (step 33) is always rebuilt.
mkdir -p "$(dirname "$OUT")" || die "cannot create output dir"
info "$(say "Merging ${#profiles[@]} MetaPhlAn profiles ..." "Unisco ${#profiles[@]} profili MetaPhlAn ...")"
merge_metaphlan_tables.py "${profiles[@]}" > "$OUT" || die "merge_metaphlan_tables.py failed"

ok "$(say "Merged table written to $OUT" "Tabella unita scritta in $OUT")"
