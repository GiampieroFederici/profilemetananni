#!/usr/bin/env bash
# bin/run.sh - orchestrate the profilemetananni pipeline from a config file.
#
# Reads config.yaml (parsed safely), validates every value, runs preflight, then runs
# Phase A (preprocessing), Phase B (read-based profiling) and, if enabled, Phase C (taxa
# dossier, optional/off by default) either locally or on a PBS cluster (auto-detected).
# --phase restricts a run to a single phase. Every step is idempotent and skips work
# already done.
#
# Usage: run.sh --config config.yaml [--dry-run] [--skip-preflight] [--phase a|b|c|all]
set -euo pipefail

PMN_BIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PMN_ROOT="$(cd "$PMN_BIN_DIR/.." && pwd)"
# shellcheck source=lib/common.sh
. "$PMN_ROOT/bin/lib/common.sh"
# shellcheck source=lib/validate.sh
. "$PMN_ROOT/bin/lib/validate.sh"
# shellcheck source=lib/scheduler.sh
. "$PMN_ROOT/bin/lib/scheduler.sh"

CONFIG=""; DRY=0; SKIP_PREFLIGHT=0; YES_TAXA=0
PHASE="all"
usage() {
  cat <<'EOF'
profilemetananni - run

Usage: run.sh --config config.yaml [--dry-run] [--skip-preflight] [--phase a|b|c|all]
              [--yes-send-taxa]
  --dry-run         print the planned steps without executing them
  --skip-preflight  do not run the environment check first
  --phase a|b|c|all  run only this phase (default: all)
  --yes-send-taxa   Phase C only: consent to sending the species names without being
                    asked (for runs with no terminal: nohup, a pipe, a CI job)
EOF
}
while [ $# -gt 0 ]; do
  case "$1" in
    --config)         CONFIG="${2:-}"; shift 2 ;;
    --dry-run)        DRY=1; shift ;;
    --skip-preflight) SKIP_PREFLIGHT=1; shift ;;
    --phase)          PHASE="${2:-}"; shift 2 ;;
    --yes-send-taxa)  YES_TAXA=1; shift ;;
    -h|--help)        usage; exit 0 ;;
    *) die "Unknown option: $(sanitize_for_log "$1")" ;;
  esac
done
[ -n "$CONFIG" ] || { usage; die "--config is required"; }
[ -f "$CONFIG" ] || die "config not found: $(sanitize_for_log "$CONFIG")"
validate_in_set "$PHASE" all a b c || die "invalid --phase (all|a|b|c)"

# --- desktop engine: paths written by installer/installa_motore.sh (docs/contratto_motore.md).
# Read key by key, never sourced: the file also sets PMN_ROOT, which must stay this checkout.
# Without the file: conda environments and the paths in config.yaml, as before.
PMN_ENV_FILE="${PMN_HOME:-$HOME/.pmn}/installazione.env"
env_get() { awk -F= -v k="$1" '$1 == k { sub(/^[^=]*=/, ""); print; exit }' "$PMN_ENV_FILE"; }
PMN_ENVS=""; PMN_FETTE=""; PMN_OSPITE=""
if [ -f "$PMN_ENV_FILE" ]; then
  PMN_ENVS="$(env_get PMN_ENVS)"; PMN_TMP="$(env_get PMN_TMP)"
  validate_path_safe "$PMN_ENVS" && [ -d "$PMN_ENVS" ] || die "PMN_ENVS missing or unsafe in $PMN_ENV_FILE"
  validate_path_safe "$PMN_TMP" && mkdir -p "$PMN_TMP" || die "PMN_TMP missing or unsafe in $PMN_ENV_FILE"
  export TMPDIR="$PMN_TMP"   # /tmp of WSL lives in RAM: downloads and host files go to disk
fi

# --- locate conda; parse config safely (values are shlex-quoted -> safe to source) ---
if [ -n "$PMN_ENVS" ]; then
  parse_py=("$PMN_ENVS/pmn_reports_py/bin/python")
else
  detect_conda || die "conda/mamba not found (run bin/preflight.sh first)"
  parse_py=(conda run --no-capture-output -n pmn_reports_py python)
fi
cfgfile="$(mktemp "${TMPDIR:-/tmp}/pmn_cfg.XXXXXX")" || die "mktemp failed"
trap 'rm -f "$cfgfile"' EXIT INT TERM
"${parse_py[@]}" "$PMN_ROOT/bin/lib/parse_config.py" "$CONFIG" > "$cfgfile" \
  || die "failed to parse config (is env pmn_reports_py installed?)"
# shellcheck disable=SC1090
. "$cfgfile"

# --- desktop engine: installed databases where the config leaves the path empty ---
validate_in_set "$PMN_KRK_PROFILO" completo rapido || die "invalid motore.kraken_db (completo|rapido)"
validate_in_set "$PMN_MPA_MODO" auto fette standard || die "invalid motore.metaphlan_modo (auto|fette|standard)"
if [ -n "$PMN_ENVS" ]; then
  [ -n "$PMN_MPA_DB" ] || PMN_MPA_DB="$(env_get PMN_MPA_DB)"
  if [ -z "$PMN_KRK_DB" ]; then
    if [ "$PMN_KRK_PROFILO" = completo ]; then PMN_KRK_DB="$(env_get PMN_KRAKEN_COMPLETO)"
    else PMN_KRK_DB="$(env_get PMN_KRAKEN_RAPIDO)"; fi
  fi
  PMN_FETTE="$(env_get PMN_FETTE)"; PMN_OSPITE="$(env_get PMN_OSPITE)"
  { [ -z "$PMN_FETTE" ] || validate_path_safe "$PMN_FETTE"; } && { [ -z "$PMN_OSPITE" ] || validate_path_safe "$PMN_OSPITE"; } \
    || die "unsafe PMN_FETTE or PMN_OSPITE in $PMN_ENV_FILE"
fi

# --- Kraken parameters: the profile of the chosen database (refs/kraken_profili.tsv, D022, D023).
# A value written in config.yaml wins. The abundance threshold is for Kraken only (D128): from the
# profile when Kraken runs; with MetaPhlAn alone it is 0, unused (MetaPhlAn is never filtered).
krk_profile() { awk -F'\t' -v p="$PMN_KRK_PROFILO" -v c="$1" '!/^#/ && $1 == p { print $c; exit }' "$PMN_ROOT/refs/kraken_profili.tsv"; }
[ -n "$PMN_KRK_CONF" ] || PMN_KRK_CONF="$(krk_profile 2)"
[ -n "$PMN_KRK_MINREADS" ] || PMN_KRK_MINREADS="$(krk_profile 3)"
if [ -z "$PMN_THRESHOLD" ]; then
  case "$PMN_TOOL" in kraken|both) PMN_THRESHOLD="$(krk_profile 4)" ;; *) PMN_THRESHOLD=0 ;; esac
fi

