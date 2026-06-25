#!/usr/bin/env bash
# steps/13_metaphlan_db.sh - download/install the MetaPhlAn marker database (ChocoPhlAn bowtie2db).
# Conda env: pmn_metaphlan (metaphlan). Idempotent: skips if a database is already present.
#
# This is a LARGE download (several GB). It is only run when profiling.auto_install_db: true,
# i.e. the user has explicitly confirmed the download.
#
# Usage: 13_metaphlan_db.sh --out DIR [--index latest]
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

OUT=""; INDEX="latest"
while [ $# -gt 0 ]; do
  case "$1" in
    --out)   OUT="${2:-}"; shift 2 ;;
    --index) INDEX="${2:-latest}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_path_safe "$OUT" || die "Unsafe output path: $(sanitize_for_log "$OUT")"
validate_name "$INDEX"    || die "Invalid index name: $(sanitize_for_log "$INDEX")"
mkdir -p "$OUT" || die "cannot create $OUT"

# A ready MetaPhlAn db dir contains bowtie2 index files. MetaPhlAn 4 ships ONLY the
# large-index files (*.bt2l), so test each glob SEPARATELY: a single `ls a b` exits
# non-zero when EITHER glob is unmatched, which would defeat the skip and the check below.
_has_mpa_index() { ls "$1"/*.bt2l >/dev/null 2>&1 || ls "$1"/*.bt2 >/dev/null 2>&1; }

# Idempotency: skip if the database is already present.
if _has_mpa_index "$OUT"; then
  ok "$(say "MetaPhlAn database already present in $OUT -> skip" "Database MetaPhlAn già presente in $OUT -> salto")"
  exit 0
fi

info "$(say "Installing the MetaPhlAn database into $OUT (large download, be patient) ..." \
            "Installo il database MetaPhlAn in $OUT (download grande, abbi pazienza) ...")"
# --install downloads and prepares the marker db; --bowtie2db sets the destination directory.
args=(--install --bowtie2db "$OUT")
if [ "$INDEX" != "latest" ]; then
  args+=(--index "$INDEX")
fi
metaphlan "${args[@]}" || die "metaphlan --install failed"

if ! _has_mpa_index "$OUT"; then
  die "MetaPhlAn install finished but no bowtie2 index found in $OUT"
fi
ok "$(say "MetaPhlAn database ready in $OUT" "Database MetaPhlAn pronto in $OUT")"
