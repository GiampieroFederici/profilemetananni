# ProfileMetaNanni — Piano di miglioramento (Iterazione 1)

_Generato da workflow multi-agente: 33 agenti (6 map + 2 vault-ground + 8 autoresearch + 16 verify + synth), 0 errori._

## Executive summary

I read the actual ProfileMetaNanni source (bin/, steps/, refs/, config.example.yaml, SPEC.md) rather than working from the map alone, so every change spec below is anchored to real line numbers and helpers, and both human-reference and phiX accessions are verified live against the NCBI Datasets API (GCF_009914755.1 = T2T-CHM13v2.0; GCF_000819615.1 = phiX174; GCF_000001405.40 = the current GRCh38.p14 row). I accept 7 focused, in-architecture changes: one P0 correctness bugfix (preflight reports BROKEN envs but still exits 0, silently defeating run.sh's gate), four P1 high-value items (make preflight probes actually verify the load-bearing tools/R-libraries per env; upgrade the automatic human host reference GRCh38→T2T-CHM13v2.0, the single strongest evidence-backed and privacy-aligned win; capture per-pass Bowtie2 host-removal stats into the existing MultiQC report for honest observability; and tighten two validators — reject unit-less PBS memory and out-of-range walltime), and two P2 nice-to-haves (add the phiX174 Illumina spike-in as a selectable host per Barcenilla 2024; add an opt-in --very-sensitive-local host-filter preset that defaults to today's behavior). Every item improves an existing step — no Nextflow/Snakemake, no new decontamination engine, no new profiler, no eval, no scope break. Only ACC-5 touches validate.sh allowlists (flagged); ACC-7 deliberately reuses the existing validate_in_set generic instead of adding one. I deliberately DEFER the heavier web candidates (Hostile masked-index CLI, Kraken2 host prefilter, residual-human Y-chromosome gate), the breadth-of-coverage/sylph arm, a food-curated DB list, and parse_config.py defense-in-depth validation, because the T2T swap already captures the real assembly gain and run.sh already re-validates every config value — adding those now would violate the anti-over-engineering constraint.


## Modifiche ACCETTATE (7)


### ACC-1 [P0] — Make preflight.sh exit non-zero when environments are BROKEN (not only MISSING); validate --lang

- **Area:** Framework & Safety / preflight  

- **File toccati:** bin/preflight.sh  

- **Nuovi file:** —  

- **Effort:** low  


**Change spec:**

bin/preflight.sh currently exits 0 for a BROKEN-but-present environment: at the summary (lines 116-160) if broken>0 and missing==0, the broken-warning block (lines 121-124) runs, the missing block (lines 126+) is skipped, and control falls off the end of the script exiting with the status of the last command (the warn, which is 0). run.sh:141 gates the whole run on this exit code, so a broken tool passes the gate. Fix, entirely within preflight.sh: (1) immediately after the arg-parse loop add a source of validate.sh — insert `. "$PMN_BIN_DIR/lib/validate.sh"` right after the existing `. "$PMN_BIN_DIR/lib/requirements.sh"` (line 17) — then after `export PMN_LANG` (line 58) add `validate_lang "$PMN_LANG" || die "invalid --lang (use en|it)"`. (2) Introduce `final_rc=0` just before the summary block (before line 116). (3) Inside the broken block (after `if [ ${#broken[@]} -gt 0 ]; then`, line 121) add `final_rc=2`. (4) At the very end of the file (after the closing `fi`/final `ok` on line 160) add `exit "$final_rc"`. Trace: all-good still exits 0 at line 118; broken-only now reaches end with final_rc=2 -> exit 2; missing-without-install still exits 2 (unchanged); missing installed OK with no broken -> final_rc=0 -> exit 0; missing installed OK but broken present -> exit 2. Update usage() exit-code text (lines 39-43) to read '2  one or more environments missing OR broken'. No control-flow rewrite, no set -e change.


**Rationale:** A preflight that prints BROKEN yet returns success is exactly the dishonest-exit-code failure the Safety Constitution forbids, and it lets run.sh proceed into a pipeline that will crash deep in a step. This is a clear, self-contained bugfix that tightens a contract already documented in usage().


