#!/usr/bin/env bash
# requirements.sh - SINGLE SOURCE OF TRUTH for conda environments & databases.
# Edit ONLY here to change packages/tools. Sourced by preflight.sh and run.sh.
# SOURCE this file (do not execute it directly).

# Conda channels (order matters: conda-forge before bioconda).
PMN_CHANNELS=(-c conda-forge -c bioconda)

# Conda environments required by the pipeline (scope: preprocessing + read-based profiling).
# Names are prefixed "pmn_" so they never clobber a user's existing environments.
declare -A PMN_ENV_PKGS=(
  [pmn_download]="sra-tools pigz"
  [pmn_qc]="multiqc"
  [pmn_trim]="fastp fastqc"
  [pmn_hostfilter]="bowtie2 samtools ncbi-datasets-cli unzip"
  [pmn_metaphlan]="metaphlan"
  [pmn_kraken]="kraken2 bracken ncbi-datasets-cli unzip"
  [pmn_stats_r]="r-base r-vegan r-ade4 r-ape r-zcompositions r-rstatix r-ggpubr"
  [pmn_reports_py]="python pandas numpy scipy matplotlib seaborn openpyxl pyyaml"
)

# A cheap probe per environment: confirms the key tool is actually callable
# (not just that the env exists). Run as:  conda run -n <env> bash -c "<probe>"
declare -A PMN_ENV_PROBE=(
  [pmn_download]="prefetch --version"
  [pmn_qc]="multiqc --version"
  [pmn_trim]="fastp --version"
  [pmn_hostfilter]="bowtie2 --version"
  [pmn_metaphlan]="metaphlan --version"
  [pmn_kraken]="kraken2 --version"
  [pmn_stats_r]="Rscript -e 'cat(R.version.string)'"
  [pmn_reports_py]="python -c 'import pandas,numpy,scipy,matplotlib,seaborn,openpyxl,yaml'"
)

# Explicit order (associative arrays are unordered) for reporting/installation.
PMN_ENV_ORDER=(
  pmn_download pmn_qc pmn_trim pmn_hostfilter
  pmn_metaphlan pmn_kraken pmn_stats_r pmn_reports_py
)

# Reference databases (large; NEVER auto-downloaded — must be confirmed explicitly).
# Format:  "approx size|how to obtain"
declare -A PMN_DB_INFO=(
  [metaphlan_db]="~20-25 GB|metaphlan --install --bowtie2db <DIR>"
  [kraken2_db]="~50-90 GB|kraken2-build --standard --db <DIR>  (or fetch a prebuilt index)"
)