# --- validate every value ---
validate_lang "$PMN_LANG"            || die "invalid language: $(sanitize_for_log "$PMN_LANG")"
export PMN_LANG
validate_source "$PMN_DATA_SOURCE"   || die "invalid data_source"
validate_name "$PMN_PROJECT"         || die "invalid project_name"
validate_path_safe "$PMN_WORK_DIR"   || die "unsafe work_dir"
validate_tool_choice "$PMN_TOOL"     || die "invalid profiling.tool"
validate_decimal "$PMN_KRK_CONF"     || die "invalid kraken_confidence"
validate_uint "$PMN_KRK_MINREADS"    || die "invalid bracken_min_reads"
validate_decimal "$PMN_THRESHOLD"    || die "invalid abundance_threshold_pct"
validate_uint "$PMN_THREADS"         || die "invalid threads"
validate_yesno "$PMN_FILTER_HUMAN"   || die "invalid filter_human"
validate_in_set "$PMN_HOST_PRESET" very-sensitive very-sensitive-local || die "invalid host_sensitivity (very-sensitive|very-sensitive-local)"
validate_yesno "$PMN_KEEP_TRIMMED"   || die "invalid cleanup.keep_trimmed"
validate_yesno "$PMN_KEEP_HOST_READS" || die "invalid cleanup.keep_host_reads"
validate_in_set "$PMN_LAYOUT" managed custom || die "invalid paths.layout (managed|custom)"
validate_yesno "$PMN_AUTO_INSTALL_DB" || die "invalid profiling.auto_install_db"
validate_db_mode "$PMN_KRK_DB_MODE"   || die "invalid profiling.kraken_db_mode (standard|custom)"
validate_uint "$PMN_BRACKEN_READLEN"  || die "invalid profiling.bracken_readlen"
validate_yesno "$PMN_DO_REPORT"       || die "invalid analysis.report"
validate_yesno "$PMN_DO_DIVERSITY"    || die "invalid analysis.diversity"
{ [ -z "$PMN_METADATA" ] || validate_path_safe "$PMN_METADATA"; } || die "unsafe analysis.metadata"
{ [ -z "$PMN_GROUP_COL" ] || validate_name "$PMN_GROUP_COL"; }    || die "invalid analysis.group_col"
validate_yesno "$PMN_STRAIN_ON"       || die "invalid analysis.strainphlan.enabled"
if [ "$PMN_STRAIN_ON" = "yes" ]; then
  { [ "$PMN_TOOL" = "metaphlan" ] || [ "$PMN_TOOL" = "both" ]; } \
    || die "analysis.strainphlan needs profiling.tool metaphlan or both"
  [ -n "$PMN_STRAIN_SPECIES" ] || die "analysis.strainphlan.enabled is true but analysis.strainphlan.species is empty"
  read -ra PMN_STRAIN_ARR <<< "$PMN_STRAIN_SPECIES"
  for _sp in "${PMN_STRAIN_ARR[@]}"; do
    [[ "$_sp" =~ ^[A-Z][a-z]+_[a-z0-9_]+$ ]] || die "invalid strainphlan species (use Genus_species): $(sanitize_for_log "$_sp")"
  done
fi
# Kraken with the full PlusPF database memory-maps 118 GB and reads scattered pieces: with a large disk read-ahead
# every piece costs megabytes (S2.2, K2: ~108 h estimated at 8192 KB, 41 min at 16 KB, identical output). The engine's
# WSL sets 16 KB at every start (installer/windows/prepara_pmn.sh); elsewhere it needs root, so only a warning here.
if [ "$PMN_KRK_PROFILO" = completo ] && [ -n "$PMN_KRK_DB" ] && { [ "$PMN_TOOL" = "kraken" ] || [ "$PMN_TOOL" = "both" ]; }; then
  ra_dev="$(basename "$(findmnt -no SOURCE --target "$PMN_KRK_DB" 2> /dev/null)")"
  [ -e "/sys/class/block/$ra_dev/queue" ] || ra_dev="$(lsblk -no PKNAME "/dev/$ra_dev" 2> /dev/null | head -n1)"
  ra_file="/sys/class/block/$ra_dev/queue/read_ahead_kb"
  if [ -n "$ra_dev" ] && [ -r "$ra_file" ] && [ "$(cat "$ra_file")" -gt 16 ]; then
    warn "$(say "Disk read-ahead is $(cat "$ra_file") KB: Kraken with the full PlusPF was measured fast only at 16 KB (41 min for 1.5 M pairs; at 8192 KB it would take days). Set it with: echo 16 | sudo tee $ra_file, or use motore.kraken_db: rapido." \
               "La lettura anticipata del disco è $(cat "$ra_file") KB: Kraken con PlusPF completo è stato misurato veloce solo a 16 KB (41 min per 1,5 M di coppie; a 8.192 KB servirebbero giorni). Impostala con: echo 16 | sudo tee $ra_file, oppure usa motore.kraken_db: rapido.")"
  fi
fi
# MetaPhlAn mode (D016; contract section 5.1). "fette" = the 6 slices of the index (peak ~8.5 GB),
# only with the desktop engine. "standard" = MetaPhlAn on the full index (~33 GB of RAM).
# auto: standard if the PC has >= 40 GB and the full index is there, else fette when installed.
if [ "$PMN_TOOL" = "metaphlan" ] || [ "$PMN_TOOL" = "both" ]; then
  if [ "$PMN_MPA_MODO" = auto ]; then
    ram_gb="$(awk '/^MemTotal:/ { printf "%d", $2 / 1048576 }' /proc/meminfo)"
    if [ "$ram_gb" -ge 40 ] && compgen -G "${PMN_MPA_DB:-/nonexistent}/${PMN_MPA_INDEX}*.1.bt2l" > /dev/null; then PMN_MPA_MODO=standard
    elif [ -n "$PMN_FETTE" ]; then PMN_MPA_MODO=fette
    else PMN_MPA_MODO=standard; fi
  fi
  if [ "$PMN_MPA_MODO" = fette ]; then
    [ -n "$PMN_FETTE" ] || die "motore.metaphlan_modo: fette needs the installed engine (PMN_FETTE in installazione.env)"
    [ "$PMN_STRAIN_ON" = "no" ] || die "analysis.strainphlan needs motore.metaphlan_modo: standard (the slices keep no alignment file)"
  fi
else
  PMN_MPA_MODO=none
fi
validate_yesno "$PMN_BIOMNI_ON"       || die "invalid analysis.biomni.enabled"
validate_walltime "$PMN_PBS_WALLTIME" || die "invalid execution.pbs_walltime (use HH:MM:SS)"
validate_mem "$PMN_PBS_MEM"           || die "invalid execution.pbs_mem (e.g. 32GB)"
validate_pbs_select "$PMN_PBS_SELECT" || die "invalid execution.pbs_select"
{ [ -z "$PMN_PBS_QUEUE" ] || validate_name "$PMN_PBS_QUEUE"; } || die "invalid execution.pbs_queue"
{ [ -z "$PMN_MPA_DB" ] || validate_path_safe "$PMN_MPA_DB"; } || die "unsafe profiling.metaphlan_db"
validate_name "$PMN_MPA_INDEX" && [ "$PMN_MPA_INDEX" != "latest" ] \
  || die "profiling.metaphlan_index must name a DB version (e.g. mpa_vJan25_CHOCOPhlAnSGB_202503), not 'latest'"
{ [ -z "$PMN_KRK_DB" ] || validate_path_safe "$PMN_KRK_DB"; } || die "unsafe profiling.kraken_db"
# numeric bounds (validate_decimal only checks the format; clamp the meaningful range)
awk -v v="$PMN_KRK_CONF"  'BEGIN{exit !(v>=0 && v<=1)}'   || die "kraken_confidence must be between 0 and 1"
awk -v v="$PMN_THRESHOLD" 'BEGIN{exit !(v>=0 && v<=100)}' || die "abundance_threshold_pct must be between 0 and 100"
validate_yesno "$PMN_TRIAGE_ON"       || die "invalid triage.enabled"
if [ "$PMN_TRIAGE_ON" = "yes" ]; then
  validate_uint "$PMN_TRIAGE_READS" && [ "$PMN_TRIAGE_READS" -gt 0 ] || die "triage.reads must be a positive integer"
  validate_decimal "$PMN_TRIAGE_MAX_HOST" && awk -v v="$PMN_TRIAGE_MAX_HOST" 'BEGIN{exit !(v>=0 && v<100)}' \
    || die "triage.max_host_pct must be >= 0 and < 100"
  validate_uint "$PMN_TRIAGE_MIN_READS" || die "triage.min_nonhost_reads must be a non-negative integer"
  validate_decimal "$PMN_TRIAGE_MIN_Q30" && awk -v v="$PMN_TRIAGE_MIN_Q30" 'BEGIN{exit !(v>=0 && v<=100)}' \
    || die "triage.min_q30_pct must be between 0 and 100"
  validate_in_set "$PMN_TRIAGE_ACTION" report skip || die "invalid triage.action (report|skip)"
fi

case "$PMN_SCHED_CHOICE" in
  auto)      PMN_SCHED="$(detect_scheduler)" ;;
  pbs|local) PMN_SCHED="$PMN_SCHED_CHOICE" ;;
  *) die "invalid scheduler: $(sanitize_for_log "$PMN_SCHED_CHOICE")" ;;
esac
# On PBS the queue is mandatory (asked at the start); fail fast with a clear message.
if [ "$PMN_SCHED" = "pbs" ] && [ -z "$PMN_PBS_QUEUE" ]; then
  die "scheduler=pbs requires execution.pbs_queue in config.yaml (the queue name of your PBS cluster)"
fi
export PMN_SCHED PMN_THREADS PMN_CONDA_BASE
export PMN_PBS_QUEUE PMN_PBS_WALLTIME PMN_PBS_MEM PMN_PBS_SELECT

