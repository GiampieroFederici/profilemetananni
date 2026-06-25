#!/usr/bin/env bash
# preflight.sh - Step 0 for profilemetananni: environment auto-detection & setup.
#
# Detects: the OS, the scheduler (PBS or local), conda/mamba, and each required
# conda environment (with a probe that the key tool is callable). Optionally checks
# the reference databases. By DEFAULT it only reports; with --install it creates any
# MISSING environment.
#
# Anti-CRLF note: if edited on Windows, run:  sed -i 's/\r$//' preflight.sh
set -uo pipefail

# --- locate own directory and source the libraries ---
PMN_BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$PMN_BIN_DIR/lib/common.sh"
# shellcheck source=lib/requirements.sh
. "$PMN_BIN_DIR/lib/requirements.sh"

# --- defaults ---
DO_INSTALL=0
ASSUME_YES=0
DB_METAPHLAN=""
DB_KRAKEN=""

usage() {
  cat <<'EOF'
profilemetananni - preflight (environment check & setup)

Usage: preflight.sh [options]

Options:
  --lang en|it         Output language (default: en)
  --install            Create any MISSING conda environment (default: report only)
  --yes                Do not ask for confirmation before installing
  --db-metaphlan DIR   Also check the MetaPhlAn database directory
  --db-kraken DIR      Also check the Kraken2 database directory
  -h, --help           Show this help

Exit codes:
  0  all required environments present (and DBs, if checked)
  2  one or more environments missing (and --install not used / install failed)
  3  conda/mamba not found
EOF
}

# --- parse arguments ---
while [ $# -gt 0 ]; do
  case "$1" in
    --lang)          PMN_LANG="${2:-en}"; shift 2 ;;
    --install)       DO_INSTALL=1; shift ;;
    --yes)           ASSUME_YES=1; shift ;;
    --db-metaphlan)  DB_METAPHLAN="${2:-}"; shift 2 ;;
    --db-kraken)     DB_KRAKEN="${2:-}"; shift 2 ;;
    -h|--help)       usage; exit 0 ;;
    *)               die "Unknown option: $1 (use --help)" ;;
  esac
done
export PMN_LANG

say "=== profilemetananni - preflight ===" "=== profilemetananni - controllo ambiente ==="

# --- system info ---
info "$(say "Operating system: $(uname -srm)" "Sistema operativo: $(uname -srm)")"
SCHED="$(detect_scheduler)"
if [ "$SCHED" = "pbs" ]; then
  info "$(say "Scheduler: PBS detected (qsub available)" "Scheduler: PBS rilevato (qsub disponibile)")"
else
  info "$(say "Scheduler: none -> jobs will run locally with bash" "Scheduler: nessuno -> i job girano in locale con bash")"
fi

# --- conda / mamba detection ---
if ! detect_conda; then
  err "$(say "conda/mamba NOT found." "conda/mamba NON trovato.")"
  err "$(say "Install Miniforge first: https://github.com/conda-forge/miniforge" "Installa prima Miniforge: https://github.com/conda-forge/miniforge")"
  exit 3
fi
ok "$(say "Package manager: $PMN_CONDA   (base: ${PMN_CONDA_BASE:-unknown})" "Gestore pacchetti: $PMN_CONDA   (base: ${PMN_CONDA_BASE:-sconosciuta})")"

# --- check each environment ---
missing=()
broken=()
printf '\n%-18s %-10s %s\n' "ENVIRONMENT" "STATUS" "TOOL / PACKAGES"
printf '%s\n' "----------------------------------------------------------------------------"
for env in "${PMN_ENV_ORDER[@]}"; do
  pkgs="${PMN_ENV_PKGS[$env]}"
  probe="${PMN_ENV_PROBE[$env]}"
  if conda_env_exists "$env"; then
    if conda run -n "$env" bash -c "$probe" >/dev/null 2>&1; then
      printf '%-18s %s%-10s%s %s\n' "$env" "$C_GRN" "OK"      "$C_RESET" "$pkgs"
    else
      printf '%-18s %s%-10s%s %s\n' "$env" "$C_YEL" "BROKEN"  "$C_RESET" "$pkgs"
      broken+=("$env")
    fi
  else
    printf '%-18s %s%-10s%s %s\n' "$env" "$C_RED" "MISSING" "$C_RESET" "$pkgs"
    missing+=("$env")
  fi
done
printf '%s\n\n' "----------------------------------------------------------------------------"

# --- optional database checks (warn only; large DBs are never auto-downloaded) ---
check_db() {
  local label="$1" path="$2"
  [ -z "$path" ] && return 0
  if [ -d "$path" ] && [ -n "$(ls -A "$path" 2>/dev/null)" ]; then
    ok "$(say "Database '$label' found: $path" "Database '$label' trovato: $path")"
  else
    warn "$(say "Database '$label' MISSING or empty: $path" "Database '$label' ASSENTE o vuoto: $path")"
    warn "$(say "  How to obtain it: ${PMN_DB_INFO[$label]#*|}" "  Come ottenerlo: ${PMN_DB_INFO[$label]#*|}")"
  fi
}
check_db metaphlan_db "$DB_METAPHLAN"
check_db kraken2_db   "$DB_KRAKEN"

# --- summary ---
if [ ${#missing[@]} -eq 0 ] && [ ${#broken[@]} -eq 0 ]; then
  ok "$(say "All required environments are present. You can proceed." "Tutti gli ambienti richiesti sono presenti. Puoi proseguire.")"
  exit 0
fi

if [ ${#broken[@]} -gt 0 ]; then
  warn "$(say "Broken (present but tool not callable): ${broken[*]}" "Difettosi (presenti ma il tool non parte): ${broken[*]}")"
  warn "$(say "  Fix by reinstalling: conda env remove -n <name>" "  Rimedio: reinstallali con  conda env remove -n <nome>")"
fi

if [ ${#missing[@]} -gt 0 ]; then
  warn "$(say "Missing environments: ${missing[*]}" "Ambienti mancanti: ${missing[*]}")"
  if [ "$DO_INSTALL" -ne 1 ]; then
    info "$(say "Re-run with --install to create them automatically." "Rilancia con --install per crearli automaticamente.")"
    exit 2
  fi

  if [ "$ASSUME_YES" -ne 1 ]; then
    printf '%s ' "$(say "Create ${#missing[@]} environment(s) now? [y/N]" "Creo ora ${#missing[@]} ambiente/i? [y/N]")"
    read -r reply
    case "$reply" in
      y|Y|yes|YES|s|S|si|Si|SI|sì|Sì) ;;
      *) die "$(say "Aborted by user." "Annullato dall'utente.")" ;;
    esac
  fi

  install_failed=0
  for env in "${missing[@]}"; do
    info "$(say "Creating $env ..." "Creo $env ...")"
    # shellcheck disable=SC2086
    if "$PMN_CONDA" create -y -n "$env" "${PMN_CHANNELS[@]}" ${PMN_ENV_PKGS[$env]}; then
      if conda run -n "$env" bash -c "${PMN_ENV_PROBE[$env]}" >/dev/null 2>&1; then
        ok "$(say "$env ready." "$env pronto.")"
      else
        err "$(say "$env created but its tool probe failed." "$env creato ma il test del tool è fallito.")"
        install_failed=1
      fi
    else
      err "$(say "Failed to create $env." "Creazione di $env fallita.")"
      install_failed=1
    fi
  done
  [ "$install_failed" -eq 0 ] || exit 2
  ok "$(say "All missing environments were created. You can proceed." "Tutti gli ambienti mancanti sono stati creati. Puoi proseguire.")"
fi
