#!/usr/bin/env bash
# scheduler.sh - run a pipeline step locally or on a PBS cluster (one interface).
# Requires common.sh already sourced (provides info/err/die, PMN_CONDA_BASE).
# Knobs (read from environment): PMN_SCHED (local|pbs), PMN_THREADS, PMN_LOG_DIR,
#   PMN_PBS_QUEUE, PMN_PBS_WALLTIME, PMN_PBS_MEM, PMN_PBS_SELECT (optional override).
# SOURCE this file (do not execute it directly).

# Run a command inside a conda env.
#   local : conda run -n <env> <command...>
#   pbs   : generate a PBS script and submit it with blocking qsub (waits for completion)
# Usage:  pmn_run <conda_env> <job_label> -- <command> [args...]
pmn_run() {
  local env="$1" label="$2"; shift 2
  [ "${1:-}" = "--" ] && shift
  validate_name "$label" || die "invalid job label: $(sanitize_for_log "$label")"
  case "${PMN_SCHED:-local}" in
    pbs)   _pmn_run_pbs "$env" "$label" "$@" ;;
    local) info "$(say "[local] $label" "[locale] $label")"
           conda run --no-capture-output -n "$env" "$@" ;;
    *) die "unknown scheduler: ${PMN_SCHED:-}" ;;
  esac
}

_pmn_run_pbs() {
  local env="$1" label="$2"; shift 2
  [ -n "${PMN_CONDA_BASE:-}" ] || die "PMN_CONDA_BASE is empty (conda info --base failed); cannot generate a PBS job"
  [ -n "${PMN_PBS_QUEUE:-}" ]  || die "execution.pbs_queue is required when scheduler=pbs"
  local logdir="${PMN_LOG_DIR:-./pmn_logs}"
  mkdir -p "$logdir" || die "cannot create log dir"
  logdir="$(cd "$logdir" && pwd)" || die "cannot resolve log dir to an absolute path"
  local pbs="$logdir/${label}.pbs"

  # Resource line: user override (pbs_select) or the standard PBS Pro form (UniTN HPC3 style).
  local selectline="${PMN_PBS_SELECT:-}"
  [ -n "$selectline" ] || selectline="select=1:ncpus=${PMN_THREADS:-8}:mem=${PMN_PBS_MEM:-32GB}"

  # Quote every argument so the command is reproduced verbatim in the PBS script.
  local cmdline="" part
  for part in "$@"; do cmdline+="$(printf '%q ' "$part")"; done
  cmdline="${cmdline% }"

  {
    echo "#PBS -N pmn_${label}"
    echo "#PBS -q ${PMN_PBS_QUEUE}"
    echo "#PBS -l walltime=${PMN_PBS_WALLTIME:-24:00:00}"
    echo "#PBS -l ${selectline}"
    echo "#PBS -o ${logdir}/${label}.o"
    echo "#PBS -e ${logdir}/${label}.e"
    echo "source ${PMN_CONDA_BASE}/etc/profile.d/conda.sh"
    echo "conda activate ${env}"
    echo "set -euo pipefail"
    echo "$cmdline"
  } > "$pbs"
  pmn_strip_crlf "$pbs"

  # Forward an OPTIONAL NCBI API key by NAME only: the value stays in the submitting
  # shell's environment and is never written into the .pbs file on disk (or any log).
  # (For local runs, `conda run` already inherits NCBI_API_KEY from the environment.)
  local qargs=(-W block=true)
  [ -n "${NCBI_API_KEY:-}" ] && qargs+=(-v NCBI_API_KEY)
  info "$(say "[pbs] submitting $label (blocking)" "[pbs] invio $label (bloccante)")"
  qsub "${qargs[@]}" "$pbs" || die "qsub failed for $label"
}