# --- directories ---
# layout=managed: the tool owns every folder under work_dir.
# layout=custom : use the user-provided dirs where given, else fall back to the managed default.
resolve_dir() {  # resolve_dir <outvar> <custom_value> <managed_default>
  local __var="$1" v="$2" d="$3"
  if [ "$PMN_LAYOUT" = "custom" ] && [ -n "$v" ]; then
    validate_path_safe "$v" || die "unsafe custom path: $(sanitize_for_log "$v")"
    printf -v "$__var" '%s' "$v"
  else
    printf -v "$__var" '%s' "$d"
  fi
}
resolve_dir RAW_DIR     "$PMN_RAW_DIR"     "$PMN_WORK_DIR/raw"
resolve_dir TRIM_DIR    "$PMN_TRIM_DIR"    "$PMN_WORK_DIR/trim"
resolve_dir NONHOST_DIR "$PMN_NONHOST_DIR" "$PMN_WORK_DIR/nonhost"
resolve_dir RES_DIR     "$PMN_RESULTS_DIR" "$PMN_WORK_DIR/results"
resolve_dir PMN_LOG_DIR "$PMN_LOGS_DIR"    "$PMN_WORK_DIR/logs"
QC_DIR="$PMN_WORK_DIR/multiqc"
REF_DIR="$PMN_WORK_DIR/host_index"
MPA_DIR="$PMN_WORK_DIR/metaphlan"
KRK_DIR="$PMN_WORK_DIR/kraken"
if [ -n "$PMN_HOST_READS_DIR" ]; then
  validate_path_safe "$PMN_HOST_READS_DIR" || die "unsafe cleanup.host_reads_dir"
  HOST_READS_DIR="$PMN_HOST_READS_DIR"
else
  HOST_READS_DIR="$PMN_WORK_DIR/host_reads"
fi
# Per-pass Bowtie2 host-removal logs (parsed by MultiQC). Under work_dir so step 22 always scans it.
HF_LOG_DIR="$PMN_WORK_DIR/hostfilter_logs"
export PMN_LOG_DIR
mkdir -p "$PMN_WORK_DIR" "$PMN_LOG_DIR" "$RES_DIR" || die "cannot create work dir"
# Temporary files on disk (WSL keeps /tmp in RAM): the engine's PMN_TMP, else an existing TMPDIR
# (cluster scratch), else under work_dir.
if [ -z "$PMN_ENVS" ] && [ -z "${TMPDIR:-}" ]; then
  mkdir -p "$PMN_WORK_DIR/tmp" || die "cannot create $PMN_WORK_DIR/tmp"
  TMPDIR="$(cd "$PMN_WORK_DIR/tmp" && pwd)"; export TMPDIR
fi

