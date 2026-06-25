#!/usr/bin/env bash
# common.sh - shared helpers for profilemetananni (PMN).
# Bilingual logging (EN/IT), scheduler detection, conda/mamba detection.
# SOURCE this file (do not execute it directly).
#
# Anti-CRLF note: if edited on Windows, run:  sed -i 's/\r$//' common.sh

# --- guard: associative arrays require bash >= 4 ---
if [ -z "${BASH_VERSINFO:-}" ] || [ "${BASH_VERSINFO[0]}" -lt 4 ]; then
  echo "ERROR: bash >= 4 is required (found: ${BASH_VERSION:-unknown})." >&2
  return 1 2>/dev/null || exit 1
fi

# --- output language: en (default) or it ---
PMN_LANG="${PMN_LANG:-en}"

# Bilingual print helper:  say "<english text>" "<italian text>"
# Falls back to English if the Italian string is omitted.
say() {
  if [ "${PMN_LANG}" = "it" ]; then
    printf '%s\n' "${2:-$1}"
  else
    printf '%s\n' "$1"
  fi
}

# --- colors (disabled when stdout is not a terminal, or NO_COLOR is set) ---
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_RESET=$'\033[0m'; C_RED=$'\033[31m'; C_GRN=$'\033[32m'
  C_YEL=$'\033[33m'; C_BLU=$'\033[34m'; C_BOLD=$'\033[1m'
else
  C_RESET=''; C_RED=''; C_GRN=''; C_YEL=''; C_BLU=''; C_BOLD=''
fi

# --- timestamped log levels ---
_pmn_ts() { date '+%Y-%m-%d %H:%M:%S'; }
info() { printf '%s [%sINFO%s] %s\n' "$(_pmn_ts)" "$C_BLU" "$C_RESET" "$*"; }
ok()   { printf '%s [%s OK %s] %s\n' "$(_pmn_ts)" "$C_GRN" "$C_RESET" "$*"; }
warn() { printf '%s [%sWARN%s] %s\n' "$(_pmn_ts)" "$C_YEL" "$C_RESET" "$*" >&2; }
err()  { printf '%s [%sFAIL%s] %s\n' "$(_pmn_ts)" "$C_RED" "$C_RESET" "$*" >&2; }
die()  { err "$*"; exit 1; }

# --- anti-CRLF: strip trailing carriage returns from a file, in place ---
pmn_strip_crlf() {
  local f="$1"
  [ -f "$f" ] || return 0
  # portable on GNU and BSD/macOS (avoids the sed -i flag difference)
  if grep -q $'\r' "$f" 2>/dev/null; then
    tr -d '\r' < "$f" > "${f}.pmn_tmp" && mv "${f}.pmn_tmp" "$f"
  fi
  return 0
}

# --- scheduler detection: echoes "pbs" if qsub is available, else "local" ---
detect_scheduler() {
  if command -v qsub >/dev/null 2>&1; then
    echo "pbs"
  else
    echo "local"
  fi
}

# --- conda/mamba detection ---
# On success: sets PMN_CONDA (the manager to use, mamba preferred) and
# PMN_CONDA_BASE, makes `conda`/`conda run` usable in this shell, returns 0.
# On failure: returns 1.
detect_conda() {
  PMN_CONDA=""
  if command -v mamba >/dev/null 2>&1; then
    PMN_CONDA="mamba"
  elif command -v conda >/dev/null 2>&1; then
    PMN_CONDA="conda"
  else
    # Not on PATH: probe the usual install locations and source their profile.
    local cand
    for cand in "$HOME/miniforge3" "$HOME/mambaforge" "$HOME/miniconda3" "$HOME/anaconda3"; do
      if [ -x "$cand/bin/conda" ]; then
        # shellcheck disable=SC1091
        . "$cand/etc/profile.d/conda.sh"
        [ -f "$cand/etc/profile.d/mamba.sh" ] && . "$cand/etc/profile.d/mamba.sh"
        if command -v mamba >/dev/null 2>&1; then PMN_CONDA="mamba"; else PMN_CONDA="conda"; fi
        break
      fi
    done
  fi

  [ -n "$PMN_CONDA" ] || return 1

  PMN_CONDA_BASE="$(conda info --base 2>/dev/null)" || PMN_CONDA_BASE=""
  # Ensure `conda`/`conda run` shell integration is loaded.
  if [ -n "$PMN_CONDA_BASE" ] && [ -f "$PMN_CONDA_BASE/etc/profile.d/conda.sh" ]; then
    # shellcheck disable=SC1091
    . "$PMN_CONDA_BASE/etc/profile.d/conda.sh"
  fi
  return 0
}

# --- true if a conda environment with the given name exists ---
conda_env_exists() {
  local name="$1"
  conda env list 2>/dev/null | awk '{print $1}' | grep -qxF "$name"
}
