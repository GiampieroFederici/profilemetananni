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

# --- locate conda; parse config safely (values are shlex-quoted -> safe to source) ---
detect_conda || die "conda/mamba not found (run bin/preflight.sh first)"
cfgfile="$(mktemp "${TMPDIR:-/tmp}/pmn_cfg.XXXXXX")" || die "mktemp failed"
trap 'rm -f "$cfgfile"' EXIT INT TERM
conda run --no-capture-output -n pmn_reports_py python "$PMN_ROOT/bin/lib/parse_config.py" "$CONFIG" > "$cfgfile" \
  || die "failed to parse config (is env pmn_reports_py installed?)"
# shellcheck disable=SC1090
. "$cfgfile"

# --- validate every value ---
validate_lang "$PMN_LANG"            || die "invalid language: $(sanitize_for_log "$PMN_LANG")"
export PMN_LANG
validate_source "$PMN_DATA_SOURCE"   || die "invalid data_source"
validate_name "$PMN_PROJECT"         || die "invalid project_name"
validate_path_safe "$PMN_WORK_DIR"   || die "unsafe work_dir"
validate_tool_choice "$PMN_TOOL"     || die "invalid profiling.tool"
validate_decimal "$PMN_KRK_CONF"     || die "invalid kraken_confidence"
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
  die "scheduler=pbs requires execution.pbs_queue in config.yaml (e.g. commonCPUQ on UniTN HPC3)"
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
if [ "$SKIP_PREFLIGHT" -eq 0 ] && [ "$DRY" -eq 0 ]; then
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

  while IFS= read -r srr; do
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

# Human reference for the automatic human-read removal (filter_human). T2T-CHM13v2.0 removes
# centromeric/satellite reads that survive GRCh38 and get misclassified as microbial, and drops
# sex-determining signal (privacy). Fully reversible: set PMN_HUMAN_HOST back to "grch38".
PMN_HUMAN_HOST="chm13"

INDEX_LIST=()
read -ra _PMN_HOST_ARR <<< "$PMN_HOSTS"   # split safely (no glob expansion)
for h in "${_PMN_HOST_ARR[@]}"; do
  [ -n "$h" ] || continue           # skip empty tokens (e.g. trailing spaces)
  case "$h" in grch38|chm13) continue ;; esac   # human handled separately via filter_human
  validate_name "$h" || die "invalid host name: $(sanitize_for_log "$h")"
  acc="$(host_accession "$h")"; [ -n "$acc" ] || die "no accession for host '$h' in refs/hosts.tsv"
  do_step pmn_hostfilter "idx_${h}" -- bash "$PMN_ROOT/steps/11_host_index.sh" \
    --host "$h" --accession "$acc" --out "$REF_DIR" --threads "$PMN_THREADS"
  INDEX_LIST+=("$REF_DIR/$h")
done
if [ "$PMN_FILTER_HUMAN" = "yes" ]; then
  acc="$(host_accession "$PMN_HUMAN_HOST")"; [ -n "$acc" ] || die "no $PMN_HUMAN_HOST accession in refs/hosts.tsv"
  do_step pmn_hostfilter "idx_${PMN_HUMAN_HOST}" -- bash "$PMN_ROOT/steps/11_host_index.sh" \
    --host "$PMN_HUMAN_HOST" --accession "$acc" --out "$REF_DIR" --threads "$PMN_THREADS"
  INDEX_LIST+=("$REF_DIR/$PMN_HUMAN_HOST")
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
  if [ "$PMN_TOOL" = "metaphlan" ] || [ "$PMN_TOOL" = "both" ]; then
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
    a+=(--db "$PMN_KRK_DB" --out "$KRK_DIR" --threads "$PMN_THREADS" --confidence "$PMN_KRK_CONF" --readlen "$PMN_BRACKEN_READLEN")
    do_step pmn_kraken "krk_${s}" -- bash "$PMN_ROOT/steps/32_kraken_bracken.sh" "${a[@]}"
  fi
  return 0
}

if [ -d "$NONHOST_DIR" ] || [ "$DRY" -eq 1 ]; then
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
  do_step pmn_reports_py kmatrix -- python "$PMN_ROOT/steps/33_kraken_matrix.py" --in "$KRK_DIR" --out "$KRK_MATRIX"
fi

# B3. Overview report (comparison + all_taxa).
if [ "$PMN_DO_REPORT" = "yes" ]; then
  a=(--out "$RES_DIR/report_overview.xlsx" --threshold-pct "$PMN_THRESHOLD")
  [ -n "$MPA_MERGED" ] && a+=(--metaphlan "$MPA_MERGED")
  [ -n "$KRK_MATRIX" ] && a+=(--kraken "$KRK_MATRIX")
  do_step pmn_reports_py report -- python "$PMN_ROOT/steps/40_compare_report.py" "${a[@]}"
fi

# B4. Diversity (compositional CLR/Aitchison/PCA + alpha) per available matrix.
# Optional grouping: if a metadata TSV is given, colour the PCA by group and run
# Kruskal-Wallis + Dunn (BH) on alpha diversity across groups.
if [ "$PMN_DO_DIVERSITY" = "yes" ]; then
  DIV_ARGS=()
  # Abundance floor for diversity: convert the percent threshold to a relative fraction in [0,1)
  # (e.g. 0.001% -> 1e-5). 41_diversity.R drops per-sample taxa below this BEFORE richness/CLR/PCA.
  MINABUND="$(awk -v p="$PMN_THRESHOLD" 'BEGIN{printf "%.10g", p/100}')"
  if [ -n "$PMN_METADATA" ]; then
    [ -f "$PMN_METADATA" ] || die "analysis.metadata not found: $(sanitize_for_log "$PMN_METADATA")"
    [ -n "$PMN_GROUP_COL" ] || die "analysis.metadata is set but analysis.group_col is empty"
    pmn_strip_crlf "$PMN_METADATA"
    DIV_ARGS=(--metadata "$PMN_METADATA" --group-col "$PMN_GROUP_COL")
  fi
  if [ -n "$MPA_MERGED" ]; then
    do_step pmn_reports_py mpa_matrix -- python "$PMN_ROOT/steps/34_metaphlan_matrix.py" --in "$MPA_MERGED" --out "$RES_DIR/metaphlan_matrix.tsv"
    do_step pmn_stats_r div_mpa -- Rscript "$PMN_ROOT/steps/41_diversity.R" --matrix "$RES_DIR/metaphlan_matrix.tsv" --out "$RES_DIR/diversity_metaphlan" --min-abundance "$MINABUND" ${DIV_ARGS[@]+"${DIV_ARGS[@]}"}
  fi
  if [ -n "$KRK_MATRIX" ]; then
    do_step pmn_stats_r div_krk -- Rscript "$PMN_ROOT/steps/41_diversity.R" --matrix "$KRK_MATRIX" --out "$RES_DIR/diversity_kraken" --min-abundance "$MINABUND" ${DIV_ARGS[@]+"${DIV_ARGS[@]}"}
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