# Call <callback> <sample> <r1> <r2|""> for every sample found in <dir>.
for_each_sample() {  # for_each_sample <dir> <callback>
  local d="$1" cb="$2" f s mate pair r1suf r2suf
  [ -d "$d" ] || { warn "reads dir not found (yet): $d"; return 0; }
  shopt -s nullglob
  # --- Paired-end (EN): recognise the common R1/R2 naming conventions, not just _1/_2.
  #     (IT): riconosci le convenzioni R1/R2 piu' comuni, non solo _1/_2.
  # Each entry is "R1-suffix|R2-suffix". The sample name is the FILENAME with the
  # R1-suffix stripped; the mate is the same path with the R1-suffix swapped for R2.
  # The default NCBI form (_1/_2.fastq.gz) stays first so existing batches behave identically.
  # Suffixes are distinct (e.g. *_R1.fastq.gz never also matches *_R1_001.fastq.gz),
  # so no file is picked up by two patterns.
  local PAIR_SUFFIXES=(
    "_1.fastq.gz|_2.fastq.gz"
    "_R1.fastq.gz|_R2.fastq.gz"
    "_R1_001.fastq.gz|_R2_001.fastq.gz"
    "_1.fq.gz|_2.fq.gz"
    "_R1.fq.gz|_R2.fq.gz"
  )
  for pair in "${PAIR_SUFFIXES[@]}"; do
    r1suf="${pair%%|*}"; r2suf="${pair##*|}"
    for f in "$d"/*"$r1suf"; do
      # derive mate + sample by stripping/swapping the R1 token in the FILENAME
      s="$(basename "${f%"$r1suf"}")"; mate="${f%"$r1suf"}$r2suf"
      validate_name "$s" || { warn "skip odd sample name from $f"; continue; }
      [ -f "$mate" ] || { warn "missing mate for $f"; continue; }
      "$cb" "$s" "$f" "$mate"
    done
  done
  # --- Single-end (EN): any *.fastq.gz / *.fq.gz that is NOT one of the paired mates above.
  #     (IT): qualsiasi *.fastq.gz / *.fq.gz che NON sia un mate di una coppia gia' gestita.
  for f in "$d"/*.fastq.gz "$d"/*.fq.gz; do
    # exclude EVERY paired R1/R2 variant we recognise, so a paired file is never re-processed as single-end
    case "$f" in
      *_1.fastq.gz|*_2.fastq.gz|*_R1.fastq.gz|*_R2.fastq.gz|*_R1_001.fastq.gz|*_R2_001.fastq.gz|*_1.fq.gz|*_2.fq.gz|*_R1.fq.gz|*_R2.fq.gz) continue ;;
    esac
    s="$(basename "$f")"; s="${s%.fastq.gz}"; s="${s%.fq.gz}"
    validate_name "$s" || continue
    "$cb" "$s" "$f" ""
  done
  shopt -u nullglob
}

# Outputs made with other parameters are redone, not reused (D022, P01 of 22/10): the steps skip a sample when its
# output exists, whatever produced it. One stamp per folder with the parameters of its files; the host stamp is part
# of the profile stamps (other hosts = other reads). Only for the phases and methods that run (a MetaPhlAn-only run
# keeps the Kraken stamp); the threshold needs nothing (Phase B tables are always redone). Never in a dry run.
# Con layout custom NONHOST_DIR è scelta dall'utente e può servire a più progetti (revisione del 22/10): si toccano
# solo le uscite dei campioni del progetto (codici di srr_list e read locali), ognuno col suo timbro accanto ai file,
# perché lo stesso campione può stare in due progetti con ospiti diversi; il timbro del progetto, che legge la Fase B,
# sta nella sua cartella di lavoro. I percorsi entrano nei modelli con pmn_glob_quote: "nonhost[2024]" non è un
# modello che trova "nonhost2". MetaPhlAn e Kraken sono sempre sotto work_dir.
NONHOST_TIMBRO="$NONHOST_DIR/.parametri"
[ "$NONHOST_DIR" = "$PMN_WORK_DIR/nonhost" ] || NONHOST_TIMBRO="$PMN_WORK_DIR/.parametri_nonhost"
stampa_campione() { printf '%s\n' "$1"; }
campioni_del_progetto() {
  local srr
  if [ "$PMN_DATA_SOURCE" != local ] && [ -f "$PMN_SRR_LIST" ]; then
    while IFS= read -r srr || [ -n "$srr" ]; do   # anche l'ultima riga senza a capo
      srr="${srr%%[[:space:]]*}"
      if validate_srr "$srr"; then printf '%s\n' "$srr"; fi
    done < "$PMN_SRR_LIST"
  fi
  if [ "$PMN_DATA_SOURCE" != ncbi ] && [ -d "$PMN_LOCAL_READS" ]; then for_each_sample "$PMN_LOCAL_READS" stampa_campione; fi
}
mapfile -t PMN_CAMPIONI < <(campioni_del_progetto 2> /dev/null)   # gli avvisi sui nomi delle read li dà la Fase A
# Completo solo se si leggono tutte le sue fonti (srr_list mancante, disco delle read non montato: no). Solo allora
# le fasi lavorano sui soli campioni del progetto e si tolgono le uscite degli altri; se no, come prima.
PMN_ELENCO_COMPLETO=1
{ [ "$PMN_DATA_SOURCE" = local ] || [ -f "$PMN_SRR_LIST" ]; } || PMN_ELENCO_COMPLETO=0
{ [ "$PMN_DATA_SOURCE" = ncbi ] || [ -d "$PMN_LOCAL_READS" ]; } || PMN_ELENCO_COMPLETO=0
[ "${#PMN_CAMPIONI[@]}" -gt 0 ] || PMN_ELENCO_COMPLETO=0
# both: una cartella locale vuota (disco non montato su una cartella che esiste) non è una fonte letta
if [ "$PMN_DATA_SOURCE" = both ] && [ -z "$(for_each_sample "$PMN_LOCAL_READS" stampa_campione 2> /dev/null)" ]; then
  PMN_ELENCO_COMPLETO=0
fi
del_progetto() { local c; for c in ${PMN_CAMPIONI[@]+"${PMN_CAMPIONI[@]}"}; do [ "$c" = "$1" ] && return 0; done; return 1; }
QW="$(pmn_glob_quote "$PMN_WORK_DIR")"; QN="$(pmn_glob_quote "$NONHOST_DIR")"; QH="$(pmn_glob_quote "$HF_LOG_DIR")"
QM="$(pmn_glob_quote "$MPA_DIR")"; QK="$(pmn_glob_quote "$KRK_DIR")"; QR="$(pmn_glob_quote "$RES_DIR")"
if [ "$DRY" -eq 0 ]; then
  if [ "$PHASE" = "all" ] || [ "$PHASE" = "a" ]; then
    ospite_timbro="$(printf 'hosts=%s\nfilter_human=%s\nhost_sensitivity=%s' "$PMN_HOSTS" "$PMN_FILTER_HUMAN" "$PMN_HOST_PRESET")"
    rifatti=1
    if [ "$NONHOST_TIMBRO" = "$NONHOST_DIR/.parametri" ]; then
      pmn_rifai_se_cambiati "$NONHOST_TIMBRO" "$ospite_timbro" \
          "$QN/*_nonhost*.fastq.gz" "$QH/*.bowtie2.log" "$QW/triage/*.triage_host.tsv" && rifatti=0
    else
      # read di un campione rifatte = rifatti anche i suoi profili, di qualunque corsa siano (altro ospite)
      for s in ${PMN_CAMPIONI[@]+"${PMN_CAMPIONI[@]}"}; do
        qs="$(pmn_glob_quote "$s")"
        pmn_rifai_se_cambiati "$NONHOST_DIR/.$s.parametri" "$ospite_timbro" \
            "$QN/${qs}_nonhost_1.fastq.gz" "$QN/${qs}_nonhost_2.fastq.gz" "$QN/${qs}_nonhost.fastq.gz" \
            "$QH/$qs.*.bowtie2.log" "$QW/triage/$qs.triage_host.tsv" \
            "$QM/${qs}_profile.txt" "$QM/$qs.mapout" "$QM/$qs.bowtie2.bz2" "$QM/$qs.sam.bz2" \
            "$QK/$qs.bracken" "$QK/$qs.k2report" "$QK/${qs}_bracken_species.k2report" "$QK/$qs.k2out" \
            "$QR/alpha_metaphlan_pari/${qs}_profile.txt" "$QR/alpha_metaphlan_pari/$qs.mapout" && rifatti=0
      done
      printf '%s\n' "$ospite_timbro" > "$NONHOST_TIMBRO" || die "cannot write $NONHOST_TIMBRO"
    fi
    [ "$rifatti" -eq 0 ] \
      && warn "$(say "Host removal parameters changed (or not recorded): host removal, MetaPhlAn and Kraken are redone" \
                     "Parametri della rimozione dell'ospite cambiati (o non registrati): rifaccio ospite, MetaPhlAn e Kraken")"
  fi
  if [ "$PHASE" = "all" ] || [ "$PHASE" = "b" ]; then
    ospite_timbro="$(cat "$NONHOST_TIMBRO" 2> /dev/null || true)"
    if [ "$PMN_TOOL" = "metaphlan" ] || [ "$PMN_TOOL" = "both" ]; then
      # results_dir personalizzata: può essere di più progetti, dei sottocampioni pari si tolgono solo quelli del
      # progetto (profilo e .mapout: un .mapout rimasto si riuserebbe coi parametri vecchi)
      mpa_uscite=("$QM/*_profile.txt" "$QM/*.bowtie2.bz2" "$QM/*.sam.bz2" "$QM/*.mapout")
      if [ "$RES_DIR" = "$PMN_WORK_DIR/results" ]; then mpa_uscite+=("$QR/alpha_metaphlan_pari")
      else
        for s in ${PMN_CAMPIONI[@]+"${PMN_CAMPIONI[@]}"}; do
          qs="$(pmn_glob_quote "$s")"
          mpa_uscite+=("$QR/alpha_metaphlan_pari/${qs}_profile.txt" "$QR/alpha_metaphlan_pari/$qs.mapout")
        done
      fi
      pmn_rifai_se_cambiati "$MPA_DIR/.parametri" \
          "$(printf '%s\nmetaphlan_mode=%s\nmetaphlan_index=%s' "$ospite_timbro" "$PMN_MPA_MODO" "$PMN_MPA_INDEX")" \
          "${mpa_uscite[@]}" \
        && warn "$(say "MetaPhlAn parameters changed (or not recorded): the MetaPhlAn profiles are redone" \
                       "Parametri di MetaPhlAn cambiati (o non registrati): rifaccio i profili di MetaPhlAn")"
    fi
    if [ "$PMN_TOOL" = "kraken" ] || [ "$PMN_TOOL" = "both" ]; then
      # the database by its real path (a trailing slash or a symlink is the same database)
      pmn_rifai_se_cambiati "$KRK_DIR/.parametri" \
          "$(printf '%s\nkraken_db=%s\nkraken_confidence=%s\nbracken_min_reads=%s\nbracken_readlen=%s' "$ospite_timbro" \
             "${PMN_KRK_DB:+$(realpath -m -- "$PMN_KRK_DB")}" "$PMN_KRK_CONF" "$PMN_KRK_MINREADS" "$PMN_BRACKEN_READLEN")" \
          "$QK/*.bracken" "$QK/*.k2report" "$QK/*.k2out" \
        && warn "$(say "Kraken parameters changed (or not recorded): the Kraken profiles are redone" \
                       "Parametri di Kraken cambiati (o non registrati): rifaccio i profili di Kraken")"
    fi
  fi
fi

# The parameters actually used, next to the results (D022: the report says what produced the numbers).
# Only those of the methods that run (22/10): no Kraken threshold or database with MetaPhlAn alone.
{
  printf 'parameter\tvalue\n'
  if [ "$PMN_TOOL" = "metaphlan" ] || [ "$PMN_TOOL" = "both" ]; then
    printf 'metaphlan_mode\t%s\nmetaphlan_index\t%s\n' "$PMN_MPA_MODO" "$PMN_MPA_INDEX"
  fi
  if [ "$PMN_TOOL" = "kraken" ] || [ "$PMN_TOOL" = "both" ]; then
    printf 'kraken_db\t%s\nkraken_profile\t%s\nkraken_confidence\t%s\n' "$PMN_KRK_DB" "$PMN_KRK_PROFILO" "$PMN_KRK_CONF"
    printf 'bracken_min_reads\t%s\nbracken_readlen\t%s\nabundance_threshold_pct\t%s\n' "$PMN_KRK_MINREADS" "$PMN_BRACKEN_READLEN" "$PMN_THRESHOLD"
  fi
  printf 'hosts\t%s\nfilter_human\t%s\n' "$PMN_HOSTS" "$PMN_FILTER_HUMAN"
} > "$RES_DIR/parameters.tsv"

# Result matrix paths: computed unconditionally (not just inside Phase B) so Phase C can
# find them when run standalone via --phase c, after an earlier Phase B run produced them.
MPA_MERGED=""; KRK_MATRIX=""
if [ "$PMN_TOOL" = "metaphlan" ] || [ "$PMN_TOOL" = "both" ]; then MPA_MERGED="$RES_DIR/metaphlan_merged.tsv"; fi
if [ "$PMN_TOOL" = "kraken" ]    || [ "$PMN_TOOL" = "both" ]; then KRK_MATRIX="$RES_DIR/kraken_matrix.tsv"; fi

say "=== profilemetananni - run ($PMN_PROJECT) ===" "=== profilemetananni - run ($PMN_PROJECT) ==="
info "$(say "Scheduler: $PMN_SCHED | tool: $PMN_TOOL | threads: $PMN_THREADS" "Scheduler: $PMN_SCHED | tool: $PMN_TOOL | thread: $PMN_THREADS")"

# --- helper: run or just print a step ---
do_step() {
  if [ "$DRY" -eq 1 ]; then
    local lbl="$2"; info "DRY-RUN step: $lbl"; return 0
  fi
  # A failed step aborts the pipeline (fail-fast) instead of continuing on stale output.
  pmn_run "$@" || die "step failed: $2"
}

# --- preflight ---
# (the desktop engine is checked by installer/verifica_motore.sh instead: no conda to look at)
if [ "$SKIP_PREFLIGHT" -eq 0 ] && [ "$DRY" -eq 0 ] && [ -z "$PMN_ENVS" ]; then
  pf_args=(--lang "$PMN_LANG")
  [ -n "$PMN_MPA_DB" ] && pf_args+=(--db-metaphlan "$PMN_MPA_DB")
  [ -n "$PMN_KRK_DB" ] && pf_args+=(--db-kraken "$PMN_KRK_DB")
  [ "$PMN_BIOMNI_ON" = "yes" ] && pf_args+=(--biomni)
  bash "$PMN_ROOT/bin/preflight.sh" "${pf_args[@]}" \
    || die "preflight failed: install the missing environments (bin/preflight.sh --install)"
fi

# ============================ PHASE A — preprocessing ============================
if [ "$PHASE" = "all" ] || [ "$PHASE" = "a" ]; then

# A1. NCBI: estimate size (GATE) then download.
if [ "$PMN_DATA_SOURCE" = "ncbi" ] || [ "$PMN_DATA_SOURCE" = "both" ]; then
  [ -n "$PMN_SRR_LIST" ] || die "data_source includes 'ncbi' but paths.srr_list is empty"
  validate_path_safe "$PMN_SRR_LIST" || die "unsafe srr_list path"
  [ -f "$PMN_SRR_LIST" ] || die "srr_list not found: $(sanitize_for_log "$PMN_SRR_LIST")"
  pmn_strip_crlf "$PMN_SRR_LIST"

  info "$(say "Estimating download size before fetching ..." "Stimo la dimensione del download prima di scaricare ...")"
  do_step pmn_reports_py size -- python "$PMN_ROOT/steps/05_estimate_size.py" \
      --srr-list "$PMN_SRR_LIST" --out "$PMN_WORK_DIR/size" --work-dir "$PMN_WORK_DIR" \
    || die "size gate failed (not enough space, or unresolved accessions). Nothing was downloaded."

  while IFS= read -r srr || [ -n "$srr" ]; do   # anche l'ultima riga senza a capo
    srr="${srr%%[[:space:]]*}"
    [ -n "$srr" ] || continue
    case "$srr" in \#*) continue ;; esac
    validate_srr "$srr" || { warn "skipping invalid accession: $(sanitize_for_log "$srr")"; continue; }
    do_step pmn_download "dl_${srr}" -- bash "$PMN_ROOT/steps/10_download_sra.sh" \
      --srr "$srr" --out "$RAW_DIR" --threads "$PMN_THREADS"
  done < "$PMN_SRR_LIST"
fi

# Which directories hold the input reads.
READ_DIRS=()
case "$PMN_DATA_SOURCE" in
  ncbi)  READ_DIRS=("$RAW_DIR") ;;
  local) validate_path_safe "$PMN_LOCAL_READS" || die "unsafe local_reads_dir"
         [ -d "$PMN_LOCAL_READS" ] || die "local_reads_dir not found"
         READ_DIRS=("$PMN_LOCAL_READS") ;;
  both)  validate_path_safe "$PMN_LOCAL_READS" || die "unsafe local_reads_dir"
         [ -d "$PMN_LOCAL_READS" ] || die "local_reads_dir not found"
         READ_DIRS=("$RAW_DIR" "$PMN_LOCAL_READS") ;;
esac

# A2. Host index build. Human (grch38) is removed automatically by default; the user
# chooses the additional animal/substrate host(s) in 'hosts'. Index order = chosen
# hosts first, human last.
host_accession() { awk -F'\t' -v h="$1" '!/^#/ && $1==h {print $2; exit}' "$PMN_ROOT/refs/hosts.tsv" | tr -d '\r'; }

# Human reference for the automatic human-read removal (filter_human): GRCh38, as the published
# profiles (D021). T2T-CHM13v2.0 ("chm13" in refs/hosts.tsv) is the alternate: it removes more
# centromeric/satellite reads, but the profiles would no longer compare with the published ones.
PMN_HUMAN_HOST="grch38"

# Desktop engine: the hosts of D021 are installed already built in PMN_OSPITE (no download,
# no build on the user's PC). Prints the index prefix if installed.
host_installed() {
  local d="$1"
  [ -n "$PMN_OSPITE" ] || return 1
  [ "$d" = grch38 ] && d=homo_sapiens   # installed name of the GRCh38 index
  [ -s "$PMN_OSPITE/$d/$d.1.bt2" ] || return 1
  printf '%s' "$PMN_OSPITE/$d/$d"
}

INDEX_LIST=()
read -ra _PMN_HOST_ARR <<< "$PMN_HOSTS"   # split safely (no glob expansion)
for h in "${_PMN_HOST_ARR[@]}"; do
  [ -n "$h" ] || continue           # skip empty tokens (e.g. trailing spaces)
  case "$h" in grch38|chm13) continue ;; esac   # human handled separately via filter_human
  validate_name "$h" || die "invalid host name: $(sanitize_for_log "$h")"
  if ready="$(host_installed "$h")"; then INDEX_LIST+=("$ready"); continue; fi
  acc="$(host_accession "$h")"; [ -n "$acc" ] || die "no accession for host '$h' in refs/hosts.tsv"
  do_step pmn_hostfilter "idx_${h}" -- bash "$PMN_ROOT/steps/11_host_index.sh" \
    --host "$h" --accession "$acc" --out "$REF_DIR" --threads "$PMN_THREADS"
  INDEX_LIST+=("$REF_DIR/$h")
done
if [ "$PMN_FILTER_HUMAN" = "yes" ]; then
  if ready="$(host_installed "$PMN_HUMAN_HOST")"; then INDEX_LIST+=("$ready")
  else
    acc="$(host_accession "$PMN_HUMAN_HOST")"; [ -n "$acc" ] || die "no $PMN_HUMAN_HOST accession in refs/hosts.tsv"
    do_step pmn_hostfilter "idx_${PMN_HUMAN_HOST}" -- bash "$PMN_ROOT/steps/11_host_index.sh" \
      --host "$PMN_HUMAN_HOST" --accession "$acc" --out "$REF_DIR" --threads "$PMN_THREADS"
    INDEX_LIST+=("$REF_DIR/$PMN_HUMAN_HOST")
  fi
fi
[ "${#INDEX_LIST[@]}" -ge 1 ] || die "no host to filter against (set 'hosts' and/or filter_human: true)"

# A3. Per-sample trimming + host filtering.
hostfilter_sample() {  # hostfilter_sample <sample> <trim_r1> <trim_r2|"">
  local s="$1" t1="$2" t2="$3" idx
  local a=(--sample "$s" --in1 "$t1")
  [ -n "$t2" ] && a+=(--in2 "$t2")
  for idx in "${INDEX_LIST[@]}"; do a+=(--index "$idx"); done
  [ "$PMN_KEEP_HOST_READS" = "yes" ] && a+=(--host-out "$HOST_READS_DIR")
  a+=(--out "$NONHOST_DIR" --threads "$PMN_THREADS" --log-dir "$HF_LOG_DIR" --preset "$PMN_HOST_PRESET")
  # do_step aborts the pipeline if host filtering fails, so the cleanup below only ever
  # runs after a SUCCESSFUL host-filter (the trimmed reads are then safe to remove).
  do_step pmn_hostfilter "hf_${s}" -- bash "$PMN_ROOT/steps/21_hostfilter.sh" "${a[@]}"
  # disk hygiene: remove trimmed intermediates unless the user asked to keep them
  if [ "$DRY" -eq 0 ] && [ "$PMN_KEEP_TRIMMED" != "yes" ]; then
    rm -f "$t1"
    if [ -n "$t2" ]; then rm -f "$t2"; fi
  fi
  return 0
}

# A3a. Triage (optional): look at the first N fragments of a sample before trimming.
TRIAGE_DIR="$PMN_WORK_DIR/triage"
TRIAGE_TSV="$RES_DIR/triage.tsv"
triage_sample() {  # triage_sample <sample> <r1> <r2|"">
  local s="$1" r1="$2" r2="$3" idx
  [ "$PMN_ELENCO_COMPLETO" -eq 1 ] && ! del_progetto "$s" && return 0   # raw_dir condivisa: non i campioni altrui
  # already host-filtered = already past the point where triage could save work
  if [ -n "$r2" ]; then [ -s "$NONHOST_DIR/${s}_nonhost_1.fastq.gz" ] && return 0
  else [ -s "$NONHOST_DIR/${s}_nonhost.fastq.gz" ] && return 0; fi
  local q=(--sample "$s" --in1 "$r1") h=(--sample "$s" --in1 "$r1")
  [ -n "$r2" ] && { q+=(--in2 "$r2"); h+=(--in2 "$r2"); }
  for idx in "${INDEX_LIST[@]}"; do h+=(--index "$idx"); done
  q+=(--out "$TRIAGE_DIR" --reads "$PMN_TRIAGE_READS" --threads "$PMN_THREADS")
  h+=(--out "$TRIAGE_DIR" --reads "$PMN_TRIAGE_READS" --threads "$PMN_THREADS")
  do_step pmn_trim "tq_${s}" -- bash "$PMN_ROOT/steps/15_triage_qc.sh" "${q[@]}"
  do_step pmn_hostfilter "th_${s}" -- bash "$PMN_ROOT/steps/16_triage_host.sh" "${h[@]}"
}
triage_excluded() {  # true if triage.action=skip and the sample's suggested decision is "exclude"
  [ "$PMN_TRIAGE_ON" = "yes" ] && [ "$PMN_TRIAGE_ACTION" = "skip" ] && [ -f "$TRIAGE_TSV" ] || return 1
  awk -F'\t' -v s="$1" 'NR == 1 { for (i = 1; i <= NF; i++) if ($i == "decision") c = i; next }
                        c && $1 == s && $c == "exclude" { found = 1 } END { exit !found }' "$TRIAGE_TSV"
}

# A3b. Trimming + host filtering of one sample.
trim_and_filter_sample() {  # trim_and_filter_sample <sample> <r1> <r2|"">
  local s="$1" r1="$2" r2="$3"
  # raw_dir condivisa: le read degli altri progetti non si toccano (filtrate senza il loro timbro, revisione del 22/10)
  [ "$PMN_ELENCO_COMPLETO" -eq 1 ] && ! del_progetto "$s" && return 0
  # already fully host-filtered? skip trim+filter (avoids re-trimming when trimmed reads were cleaned up)
  if [ -n "$r2" ]; then [ -s "$NONHOST_DIR/${s}_nonhost_1.fastq.gz" ] && return 0
  else [ -s "$NONHOST_DIR/${s}_nonhost.fastq.gz" ] && return 0; fi
  if triage_excluded "$s"; then
    warn "$(say "$s skipped: triage suggested 'exclude' (see $TRIAGE_TSV; set triage.action: report to keep it)" \
               "$s saltato: il triage suggerisce 'exclude' (vedi $TRIAGE_TSV; metti triage.action: report per tenerlo)")"
    return 0
  fi
  if [ -n "$r2" ]; then
    do_step pmn_trim "trim_${s}" -- bash "$PMN_ROOT/steps/20_trim.sh" \
      --sample "$s" --in1 "$r1" --in2 "$r2" --out "$TRIM_DIR" --threads "$PMN_THREADS"
    hostfilter_sample "$s" "$TRIM_DIR/${s}_trim_1.fastq.gz" "$TRIM_DIR/${s}_trim_2.fastq.gz"
  else
    do_step pmn_trim "trim_${s}" -- bash "$PMN_ROOT/steps/20_trim.sh" \
      --sample "$s" --in1 "$r1" --out "$TRIM_DIR" --threads "$PMN_THREADS"
    hostfilter_sample "$s" "$TRIM_DIR/${s}_trim_1.fastq.gz" ""
  fi
}

if [ "$PMN_TRIAGE_ON" = "yes" ]; then
  info "$(say "Triage: first $PMN_TRIAGE_READS fragments of each sample (host, quality, yield) ..." \
             "Triage: primi $PMN_TRIAGE_READS frammenti di ogni campione (host, qualità, resa) ...")"
  for d in "${READ_DIRS[@]}"; do for_each_sample "$d" triage_sample; done
  if [ "$DRY" -eq 1 ] || compgen -G "$TRIAGE_DIR/*.triage_*" > /dev/null; then
    do_step pmn_reports_py triage -- python "$PMN_ROOT/steps/17_triage_report.py" \
      --in "$TRIAGE_DIR" --out "$TRIAGE_TSV" --max-host-pct "$PMN_TRIAGE_MAX_HOST" \
      --min-nonhost-reads "$PMN_TRIAGE_MIN_READS" --min-q30-pct "$PMN_TRIAGE_MIN_Q30" --lang "$PMN_LANG"
    [ "$PMN_TRIAGE_ACTION" = "report" ] && info "$(say "Triage table: $TRIAGE_TSV (action: report, no sample is skipped)." \
                                                     "Tabella di triage: $TRIAGE_TSV (action: report, nessun campione saltato).")"
  fi
fi

for d in "${READ_DIRS[@]}"; do for_each_sample "$d" trim_and_filter_sample; done

# A4. MultiQC.
do_step pmn_qc multiqc -- bash "$PMN_ROOT/steps/22_multiqc.sh" --in "$PMN_WORK_DIR" --out "$QC_DIR" --title "$PMN_PROJECT"
info "$(say "Phase A done. Review the MultiQC report in $QC_DIR before interpreting." "Fase A finita. Guarda il report MultiQC in $QC_DIR prima di interpretare.")"

fi

# ============================ PHASE B prep — databases ============================
if [ "$PHASE" = "all" ] || [ "$PHASE" = "b" ]; then
# If a DB path is empty, either auto-build it (auto_install_db: true = the user's explicit
# confirmation for the large download) or stop with a clear manual instruction.
DB_DIR="$PMN_WORK_DIR/db"
if [ "$PMN_TOOL" = "metaphlan" ] || [ "$PMN_TOOL" = "both" ]; then
  if [ -z "$PMN_MPA_DB" ]; then
    if [ "$PMN_AUTO_INSTALL_DB" = "yes" ]; then
      PMN_MPA_DB="$DB_DIR/metaphlan"
      do_step pmn_metaphlan db_metaphlan -- bash "$PMN_ROOT/steps/13_metaphlan_db.sh" --out "$PMN_MPA_DB" --index "$PMN_MPA_INDEX"
    elif [ "$DRY" -eq 1 ]; then
      warn "$(say "DRY-RUN: MetaPhlAn DB not set; a real run would stop here (set profiling.metaphlan_db or auto_install_db: true)." "DRY-RUN: DB MetaPhlAn non impostato; una run reale si fermerebbe qui (imposta profiling.metaphlan_db o auto_install_db: true).")"
    else
      die "MetaPhlAn DB not set (profiling.metaphlan_db) and auto_install_db=false. Set the path, or set auto_install_db: true. Manual: conda run -n pmn_metaphlan metaphlan --install --db_dir <DIR> --index $PMN_MPA_INDEX"
    fi
  fi
fi
if [ "$PMN_TOOL" = "kraken" ] || [ "$PMN_TOOL" = "both" ]; then
  if [ -z "$PMN_KRK_DB" ]; then
    if [ "$PMN_AUTO_INSTALL_DB" = "yes" ]; then
      PMN_KRK_DB="$DB_DIR/kraken"
      kdb_args=(--out "$PMN_KRK_DB" --mode "$PMN_KRK_DB_MODE" --threads "$PMN_THREADS" --readlen "$PMN_BRACKEN_READLEN")
      if [ "$PMN_KRK_DB_MODE" = "custom" ]; then
        [ -n "$PMN_KRK_CUSTOM_GENOMES" ] || die "kraken_db_mode=custom requires profiling.kraken_custom_genomes (file of NCBI accessions)"
        validate_path_safe "$PMN_KRK_CUSTOM_GENOMES" || die "unsafe kraken_custom_genomes path"
        kdb_args+=(--genomes "$PMN_KRK_CUSTOM_GENOMES")
      fi
      do_step pmn_kraken db_kraken -- bash "$PMN_ROOT/steps/12_kraken_db.sh" "${kdb_args[@]}"
    elif [ "$DRY" -eq 1 ]; then
      warn "$(say "DRY-RUN: Kraken2 DB not set; a real run would stop here (set profiling.kraken_db or auto_install_db: true)." "DRY-RUN: DB Kraken2 non impostato; una run reale si fermerebbe qui (imposta profiling.kraken_db o auto_install_db: true).")"
    else
      die "Kraken2 DB not set (profiling.kraken_db) and auto_install_db=false. Set the path, or set auto_install_db: true. See steps/12_kraken_db.sh for the manual build."
    fi
  fi
fi

# ============================ PHASE B — read-based profiling ============================

run_profilers() {  # run_profilers <sample> <r1> <r2|"">
  local s="$1" r1="$2" r2="$3" a
  if [ "$PMN_MPA_MODO" = fette ]; then
    # MetaPhlAn on the 6 slices (motore/, D012, D028): profile and mapout land in $MPA_DIR
    if [ -s "$MPA_DIR/${s}_profile.txt" ]; then
      ok "$(say "$s already profiled (MetaPhlAn) -> skip" "$s già profilato (MetaPhlAn) -> salto")"
    else
      mkdir -p "$MPA_DIR" || die "cannot create $MPA_DIR"
      do_step pmn_metaphlan "mpa_${s}" -- bash "$PMN_ROOT/motore/metaphlan_fette.sh" "$s" "$r1" "$r2" "$MPA_DIR" "$PMN_THREADS"
    fi
  elif [ "$PMN_TOOL" = "metaphlan" ] || [ "$PMN_TOOL" = "both" ]; then
    a=(--sample "$s" --in1 "$r1"); [ -n "$r2" ] && a+=(--in2 "$r2")
    [ -n "$PMN_MPA_DB" ] && a+=(--db "$PMN_MPA_DB")
    a+=(--index "$PMN_MPA_INDEX")
    [ "$PMN_STRAIN_ON" = "yes" ] && a+=(--samout)
    a+=(--out "$MPA_DIR" --threads "$PMN_THREADS")
    do_step pmn_metaphlan "mpa_${s}" -- bash "$PMN_ROOT/steps/30_metaphlan.sh" "${a[@]}"
  fi
  if [ "$PMN_TOOL" = "kraken" ] || [ "$PMN_TOOL" = "both" ]; then
    if [ -z "$PMN_KRK_DB" ] && [ "$DRY" -eq 0 ]; then
      die "profiling.tool includes kraken but profiling.kraken_db is empty"
    fi
    a=(--sample "$s" --in1 "$r1"); [ -n "$r2" ] && a+=(--in2 "$r2")
    a+=(--db "$PMN_KRK_DB" --out "$KRK_DIR" --threads "$PMN_THREADS" --confidence "$PMN_KRK_CONF" --readlen "$PMN_BRACKEN_READLEN" --min-reads "$PMN_KRK_MINREADS")
    do_step pmn_kraken "krk_${s}" -- bash "$PMN_ROOT/steps/32_kraken_bracken.sh" "${a[@]}"
  fi
  return 0
}

# Only the samples of the project (revisione del 22/10): a shared nonhost folder holds other projects' samples, and the
# outputs of samples taken out of the project would end in the merged tables, the beta and the depth of step 42.
# An incomplete sample list keeps the old behaviour (every sample in the folder, nothing removed).
# Custom nonhost folder: reads redone by another project with other host parameters are not profiled.
if [ "$PMN_ELENCO_COMPLETO" -eq 1 ]; then
  [ "$DRY" -eq 0 ] && pmn_togli_campioni_tolti "$MPA_DIR" "$KRK_DIR" "${PMN_CAMPIONI[@]}"
  for s in "${PMN_CAMPIONI[@]}"; do
    if [ "$DRY" -eq 0 ] && [ "$NONHOST_TIMBRO" != "$NONHOST_DIR/.parametri" ] && [ -f "$NONHOST_DIR/.$s.parametri" ] \
       && [ "$(cat "$NONHOST_DIR/.$s.parametri")" != "$(cat "$NONHOST_TIMBRO" 2> /dev/null)" ]; then
      warn "$(say "$s: its host-free reads were made with other host parameters (another project?): not profiled, run Phase A again" \
                  "$s: le read senza ospite sono state fatte con altri parametri dell'ospite (un altro progetto?): non lo profilo, rifai la Fase A")"
      continue
    fi
    if [ -s "$NONHOST_DIR/${s}_nonhost_1.fastq.gz" ]; then
      run_profilers "$s" "$NONHOST_DIR/${s}_nonhost_1.fastq.gz" "$NONHOST_DIR/${s}_nonhost_2.fastq.gz"
    elif [ -s "$NONHOST_DIR/${s}_nonhost.fastq.gz" ]; then
      run_profilers "$s" "$NONHOST_DIR/${s}_nonhost.fastq.gz" ""
    fi
  done
elif [ -d "$NONHOST_DIR" ] || [ "$DRY" -eq 1 ]; then
  shopt -s nullglob
  for f in "$NONHOST_DIR"/*_nonhost_1.fastq.gz; do
    s="$(basename "${f%_nonhost_1.fastq.gz}")"
    run_profilers "$s" "$f" "${f%_nonhost_1.fastq.gz}_nonhost_2.fastq.gz"
  done
  for f in "$NONHOST_DIR"/*_nonhost.fastq.gz; do
    s="$(basename "${f%_nonhost.fastq.gz}")"
    run_profilers "$s" "$f" ""
  done
  shopt -u nullglob
fi

# B2. Merge / matrices.
MPA_MERGED=""; KRK_MATRIX=""
if [ "$PMN_TOOL" = "metaphlan" ] || [ "$PMN_TOOL" = "both" ]; then
  MPA_MERGED="$RES_DIR/metaphlan_merged.tsv"
  do_step pmn_metaphlan merge -- bash "$PMN_ROOT/steps/31_merge_metaphlan.sh" --in "$MPA_DIR" --out "$MPA_MERGED"
fi
# B2b. StrainPhlAn on the user's species list (optional).
if [ "$PMN_STRAIN_ON" = "yes" ]; then
  if [ -z "$PMN_MPA_DB" ] && [ "$DRY" -eq 0 ]; then
    die "analysis.strainphlan needs profiling.metaphlan_db (the folder with $PMN_MPA_INDEX.pkl)"
  fi
  strain_args=(--sam-dir "$MPA_DIR" --db "$PMN_MPA_DB" --index "$PMN_MPA_INDEX" --out "$RES_DIR/strainphlan" --threads "$PMN_THREADS")
  for _sp in "${PMN_STRAIN_ARR[@]}"; do strain_args+=(--species "$_sp"); done
  do_step pmn_metaphlan strainphlan -- bash "$PMN_ROOT/steps/35_strainphlan.sh" "${strain_args[@]}"
fi
if [ "$PMN_TOOL" = "kraken" ] || [ "$PMN_TOOL" = "both" ]; then
  KRK_MATRIX="$RES_DIR/kraken_matrix.tsv"
  # + the product taxa only (bacteria, archaea, fungi at or above the threshold, as in the report) for the beta diversity
  do_step pmn_reports_py kmatrix -- python "$PMN_ROOT/steps/33_kraken_matrix.py" --in "$KRK_DIR" --out "$KRK_MATRIX" \
    --taxa-out "$RES_DIR/kraken_matrix_taxa.tsv" --threshold-pct "$PMN_THRESHOLD"
fi

# B3. Overview report (comparison + all_taxa).
if [ "$PMN_DO_REPORT" = "yes" ]; then
  a=(--out "$RES_DIR/report_overview.xlsx" --threshold-pct "$PMN_THRESHOLD")
  [ -n "$MPA_MERGED" ] && a+=(--metaphlan "$MPA_MERGED")
  # Kraken: the product taxa only (bacteria, archaea, fungi), as in the report and the beta diversity (P28)
  [ -n "$KRK_MATRIX" ] && a+=(--kraken "$RES_DIR/kraken_matrix_taxa.tsv")
  do_step pmn_reports_py report -- python "$PMN_ROOT/steps/40_compare_report.py" "${a[@]}"
fi

# B4. Diversity (compositional CLR/Aitchison/PCA + alpha) per available matrix.
# Optional grouping: if a metadata TSV is given, colour the PCA by group and run
# Kruskal-Wallis + Dunn (BH) on alpha diversity across groups.
if [ "$PMN_DO_DIVERSITY" = "yes" ]; then
  DIV_ARGS=()
  # No abundance floor inside 41_diversity.R (--min-abundance 0): MetaPhlAn is never filtered, and the Kraken matrix
  # of the product taxa (step 33, kraken_matrix_taxa.tsv) is already at or above the threshold of % of the total assigned (22/10).
  if [ -n "$PMN_METADATA" ]; then
    [ -f "$PMN_METADATA" ] || die "analysis.metadata not found: $(sanitize_for_log "$PMN_METADATA")"
    [ -n "$PMN_GROUP_COL" ] || die "analysis.metadata is set but analysis.group_col is empty"
    pmn_strip_crlf "$PMN_METADATA"
    DIV_ARGS=(--metadata "$PMN_METADATA" --group-col "$PMN_GROUP_COL")
  fi
  # Alpha diversity at equal depth (R1): richness grows with the reads, so samples are compared at the depth of the
  # shallowest one. MetaPhlAn: the deeper samples get a random subsample of their reads (seed 1992, from the mapout)
  # and MetaPhlAn is re-run on it; Kraken: exact expected rarefaction of Bracken reads. One table per tool.
  ALPHA_ARGS=(--threshold-pct "$PMN_THRESHOLD" --out "$RES_DIR")
  if [ -n "$MPA_MERGED" ]; then
    PARI_DIR="$RES_DIR/alpha_metaphlan_pari"
    do_step pmn_reports_py alfa_sotto -- python "$PMN_ROOT/steps/42_alpha_equal_depth.py" sottocampiona --metaphlan-dir "$MPA_DIR" --out "$PARI_DIR"
    shopt -s nullglob
    for m in "$PARI_DIR"/*.mapout; do
      s="$(basename "$m" .mapout)"
      validate_name "$s" || die "invalid sample name: $(sanitize_for_log "$s")"
      [ "$PARI_DIR/${s}_profile.txt" -nt "$m" ] && continue   # already re-run on this subsample
      if [ "$PMN_MPA_MODO" = fette ]; then
        do_step pmn_metaphlan "alfa_mpa_${s}" -- bash "$PMN_ROOT/motore/metaphlan_da_mapout.sh" "$s" "$m" "$PARI_DIR" "$PMN_THREADS"
      else
        do_step pmn_metaphlan "alfa_mpa_${s}" -- metaphlan "$m" --input_type mapout --nproc "$PMN_THREADS" \
          ${PMN_MPA_DB:+--db_dir "$PMN_MPA_DB"} --index "$PMN_MPA_INDEX" --sample_id "$s" -o "$PARI_DIR/${s}_profile.txt"
      fi
    done
    shopt -u nullglob
    ALPHA_ARGS+=(--metaphlan-dir "$MPA_DIR" --pari-dir "$PARI_DIR")
  fi
  [ -n "$KRK_MATRIX" ] && ALPHA_ARGS+=(--kraken-dir "$KRK_DIR")
  do_step pmn_reports_py alfa -- python "$PMN_ROOT/steps/42_alpha_equal_depth.py" calcola "${ALPHA_ARGS[@]}"
  if [ -n "$MPA_MERGED" ]; then
    do_step pmn_reports_py mpa_matrix -- python "$PMN_ROOT/steps/34_metaphlan_matrix.py" --in "$MPA_MERGED" --out "$RES_DIR/metaphlan_matrix.tsv"
    do_step pmn_stats_r div_mpa -- Rscript "$PMN_ROOT/steps/41_diversity.R" --matrix "$RES_DIR/metaphlan_matrix.tsv" --out "$RES_DIR/diversity_metaphlan" --min-abundance 0 --alpha "$RES_DIR/alpha_diversity_metaphlan.tsv" ${DIV_ARGS[@]+"${DIV_ARGS[@]}"}
  fi
  if [ -n "$KRK_MATRIX" ]; then
    do_step pmn_stats_r div_krk -- Rscript "$PMN_ROOT/steps/41_diversity.R" --matrix "$RES_DIR/kraken_matrix_taxa.tsv" --out "$RES_DIR/diversity_kraken" --min-abundance 0 --alpha "$RES_DIR/alpha_diversity_kraken.tsv" ${DIV_ARGS[@]+"${DIV_ARGS[@]}"}
  fi
fi

fi

# ============================ PHASE C — taxa dossier (OPTIONAL) ============================
# Never submitted to PBS: compute nodes usually have no internet, and the Biomni data lake
# would eat the user's disk quota. Off by default; only species names ever leave the machine.
if [ "$PMN_BIOMNI_ON" = "yes" ] && { [ "$PHASE" = "all" ] || [ "$PHASE" = "c" ]; }; then
  if [ "$PMN_SCHED" = "pbs" ]; then
    info "$(say "Phase C skipped under PBS. Download the results and run: bash bin/run.sh --config <cfg> --phase c" \
             "Fase C saltata sotto PBS. Scarica i risultati e lancia: bash bin/run.sh --config <cfg> --phase c")"
  else
    validate_llm_name "$PMN_BIOMNI_LLM" || die "analysis.biomni.enabled is true but analysis.biomni.llm is invalid or empty"
    validate_uint "$PMN_BIOMNI_MAX"     || die "invalid analysis.biomni.max_taxa"
    awk -v v="$PMN_BIOMNI_MAX" 'BEGIN{exit !(v>=1 && v<=500)}' || die "analysis.biomni.max_taxa must be between 1 and 500"
    { [ -z "$PMN_BIOMNI_DATA" ] || validate_path_safe "$PMN_BIOMNI_DATA"; } || die "unsafe analysis.biomni.data_path"
    c=(--out "$RES_DIR/biomni_dossier" --llm "$PMN_BIOMNI_LLM" --work-dir "$PMN_WORK_DIR"
       --threshold-pct "$PMN_THRESHOLD" --max-taxa "$PMN_BIOMNI_MAX")
    [ -n "$PMN_BIOMNI_DATA" ] && c+=(--data-path "$PMN_BIOMNI_DATA")
    # Only pass a table that actually EXISTS: running --phase c before Phase B has produced
    # them would otherwise surface as a FileNotFoundError traceback.
    have_table=0
    if [ -n "$MPA_MERGED" ] && [ -f "$MPA_MERGED" ]; then c+=(--metaphlan "$MPA_MERGED"); have_table=1; fi
    if [ -n "$KRK_MATRIX" ] && [ -f "$KRK_MATRIX" ]; then c+=(--kraken "$KRK_MATRIX"); have_table=1; fi
    [ "$DRY" -eq 1 ] && c+=(--dry-run)
    [ "$YES_TAXA" -eq 1 ] && c+=(--yes-send-taxa)
    if [ "$have_table" -eq 0 ] && [ "$DRY" -eq 0 ]; then
      warn "$(say "Phase C skipped: no profiling table found in $RES_DIR. Run Phase B first, or check paths.results_dir." \
               "Fase C saltata: nessuna tabella di profiling in $RES_DIR. Lancia prima la Fase B, o controlla paths.results_dir.")"
    else
      # NOT via do_step, for two reasons: do_step short-circuits on --dry-run, which would
      # keep the step (and its "what would be sent" listing) from ever running; and do_step
      # aborts the pipeline on failure, while Phase C is the optional, network- and
      # LLM-dependent stage - its failure must not turn a finished Phase A/B run into a
      # failed one. It returns non-zero for ordinary situations too ("no taxa above the
      # threshold"), so warn and carry on.
      pmn_run pmn_biomni dossier -- python "$PMN_ROOT/steps/50_biomni_dossier.py" "${c[@]}" \
        || warn "$(say "Phase C did not complete (reason above). Phase A/B results are unaffected." \
                    "Fase C non completata (motivo qui sopra). I risultati di Fase A/B non sono toccati.")"
    fi
  fi
fi

ok "$(say "Pipeline complete. Results in $RES_DIR" "Pipeline completata. Risultati in $RES_DIR")"
info "$(say "Interpretation is human-guided: review the report and the diversity plots." "L'interpretazione è guidata dall'uomo: controlla il report e i grafici di diversità.")"
