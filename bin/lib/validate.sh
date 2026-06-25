#!/usr/bin/env bash
# validate.sh - input-validation & sanitization helpers for profilemetananni (PMN).
# SECURITY-CRITICAL: every value coming from a user, a config file, a filename,
# a metadata field or a tool output MUST pass through these checks before use.
# SOURCE this file (do not execute it directly).
#
# Design rules enforced here:
#   - allowlist, never denylist
#   - never `eval`, never build a command string from untrusted data
#   - reject path traversal (..), control characters and shell metacharacters
#
# Anti-CRLF note: if edited on Windows, run:  sed -i 's/\r$//' validate.sh

# --- generic: is $1 one of the remaining args? ---
validate_in_set() {
  local v="$1"; shift
  local opt
  for opt in "$@"; do [ "$v" = "$opt" ] && return 0; done
  return 1
}

# --- enumerations used by the pipeline ---
validate_lang()        { validate_in_set "${1:-}" en it; }
validate_source()      { validate_in_set "${1:-}" ncbi local both; }
validate_tool_choice() { validate_in_set "${1:-}" metaphlan kraken both; }
validate_yesno()       { validate_in_set "${1:-}" yes no; }
validate_scheduler()   { validate_in_set "${1:-}" auto pbs local; }
validate_db_mode()     { validate_in_set "${1:-}" standard custom; }

# PBS walltime HH:MM:SS (hours may have >2 digits, e.g. 168:00:00)
validate_walltime() {
  case "${1:-}" in
    *[!0-9:]*)                       return 1 ;;
    [0-9]*:[0-9][0-9]:[0-9][0-9])    return 0 ;;
    *)                               return 1 ;;
  esac
}

# PBS memory: digits then an optional unit (b/kb/mb/gb/tb), e.g. 32GB / 512mb / 1tb / 4000
validate_mem() {
  local m="${1:-}"
  [[ "$m" =~ ^[0-9]+([KkMmGgTt][Bb]?|[Bb])?$ ]]
}

# Optional raw '-l select=...' override: allowlist (alnum + : = , . _ + space -) only
validate_pbs_select() {
  local s="${1:-}" re='^[A-Za-z0-9:=,._+ -]+$'
  [ -z "$s" ] && return 0
  [[ "$s" =~ $re ]]
}

# --- non-negative integer ---
validate_uint() {
  case "${1:-}" in
    ''|*[!0-9]*) return 1 ;;
    *) return 0 ;;
  esac
}

# --- decimal number (e.g. a threshold or confidence) ---
validate_decimal() {
  case "${1:-}" in
    ''|*[!0-9.]*) return 1 ;;   # only digits and dots
    *.*.*)        return 1 ;;   # more than one dot
  esac
  # must contain at least one digit (rejects a lone "." )
  case "${1:-}" in *[0-9]*) return 0 ;; *) return 1 ;; esac
}

# --- sample / project name: strict allowlist, no leading dash or dot ---
validate_name() {
  local n="${1:-}"
  [ -n "$n" ] || return 1
  [ ${#n} -le 64 ] || return 1
  case "$n" in
    -*|.*)               return 1 ;;   # no leading '-' (option spoofing) or '.'
    *[!A-Za-z0-9._-]*)   return 1 ;;   # allowlist only
    *)                   return 0 ;;
  esac
}

# --- NCBI assembly accession: GCF_/GCA_ followed by 9 digits, dot, version ---
validate_accession() {
  local a="${1:-}"
  [ ${#a} -le 24 ] || return 1
  case "$a" in
    GC[AF]_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].[0-9]*)
      case "$a" in *[!GCAF0-9._]*) return 1 ;; *) return 0 ;; esac ;;
    *) return 1 ;;
  esac
}

# --- SRA run accession: (S|E|D)RR followed by digits ---
validate_srr() {
  local s="${1:-}"
  [ ${#s} -le 16 ] || return 1
  case "$s" in
    [SED]RR[0-9]*)
      case "$s" in *[!SEDR0-9]*) return 1 ;; *) return 0 ;; esac ;;
    *) return 1 ;;
  esac
}

# --- path is free of traversal, control chars and shell metacharacters ---
validate_path_safe() {
  local p="${1:-}"
  [ -n "$p" ] || return 1
  # reject a leading dash (option-spoofing if ever passed as a bare argv token)
  case "$p" in -*) return 1 ;; esac
  # any control character (newline, tab, CR, etc.)
  case "$p" in
    *[[:cntrl:]]*) return 1 ;;
  esac
  # shell metacharacters / glob characters that must never appear in a configured path
  case "$p" in
    *'$('*|*'`'*|*';'*|*'|'*|*'&'*|*'<'*|*'>'*|*'!'*|*'*'*|*'?'*) return 1 ;;
  esac
  # a leading '~' would be tilde-expanded if ever used unquoted
  case "$p" in '~'*) return 1 ;; esac
  # parent-directory traversal as a path segment
  case "/$p/" in
    *'/../'*) return 1 ;;
  esac
  return 0
}

# --- confine $2 inside base dir $1 (defeats traversal via symlinks/.. ) ---
validate_under_base() {
  local base="${1:-}" target="${2:-}" rb rt
  command -v realpath >/dev/null 2>&1 || { err "realpath not available; cannot confine path"; return 2; }
  rb="$(realpath -m -- "$base" 2>/dev/null)"   || return 1
  rt="$(realpath -m -- "$target" 2>/dev/null)" || return 1
  case "$rt/" in
    "$rb"/*|"$rb"/) return 0 ;;
    *) return 1 ;;
  esac
}

# --- strip control characters so untrusted text cannot inject terminal escapes ---
sanitize_for_log() {
  printf '%s' "${1:-}" | LC_ALL=C tr -d '[:cntrl:]'
}

# --- verify a downloaded file against an expected sha256 (supply-chain integrity) ---
verify_checksum() {
  local file="${1:-}" expected="${2:-}" actual
  [ -f "$file" ] || { err "file not found: $(sanitize_for_log "$file")"; return 1; }
  [ -n "$expected" ] || { err "no expected checksum provided"; return 1; }
  if command -v sha256sum >/dev/null 2>&1; then
    actual="$(sha256sum -- "$file" | awk '{print $1}')"
  elif command -v shasum >/dev/null 2>&1; then
    actual="$(shasum -a 256 -- "$file" | awk '{print $1}')"
  else
    warn "no sha256 tool available; cannot verify $(sanitize_for_log "$file")"
    return 2
  fi
  [ "$actual" = "$expected" ]
}
