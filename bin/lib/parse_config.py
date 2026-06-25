#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# bin/lib/parse_config.py - SAFELY parse config.yaml and emit shell assignments.
# Security: uses yaml.safe_load (cannot execute code); every value is shell-quoted with
# shlex.quote and assigned to a fixed allowlist of PMN_* variable names. The output is
# meant to be written to a file and `source`d (it only performs assignments).
import shlex
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML not available (expected in conda env pmn_reports_py)")


def get(d, *keys, default=""):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return default if cur is None else cur


def emit(name, val):
    if isinstance(val, dict):
        sys.exit(f"config error: '{name}' expects a scalar or list, got a mapping")
    if isinstance(val, bool):
        val = "yes" if val else "no"
    elif isinstance(val, (list, tuple)):
        val = " ".join(str(x) for x in val)
    else:
        val = str(val)
    print(f"{name}={shlex.quote(val)}")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: parse_config.py config.yaml")
    with open(sys.argv[1], encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    emit("PMN_LANG", get(cfg, "language", default="en"))
    emit("PMN_DATA_SOURCE", get(cfg, "data_source", default="ncbi"))
    emit("PMN_PROJECT", get(cfg, "project_name", default="study"))
    emit("PMN_WORK_DIR", get(cfg, "paths", "work_dir", default="./pmn_work"))
    emit("PMN_LOCAL_READS", get(cfg, "paths", "local_reads_dir", default=""))
    emit("PMN_SRR_LIST", get(cfg, "paths", "srr_list", default=""))
    # folder layout: managed (tool owns the folders) or custom (user-provided dirs)
    emit("PMN_LAYOUT", get(cfg, "paths", "layout", default="managed"))
    emit("PMN_RAW_DIR", get(cfg, "paths", "raw_dir", default=""))
    emit("PMN_TRIM_DIR", get(cfg, "paths", "trim_dir", default=""))
    emit("PMN_NONHOST_DIR", get(cfg, "paths", "nonhost_dir", default=""))
    emit("PMN_RESULTS_DIR", get(cfg, "paths", "results_dir", default=""))
    emit("PMN_LOGS_DIR", get(cfg, "paths", "logs_dir", default=""))
    emit("PMN_HOSTS", get(cfg, "hosts", default=[]))
    emit("PMN_FILTER_HUMAN", get(cfg, "filter_human", default=True))
    # cleanup / disk hygiene
    emit("PMN_KEEP_TRIMMED", get(cfg, "cleanup", "keep_trimmed", default=False))
    emit("PMN_KEEP_HOST_READS", get(cfg, "cleanup", "keep_host_reads", default=False))
    emit("PMN_HOST_READS_DIR", get(cfg, "cleanup", "host_reads_dir", default=""))
    emit("PMN_TOOL", get(cfg, "profiling", "tool", default="both"))
    emit("PMN_MPA_DB", get(cfg, "profiling", "metaphlan_db", default=""))
    emit("PMN_KRK_DB", get(cfg, "profiling", "kraken_db", default=""))
    emit("PMN_AUTO_INSTALL_DB", get(cfg, "profiling", "auto_install_db", default=False))
    emit("PMN_KRK_DB_MODE", get(cfg, "profiling", "kraken_db_mode", default="standard"))
    emit("PMN_KRK_CUSTOM_GENOMES", get(cfg, "profiling", "kraken_custom_genomes", default=""))
    emit("PMN_KRK_CONF", get(cfg, "profiling", "kraken_confidence", default="0.4"))
    emit("PMN_BRACKEN_READLEN", get(cfg, "profiling", "bracken_readlen", default="150"))
    emit("PMN_THRESHOLD", get(cfg, "profiling", "abundance_threshold_pct", default="0.001"))
    emit("PMN_DO_REPORT", get(cfg, "analysis", "report", default=True))
    emit("PMN_DO_DIVERSITY", get(cfg, "analysis", "diversity", default=True))
    emit("PMN_METADATA", get(cfg, "analysis", "metadata", default=""))
    emit("PMN_GROUP_COL", get(cfg, "analysis", "group_col", default=""))
    emit("PMN_SCHED_CHOICE", get(cfg, "execution", "scheduler", default="auto"))
    emit("PMN_THREADS", get(cfg, "execution", "threads", default="8"))
    emit("PMN_PBS_QUEUE", get(cfg, "execution", "pbs_queue", default=""))
    emit("PMN_PBS_WALLTIME", get(cfg, "execution", "pbs_walltime", default="24:00:00"))
    emit("PMN_PBS_MEM", get(cfg, "execution", "pbs_mem", default="32GB"))
    emit("PMN_PBS_SELECT", get(cfg, "execution", "pbs_select", default=""))


if __name__ == "__main__":
    main()
