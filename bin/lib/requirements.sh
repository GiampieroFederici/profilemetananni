#!/usr/bin/env bash
# requirements.sh - SINGLE SOURCE OF TRUTH for conda environments & databases.
# Edit ONLY here to change packages/tools. Sourced by preflight.sh and run.sh.
# SOURCE this file (do not execute it directly).

# Conda channels (order matters: conda-forge before bioconda).
PMN_CHANNELS=(-c conda-forge -c bioconda)

# Conda environments required by the pipeline (scope: preprocessing + read-based profiling).
# Names are prefixed "pmn_" so they never clobber a user's existing environments.
#
# REPRODUCIBILITY NOTE (EN):
#   Tested-with versions (known-good combo on which this pipeline was validated):
#     MetaPhlAn 4.2.4 (DB vJan25, exact pin)  ·  Kraken2 2.1.3  ·  Bracken 2.9
#     fastp 0.23.x     ·  Bowtie2 2.5.x  ·  R 4.x
#   Only the three scientifically load-bearing tools carry a conservative
#   MINIMUM-version pin (">=") to guard against ancient/incompatible releases
#   while keeping the conda solve flexible. Exact "==" pins are deliberately
#   avoided because they frequently make the environment unsolvable.
#   All other packages stay as bare names (latest compatible build is fine).
#
# NOTA RIPRODUCIBILITA (IT):
#   Versioni di riferimento (combinazione testata e funzionante):
#     MetaPhlAn 4.2.4 (DB vJan25, exact pin)  ·  Kraken2 2.1.3  ·  Bracken 2.9
#     fastp 0.23.x     ·  Bowtie2 2.5.x  ·  R 4.x
#   Solo i tre strumenti scientificamente cruciali hanno un vincolo di
#   versione MINIMA (">="), per evitare versioni troppo vecchie senza
#   rendere irrisolvibile l'ambiente conda. I pin esatti ("==") sono
#   evitati di proposito perche spesso bloccano il solve. Tutti gli altri
#   pacchetti restano nomi nudi (va bene l'ultima build compatibile).
#   pytest dentro pmn_reports_py e' una scelta, non una svista: la Fase C
#   verifica ogni task con
#   "conda run -n pmn_reports_py python -m pytest ...", quindi in produzione i test
#   girano dentro questo env e senza pytest non partono affatto. Il prezzo e' che un
#   ambiente di analisi senza pytest viene segnalato ROTTO da preflight: accettato,
#   perche' un ambiente in cui i test non si possono lanciare non e' verificabile.
declare -A PMN_ENV_PKGS=(
  [pmn_download]="sra-tools pigz"
  [pmn_qc]="multiqc"
  [pmn_trim]="fastp fastqc"
  [pmn_hostfilter]="bowtie2 samtools ncbi-datasets-cli unzip"
  # EXACT pin on purpose (exception to the ">=" rule above): metaphlan=4.2.4 + DB vJan25 is the
  # combination behind the published Ciauscolo profiles; another version/DB gives profiles that
  # cannot be compared with them. python=3.11: the version this combination was tested with here.
  [pmn_metaphlan]="metaphlan=4.2.4 python=3.11"
  [pmn_kraken]="kraken2>=2.1.3 bracken>=2.9 ncbi-datasets-cli unzip"
  [pmn_stats_r]="r-base r-vegan r-ade4 r-ape r-zcompositions r-rstatix r-ggpubr"
  [pmn_reports_py]="python pandas numpy scipy matplotlib seaborn openpyxl pyyaml pytest"
  [pmn_biomni]="python pandas pip"
)

# Packages that do NOT exist on conda and must be pip-installed AFTER the env is created.
# Biomni ships on PyPI only, so `conda create -n pmn_biomni python pandas pip` alone leaves
# `import biomni` failing and the probe below reporting BROKEN forever. Biomni's own installer
# targets Ubuntu, so this pip step can legitimately fail elsewhere: preflight then prints the
# manual command (see PMN_ENV_PIP_MANUAL) instead of sending the user round a loop.
declare -A PMN_ENV_PIP=(
  [pmn_biomni]="biomni"
)
# The exact command to suggest when the automatic pip step above is not possible or fails.
declare -A PMN_ENV_PIP_MANUAL=(
  [pmn_biomni]="conda run -n pmn_biomni pip install biomni"
)

# A cheap probe per environment: confirms the key tool is actually callable
# (not just that the env exists). Run as:  conda run -n <env> bash -c "<probe>"
# Compound probes verify EVERY load-bearing tool/library in a multi-package env (a
# one-tool probe lets a partially-installed env report OK, then fail deep in a step).
# --version for the primary tool; `command -v` for secondary CLIs so a missing --version
# flag cannot cause a false BROKEN. pmn_stats_r probes ONLY vegan -- the one library
# 41_diversity.R loads unconditionally (line 15); zCompositions/rstatix are optional there
# (the script has requireNamespace() fallbacks) and ade4/ape/ggpubr are unused, so probing
# them would false-BROKEN an env whose diversity stage would in fact run.
declare -A PMN_ENV_PROBE=(
  [pmn_download]="prefetch --version && command -v pigz"
  [pmn_qc]="multiqc --version"
  [pmn_trim]="fastp --version && command -v fastqc"
  [pmn_hostfilter]="bowtie2 --version && command -v samtools && command -v datasets && command -v unzip"
  [pmn_metaphlan]="metaphlan --version"
  [pmn_kraken]="kraken2 --version && command -v bracken && command -v datasets && command -v unzip"
  [pmn_stats_r]="Rscript -e 'suppressMessages(library(vegan))'"
  [pmn_reports_py]="python -c 'import pandas,numpy,scipy,matplotlib,seaborn,openpyxl,yaml,pytest'"
  [pmn_biomni]="python -c 'import biomni'"
)

# Explicit order (associative arrays are unordered) for reporting/installation.
PMN_ENV_ORDER=(
  pmn_download pmn_qc pmn_trim pmn_hostfilter
  pmn_metaphlan pmn_kraken pmn_stats_r pmn_reports_py pmn_biomni
)

# Consistency guard: every ordered env MUST have a package list and a probe. A typo here
# would otherwise surface as a cryptic `set -u` unbound-variable error deep in preflight.
for _pmn_e in "${PMN_ENV_ORDER[@]}"; do
  if [ -z "${PMN_ENV_PKGS[$_pmn_e]+x}" ] || [ -z "${PMN_ENV_PROBE[$_pmn_e]+x}" ]; then
    printf 'requirements.sh: %s missing from PMN_ENV_PKGS/PMN_ENV_PROBE\n' "$_pmn_e" >&2
    exit 1
  fi
done
unset _pmn_e

# Reference databases (large; NEVER auto-downloaded — must be confirmed explicitly).
# Format:  "approx size|how to obtain"
declare -A PMN_DB_INFO=(
  [metaphlan_db]="~30 GB|metaphlan --install --db_dir <DIR> --index mpa_vJan25_CHOCOPhlAnSGB_202503"
  [kraken2_db]="~50-90 GB|kraken2-build --standard --db <DIR>  (or fetch a prebuilt index)"
)