**Citations:** INPUT1 map, preflight.sh correctness_risks[0]: 'BROKEN environments never change the final exit code ... exits 0'; bin/preflight.sh:116-160 (verified fall-through); bin/run.sh:141 (`|| die "preflight failed"` gates on exit code); SPEC.md §0.7 'Be honest. Never claim a step succeeded without checking its real exit code'


**Risk:** Low. Only new outcome is exit 2 where a broken env exists — a caller that ignored exit codes is unaffected; run.sh now correctly stops. validate_lang rejects a bogus --lang instead of silently defaulting to English.


### ACC-2 [P1] — Preflight probes must verify every load-bearing tool/R-library per env, not just one

- **Area:** Framework & Safety / requirements (single source of truth)  

- **File toccati:** bin/lib/requirements.sh  

- **Nuovi file:** —  

- **Effort:** low  


**Change spec:**

In bin/lib/requirements.sh each multi-package env probes only one binary (PMN_ENV_PROBE, lines 44-53), so a partially-installed env reports OK and fails later; pmn_stats_r checks only R.version.string, never the R packages that 41_diversity.R hard-requires (vegan, ade4, ape, zCompositions, rstatix, ggpubr) and that notoriously fail to install from bioconda. Extend the probes to cheap compound checks (keep --version for tools already probed that way; use `command -v` for secondary CLIs so a missing-version flag can't cause a false BROKEN): [pmn_download]="prefetch --version && command -v pigz"; [pmn_trim]="fastp --version && command -v fastqc"; [pmn_hostfilter]="bowtie2 --version && command -v samtools && command -v datasets && command -v unzip"; [pmn_kraken]="kraken2 --version && command -v bracken && command -v datasets && command -v unzip"; [pmn_stats_r]="Rscript -e 'suppressMessages({library(vegan);library(ade4);library(ape);library(zCompositions);library(rstatix);library(ggpubr)})'". Leave [pmn_qc], [pmn_metaphlan] (single tool) and [pmn_reports_py] (already imports all modules) as-is. Second, add a source-time consistency guard right after the three arrays are declared (after line 59): loop over PMN_ENV_ORDER and, for any name missing a key in PMN_ENV_PKGS or PMN_ENV_PROBE, print `requirements.sh: <name> missing from PMN_ENV_PKGS/PROBE` to stderr and `exit 1` (this file is only ever sourced after common.sh, so failing here is a clear fail-fast; `unset` the loop var afterward). No package-list or version-pin changes.


**Rationale:** The probe's stated purpose is 'the key tool is actually callable' — currently it proves only that ONE tool exists. The R-library gap is the highest-value: a missing vegan/zCompositions passes preflight then aborts the diversity step after the whole expensive pipeline has run. The consistency guard turns a cryptic set -u unbound-variable into a named error.


**Citations:** INPUT1 map, requirements.sh correctness_risks[0-1] and improvements[0-1] (probe coverage; parallel-array consistency); steps/41_diversity.R:15,70,150 (requires vegan, zCompositions, rstatix at runtime); INPUT2 vault, Caffrey/tooling note: bioconda R builds frequently miss packages; bin/lib/requirements.sh:44-53


**Risk:** Low. Preflight runs a few seconds longer (R library() loads). No runtime behavior change; only detection is stricter and earlier.


### ACC-3 [P1] — Upgrade the automatic human host reference from GRCh38.p14 to T2T-CHM13v2.0

- **Area:** Host depletion / reference genome  

- **File toccati:** refs/hosts.tsv, bin/run.sh, config.example.yaml, SPEC.md, README.md  

- **Nuovi file:** —  

- **Effort:** medium  


**Change spec:**

Verified accession: GCF_009914755.1 = Homo sapiens, T2T-CHM13v2.0, Complete Genome (live NCBI Datasets check). (1) refs/hosts.tsv: ADD a row `chm13<TAB>GCF_009914755.1<TAB>human (T2T-CHM13v2.0)` and KEEP the existing grch38 row (reversibility / operator choice). (2) bin/run.sh: introduce a single human-label variable just before the host loop (before line 186): `PMN_HUMAN_HOST="chm13"  # T2T human ref for the automatic human-read removal`. Change the extra-hosts skip at line 190 from `[ "$h" = "grch38" ] && continue` to `case "$h" in grch38|chm13) continue ;; esac` (listing either human label in `hosts` never double-adds). In the filter_human block (lines 197-202) replace the three hard-coded `grch38` tokens: `acc="$(host_accession "$PMN_HUMAN_HOST")"`, `--host "$PMN_HUMAN_HOST"`, and `INDEX_LIST+=("$REF_DIR/$PMN_HUMAN_HOST")`, and update the die message to reference $PMN_HUMAN_HOST. Because the index is named by label, the index file becomes chm13.1.bt2(l): 11_host_index.sh builds a FRESH index (its idempotency skip at line 34 keys on the label), so there is NO stale-GRCh38-index trap and no forced deletion. (3) config.example.yaml lines 15-16/22: change the comment 'Human (grch38) is removed AUTOMATICALLY' to 'Human (T2T-CHM13v2.0) is removed AUTOMATICALLY (removes centromeric/satellite reads that survive GRCh38 and get misclassified as microbial)'. (4) Docs: update the grch38 mentions in SPEC.md §2.2 (line 67) and README.md to state CHM13v2.0 is the default human reference, GRCh38 remains available as a hosts.tsv row. Reversible by setting PMN_HUMAN_HOST back to "grch38".


**Rationale:** Two independent 2025 peer-reviewed benchmarks (CONFIRMED by the adversarial pass) show GRCh38 leaves a median ~0.08% (up to 2.48%) residual human reads that are misclassified as microbial taxa, and that T2T-CHM13 removes them — cutting false-positive species ~47.75% and, critically for this project's privacy rule, eliminating sex-determining Y-chromosome signal. It is a one-row data-driven change to an already accession-driven, idempotent Bowtie2 index build; zero new tools/deps.


**Citations:** INPUT3 T1-1 / INPUT4 verdict CONFIRMED (recommended=true): Zhou 2025 mSystems 10:e00840-25; Forbes 2025 Cell Reports Methods PMC12664888; NCBI Datasets API (verified this session): GCF_009914755.1 -> T2T-CHM13v2.0, Complete Genome; INPUT2 vault: privacy / removing reidentifying human reads; CLAUDE.md privacy rule 'mai dati identificabili'; bin/run.sh:182-202; refs/hosts.tsv:8; steps/11_host_index.sh:33-37


**Risk:** Low-medium. +216 Mbp reference => slightly larger index and one-time longer build. Retaining the grch38 row and using a new label keeps the change fully reversible and idempotent.


### ACC-4 [P1] — Capture per-pass Bowtie2 host-removal stats into the existing MultiQC report

- **Area:** Host depletion / QC, observability, honest reporting  

- **File toccati:** steps/21_hostfilter.sh, bin/run.sh  

- **Nuovi file:** —  

- **Effort:** low  


**Change spec:**

Today steps/21_hostfilter.sh sends the SAM to /dev/null and lets Bowtie2's alignment summary (the 'overall alignment rate' = host fraction) go to the terminal, where it is lost; MultiQC (steps/22_multiqc.sh, run over $PMN_WORK_DIR) therefore shows nothing about host removal. Make it observable with an additive capture: (1) steps/21_hostfilter.sh — add a `--log-dir DIR` option to the arg loop (default empty), validate it with `validate_path_safe "$LOGDIR"` when non-empty, set `LOGDIR="${LOGDIR:-$OUT}"`, `mkdir -p "$LOGDIR"`. In run_pass() append a stderr redirect to each bowtie2 invocation (lines 88-92): `... -S /dev/null 2> "$LOGDIR/${SAMPLE}.${idxname}.bowtie2.log" || return 1`. The per-pass, per-host log now contains the summary MultiQC's Bowtie2 module auto-parses. (2) bin/run.sh — define `HF_LOG_DIR="$PMN_WORK_DIR/hostfilter_logs"` near the other dir vars (after line 120; note it lives UNDER work_dir so MultiQC always scans it even in custom layout) and in hostfilter_sample() (lines 206-215) add `--log-dir "$HF_LOG_DIR"` to the arg array `a`. No change to 22_multiqc.sh (its bowtie2 module already matches on log content). Idempotency untouched: the skip at 21_hostfilter.sh:66 still keys on final outputs; logs are simply rewritten on a real (non-skipped) pass.


**Rationale:** Alignment host-removal has two silent failure modes — over-depletion (stripping microbial reads) and under-depletion (residual host inflating downstream cost 7-20x) — both only catchable if per-sample removal is measured. The stats already exist on Bowtie2 stderr; we just persist them where the pipeline's existing MultiQC step surfaces them. High leverage, ~4 lines, no new tool, and it lays the groundwork for a later residual-host/privacy gate.


**Citations:** INPUT3 T1-5 / INPUT4 verdict PLAUSIBLE (recommended=true): Benchmarking short-read host-removal, GigaScience 2025, PMC11878760; steps/21_hostfilter.sh:74-94 (stderr currently uncaptured); steps/22_multiqc.sh:37 (scans work_dir); SPEC.md §0.7 honesty; §3.2 'give a short comment ... after MultiQC'


**Risk:** Low. Bowtie2 summary moves from console to a log file (still visible in MultiQC and on disk); the pipeline's own info() lines still narrate progress.


### ACC-5 [P1] — Tighten validators: require a unit on PBS memory and bound walltime MM/SS to 0-59

- **Area:** Framework & Safety / validation (allowlist) — FLAGGED: touches validate.sh  

- **File toccati:** bin/lib/validate.sh, config.example.yaml  

- **Nuovi file:** —  

- **Effort:** low  


**Change spec:**

FLAG: this edits allowlist regexes in bin/lib/validate.sh; keep it consistent with parse_config defaults and config.example. (1) validate_mem (lines 40-43): the current regex `^[0-9]+([KkMmGgTt][Bb]?|[Bb])?$` accepts a bare integer like `4000`, which some PBS/Torque configs treat as BYTES -> a silent ~4KB memory request. Drop the trailing optional group to REQUIRE a unit: `[[ "$m" =~ ^[0-9]+([KkMmGgTt][Bb]?|[Bb])$ ]]`. This still accepts 32GB / 512mb / 1tb / 4000b (explicit bytes) and rejects a unit-less number, which run.sh:73 already reports as `invalid execution.pbs_mem (e.g. 32GB)`. The parse_config default (32GB) and config.example (32GB) both pass, so no default breaks. (2) validate_walltime (lines 31-37): tighten the good-case pattern from `[0-9]*:[0-9][0-9]:[0-9][0-9]` to `[0-9]*:[0-5][0-9]:[0-5][0-9]` so `1:99:99` is rejected at validation instead of only at qsub time; multi-digit hours (168:00:00) still pass. (3) config.example.yaml line 78: extend the pbs_mem comment to state 'a unit is REQUIRED (e.g. 32GB, 512MB); a bare number is rejected'. No call-site changes needed (both validators are used only in run.sh:72-73).


**Rationale:** A unit-less memory value silently under-requesting RAM on PBS is a real correctness/expense hazard (a Kraken standard-DB job needs ~80GB; getting ~4KB fails cryptically after queueing). Requiring the unit fails closed with a clear message. Bounding MM/SS makes the validator's guarantee match its documented intent.


**Citations:** INPUT1 map, validate.sh correctness_risks[0] (unit-less mem) and [1] (unbounded MM/SS); improvements 'Memory unit enforcement' + 'Walltime field bounds'; bin/lib/validate.sh:31-43; bin/run.sh:72-73; config.example.yaml:78


**Risk:** Low, but behavior-changing: a config that used a bare-number pbs_mem is now rejected (it was mis-sizing before). Mitigated by the clear die message and the doc note; all shipped defaults/examples already carry a unit.


### ACC-6 [P2] — Add phiX174 Illumina spike-in as a selectable host; document the livestock+phiX+human chain

- **Area:** Host depletion / non-human hosts (data-only)  

- **File toccati:** refs/hosts.tsv, config.example.yaml, SPEC.md  

- **Nuovi file:** —  

- **Effort:** low  


**Change spec:**

Verified accession: GCF_000819615.1 = Escherichia phage phiX174 (ViralProj14015), Complete Genome. (1) refs/hosts.tsv: add row `phix<TAB>GCF_000819615.1<TAB>PhiX174 Illumina spike-in (Barcenilla 2024)`. It flows through the existing chain automatically — run.sh:184-196 downloads+indexes any hosts.tsv row named in `hosts`, and phix passes validate_name (line 191) and validate_accession. (2) config.example.yaml: in the hosts block comment (lines 14-21) note 'for Illumina data add `phix` to remove the PhiX174 spike-in; add `bos_taurus` for beef, `gallus_gallus` for poultry — reference relatedness to the true substrate dominates accuracy'. Keep the default hosts list as-is (sus_scrofa) to stay non-destructive — phix is opt-in. (3) SPEC.md §2.2 (line 67-70): mention phix and the livestock rows as recommended additions for meat/food matrices. No code changes.


**Rationale:** The closest real-world parameter set in the vault (Barcenilla 2024, the exact meat-plant WMS domain) depletes phiX174 + human + livestock; phiX is an ~5kb spike-in present in essentially all Illumina runs and trivially cheap to remove. The pipeline already supports arbitrary host chaining, so this is a one-line reference-data add plus documentation — the architecture already earns it.


**Citations:** INPUT2 vault: Barcenilla et al. 2024, Microbiome 12:199 (phiX174 + GRCh38 + Bos taurus + Sus scrofa host depletion); NCBI Datasets API (verified this session): GCF_000819615.1 -> phiX174; refs/hosts.tsv:1-9; bin/run.sh:184-196


**Risk:** Low. Pure opt-in data addition; default behavior unchanged unless the user adds `phix` to hosts.


### ACC-7 [P2] — Optional --very-sensitive-local host-filter preset (opt-in, defaults to current behavior)

- **Area:** Host depletion / aligner configuration  

- **File toccati:** bin/lib/parse_config.py, bin/run.sh, steps/21_hostfilter.sh, config.example.yaml  

- **Nuovi file:** —  

- **Effort:** medium  


**Change spec:**

Add a gated sensitivity preset without changing today's default or the paired-mode handling. (1) bin/lib/parse_config.py: add one line after line 56 (near the host keys) — `emit("PMN_HOST_PRESET", get(cfg, "host_sensitivity", default="very-sensitive"))`. (2) bin/run.sh: after the other validations, add `validate_in_set "$PMN_HOST_PRESET" very-sensitive very-sensitive-local || die "invalid host_sensitivity (very-sensitive|very-sensitive-local)"` (reuses the EXISTING generic in validate.sh — no new validator, no allowlist edit), and in hostfilter_sample() add `--preset "$PMN_HOST_PRESET"` to arg array `a`. (3) steps/21_hostfilter.sh: add a `--preset` option (default `very-sensitive`) to the arg loop; validate it with an inline case-allowlist and map to a single Bowtie2 token: `case "$PRESET" in very-sensitive) BT2_PRESET="--very-sensitive" ;; very-sensitive-local) BT2_PRESET="--very-sensitive-local" ;; *) die "invalid --preset" ;; esac`; then replace the literal `--very-sensitive` in both bowtie2 calls (run_pass, lines 88 and 91) with `$BT2_PRESET` (a single allowlisted token, safe unquoted). Keep paired --un-conc-gz handling unchanged (do NOT switch to unpaired mode — that is a larger change with its own trade-offs; the soft-clipping gain comes from -local). (4) config.example.yaml: document `host_sensitivity: very-sensitive   # very-sensitive | very-sensitive-local (soft-clips partial host reads; slightly higher host sensitivity, ~negligible microbial loss)`. Compose after ACC-4 (both edit run_pass).


**Rationale:** The 2025 benchmark shows --very-sensitive-local yields materially fewer missed-host reads at a quantified-negligible specificity cost (median 5 false-positive reads), which supports the project's privacy goal and lighter downstream read volume. Kept strictly opt-in and defaulting to today's flag so it is non-destructive; reuses validate_in_set so no allowlist surface is added.


**Citations:** INPUT3 T1-2 / INPUT4 verdict PLAUSIBLE (recommended=true): Forbes 2025 Cell Reports Methods PMC12664888 (Bowtie2-VSL benchmark); steps/21_hostfilter.sh:88,91 (current --very-sensitive); bin/lib/validate.sh:15-20 (validate_in_set); bin/run.sh:206-215


**Risk:** Low. Default path byte-for-byte unchanged; the alternate value is confined to an allowlisted single token in one bowtie2 flag. Verdict notes the profiling-accuracy uplift is marginal, so this is the lowest-priority accepted item.


## Implementation blueprint

Implement in this order in iteration 2, smallest-blast-radius and most-isolated first, each verified before the next. STEP 1 — ACC-5 (validate.sh tightening): pure validator regexes with no downstream behavior beyond stricter acceptance; edit first and confirm config.example.yaml (32GB, 24:00:00) still passes and that a bare `4000` / `1:99:99` now fail. FLAG: this is the only validate.sh allowlist change — keep it in lockstep with parse_config defaults. STEP 2 — ACC-1 (preflight honesty + lang): isolated to preflight.sh; make the gate honest BEFORE other changes rely on it. Verify by simulating a broken env (env present, tool absent) -> exit 2, and a good machine -> exit 0. STEP 3 — ACC-2 (probe coverage): requirements.sh only; run `bash bin/preflight.sh` on a machine with the envs to confirm all eight still probe OK (especially the pmn_stats_r R-library load) and that the new source-time consistency guard is silent. STEP 4 — ACC-4 (host-filter QC logs): additive stderr capture in 21_hostfilter.sh + one dir var and one arg in run.sh; no output-path or idempotency change. Verify a small paired sample produces $work/hostfilter_logs/<sample>.<host>.bowtie2.log and that MultiQC surfaces a Bowtie2 section. STEP 5 — ACC-3 (T2T-CHM13 relabel): add the chm13 row (keep grch38), introduce PMN_HUMAN_HOST and swap the three run.sh tokens + skip-case, update config/SPEC/README. Because the host label changes, step 11 builds a fresh chm13 index (idempotent; no stale-index reuse, no deletion); fully reversible by resetting PMN_HUMAN_HOST=grch38. STEP 6 — ACC-6 (phiX row): data-only hosts.tsv addition + docs; opt-in, default hosts unchanged. STEP 7 — ACC-7 (--very-sensitive-local preset): last because it spans the most files and is lowest priority; it edits run_pass in 21_hostfilter.sh so sequence it AFTER ACC-4 so the stderr-redirect and the $BT2_PRESET token edits compose cleanly. Default value keeps byte-identical behavior. Cross-cutting guarantees held by every step: NON-DESTRUCTIVE (grch38 row retained; phiX and the -local preset opt-in and defaulted to today's behavior; mem/walltime only reject clearly-wrong values that were already mis-sizing; no file/DB deletion added). IDEMPOTENT (all skip-if-exists checks untouched; the new human label forces a clean rebuild rather than reusing a stale index; QC logs are simply overwritten on a real pass). SAFE / Safety-Constitution (no eval, no sudo/chmod, no new privileged ops; every new input flows through existing allowlists — validate_lang, validate_in_set, validate_path_safe, validate_accession — or an inline case-allowlist; the one bowtie2 preset is a single allowlisted token; captured tool stderr goes only to validate_path_safe-checked paths and remains sanitizable via sanitize_for_log; no egress). MINIMAL (reuse existing helpers and the existing MultiQC Bowtie2 module, the accession-driven step-11 build, and the validate_in_set generic — no Nextflow/Snakemake, no new profiler, no new decontamination engine, no new conda package). After each step: check the real exit code and expected outputs (SPEC §0.7/§3.4) before proceeding, and run one paired + one single-end sample end-to-end after STEP 7 to confirm the full chain still completes and the report/diversity outputs are unchanged.


## Deferiti (11) — con motivazione


- **Hostile masked human index (human-t2t-hla-argos985) as an alternate fetch path** — INPUT4 verdict recommended ONLY the minimal form and showed the over-depletion benefit is marginal for short reads (bacterial retention 99.99989%->99.99994%; the 43x sparing is ONT-only) and that Hostile ships no masked livestock references, leaving this pipeline's dominant hosts untouched. The real assembly gain (GRCh38->T2T-CHM13v2.0) is already captured by ACC-3 via the clean NCBI-accession build. Adding Hostile's object-store download path duplicates the idempotent step-11 build machinery — an anti-over-engineering violation for marginal gain. Revisit as an optional gated wrapper only if long-read support is added.

- **Residual-human privacy gate (Y-chromosome depth / residual host fraction) after depletion** — An honest measurement of reads that ESCAPED depletion requires a separate alignment (e.g. Y-chromosome depth), which is heavier than the Bowtie2-log parse ACC-4 provides; the log only shows what WAS removed. ACC-3 (T2T-CHM13) is the actual privacy win (eliminates sex-determining signal). Best built later on top of ACC-4's captured logs as a small, explicitly-gated check.

- **Kraken2 k-mer host prefilter before the alignment pass** — INPUT3 flagged it speculative and gated OFF; k-mer methods under-deplete, so alignment must stay authoritative, and it only helps when the alignment step is proven the bottleneck. No evidence that it is here. Skip per anti-over-engineering.

- **Breadth-of-coverage / genome-presence arm (MiFoDB / sylph / inStrain-style)** — Directly on-point (Caffrey 2025: relative-abundance-to-100% + no breadth-of-coverage lets a few spurious reads masquerade as present), but it means a new tool and alignment-based profiling — out of the declared read-based scope. The pipeline already mitigates via the Bracken min-read threshold (-t 10) plus the post-hoc abundance filter in 41_diversity.R. Document as a planned optional gated arm, do not add now.

- **Ship a food/fermented-meat-curated Kraken custom-genome accession list (cFMD/MiFoDB)** — Carlino 2024 quantifies the reference-DB gap (hundreds of food SGBs absent from standard DBs), and the pipeline ALREADY supports kraken_db_mode: custom with an accession list — so the architecture is present. Curating the list is domain data work, not pipeline architecture; ship an example list as a later docs/data addition.

- **parse_config.py defense-in-depth (enum/number/list/empty-string validation)** — run.sh is the sole consumer of parse_config's output and already re-validates every emitted value (lines 52-80: langs, enums, decimals with awk range clamps, yes/no, paths, walltime/mem/select). Empty overrides of non-empty defaults (e.g. work_dir='') and list/number type errors are all caught downstream by validate_path_safe/validate_uint/validate_in_set. Duplicating those checks in Python is a redundant addition the anti-over-engineering rule rejects; shlex.quote already neutralizes injection at the parse boundary.

- **conda_env_exists: replace `conda env list | awk` with a direct envs-dir test** — INPUT1 rates the parsing fragility 'low but real'; it is exact enough for the named pmn_* envs this project creates in the default envs dir. Low impact, not an active bug — not worth a change on its own.

- **Checksum-verify large DB downloads (verify_checksum wired into steps 12/13)** — SECURITY.md already honestly documents this gap. DBs are multi-GB and evolve, so pinning sha256 is impractical, and they are fetched via official tools (datasets, kraken2-build, metaphlan --install) that validate their own packages. Adding brittle checksum gates now yields little and risks fail-closed friction.

- **validate_under_base / verify_checksum tri-state (rc=2) contract hardening** — A real design nuance (a `|| die` caller conflates 'unsafe' with 'cannot check'), but it is a behavior change requiring a call-site audit and there is no active exploit in the current call graph. Defer until a call site actually depends on the distinction.

- **Unpaired Bowtie2 mapping mode for host depletion** — The T1-2 benchmark's unpaired mode is a larger change to the pipeline's paired --un-conc-gz handling with its own trade-offs; ACC-7 adopts the -local sensitivity preset while retaining paired mapping to stay minimal and idempotent. Revisit only if privacy/host-sensitivity data demands it.

- **StrainPhlAn, assembly, MAG recovery, functional annotation** — Explicitly out-of-scope per SPEC.md §3 (documented as planned). Not proposed here; would only be added as clearly-gated optional arms in a future iteration, never silently.