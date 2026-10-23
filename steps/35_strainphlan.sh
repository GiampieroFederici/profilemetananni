#!/usr/bin/env bash
# steps/35_strainphlan.sh - strain-level comparison (StrainPhlAn 4.2) of a USER-CHOSEN list of species.
# Conda env: pmn_metaphlan (metaphlan, sample2markers.py, strainphlan).
#
# Input: the *.sam.bz2 files written by 30_metaphlan.sh (--samout), the MetaPhlAn DB dir and its
# pinned index name. For every sample it rebuilds the marker consensus (sample2markers.py, only
# for samples not done yet); then, for each species, it runs strainphlan with --non_interactive,
# which accepts a species name (s__Genus_species) and picks its SGB by itself.
# A species that cannot be analysed (e.g. too few samples carry it) is recorded in
# strainphlan_summary.tsv and skipped: it does not stop the pipeline.
#
# Usage: 35_strainphlan.sh --sam-dir DIR --db DIR --index NAME --species Genus_species
#          [--species ...] --out DIR [--threads N]
set -uo pipefail

PMN_STEP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_STEP_DIR/.." && pwd)"
# shellcheck source=../bin/lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=../bin/lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"

SAM_DIR=""; DB=""; INDEX=""; OUT=""; THREADS=4
SPECIES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --sam-dir) SAM_DIR="${2:-}"; shift 2 ;;
    --db)      DB="${2:-}"; shift 2 ;;
    --index)   INDEX="${2:-}"; shift 2 ;;
    --species) SPECIES+=("${2:-}"); shift 2 ;;
    --out)     OUT="${2:-}"; shift 2 ;;
    --threads) THREADS="${2:-4}"; shift 2 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done

validate_path_safe "$SAM_DIR" || die "Unsafe sam-dir path"
validate_path_safe "$DB"      || die "Unsafe db path"
validate_path_safe "$OUT"     || die "Unsafe output path"
validate_name "$INDEX"        || die "Invalid MetaPhlAn index name: $(sanitize_for_log "$INDEX")"
validate_uint "$THREADS"      || die "threads must be a non-negative integer"
[ "${#SPECIES[@]}" -ge 1 ]    || die "at least one --species is required"
for sp in "${SPECIES[@]}"; do
  # Genus_species (MetaPhlAn naming): letters, digits, underscores only
  [[ "$sp" =~ ^[A-Z][a-z]+_[a-z0-9_]+$ ]] || die "Invalid species name (use Genus_species): $(sanitize_for_log "$sp")"
done
PKL="$DB/$INDEX.pkl"
[ -s "$PKL" ] || die "MetaPhlAn DB file not found: $(sanitize_for_log "$PKL")"

shopt -s nullglob
sams=("$SAM_DIR"/*.sam.bz2)
shopt -u nullglob
[ "${#sams[@]}" -ge 1 ] || die "no *.sam.bz2 in $(sanitize_for_log "$SAM_DIR") (run MetaPhlAn with StrainPhlAn enabled)"

CONS="$OUT/consensus_markers"
mkdir -p "$CONS" || die "cannot create $CONS"

# 1) Marker consensus per sample: only the samples without an output yet (json.bz2 or pkl).
todo=()
for f in "${sams[@]}"; do
  s="$(basename "${f%.sam.bz2}")"
  if [ -s "$CONS/$s.json.bz2" ] || [ -s "$CONS/$s.pkl" ]; then continue; fi
  todo+=("$f")
done
if [ "${#todo[@]}" -gt 0 ]; then
  info "$(say "StrainPhlAn: marker consensus for ${#todo[@]} sample(s) ..." "StrainPhlAn: consenso dei marcatori per ${#todo[@]} campione/i ...")"
  sample2markers.py -i "${todo[@]}" -o "$CONS" -d "$PKL" -n "$THREADS" \
    || die "sample2markers.py failed"
fi
shopt -s nullglob
cons=("$CONS"/*.json.bz2 "$CONS"/*.pkl)
shopt -u nullglob
[ "${#cons[@]}" -ge 1 ] || die "sample2markers.py produced no consensus files in $(sanitize_for_log "$CONS")"

# 2) One strainphlan run per species. Failures are recorded, not fatal.
summary="$OUT/strainphlan_summary.tsv"
printf 'species\tstatus\toutput_dir\n' > "$summary"
n_ok=0
for sp in "${SPECIES[@]}"; do
  sdir="$OUT/$sp"
  if [ -f "$sdir/.done" ]; then
    printf '%s\tok\t%s\n' "$sp" "$sdir" >> "$summary"; n_ok=$((n_ok + 1))
    ok "$(say "StrainPhlAn $sp already done -> skip" "StrainPhlAn $sp già fatto -> salto")"
    continue
  fi
  mkdir -p "$sdir" || die "cannot create $sdir"
  info "$(say "StrainPhlAn: $sp across ${#cons[@]} sample(s) ..." "StrainPhlAn: $sp su ${#cons[@]} campione/i ...")"
  if strainphlan -s "${cons[@]}" -d "$PKL" -c "s__$sp" --non_interactive \
       -o "$sdir" -n "$THREADS" > "$sdir/strainphlan.log" 2>&1; then
    touch "$sdir/.done"
    printf '%s\tok\t%s\n' "$sp" "$sdir" >> "$summary"; n_ok=$((n_ok + 1))
    ok "$(say "StrainPhlAn $sp done." "StrainPhlAn $sp fatto.")"
  else
    printf '%s\tfailed (see strainphlan.log)\t%s\n' "$sp" "$sdir" >> "$summary"
    warn "$(say "StrainPhlAn $sp failed (often: too few samples carry it). Log: $sdir/strainphlan.log" \
               "StrainPhlAn $sp non riuscito (spesso: troppo pochi campioni la contengono). Log: $sdir/strainphlan.log")"
  fi
done

ok "$(say "StrainPhlAn: $n_ok/${#SPECIES[@]} species analysed. Summary: $summary" \
          "StrainPhlAn: $n_ok/${#SPECIES[@]} specie analizzate. Riepilogo: $summary")"
