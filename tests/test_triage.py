# -*- coding: utf-8 -*-
import importlib.util
import json
import os
import subprocess
import sys

import pytest

STEP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "steps", "17_triage_report.py")
_spec = importlib.util.spec_from_file_location("triage_report", STEP)
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)

DEFAULTS = dict(max_host_pct=95.0, min_nonhost_reads=1_000_000, min_q30_pct=70.0)


def metrics(total=10_000_000, pass_rate=0.95, q30=90.0, tested=100_000, nonhost=50_000):
    return {"total": total, "pass_rate": pass_rate, "q30": q30, "dup": 10.0,
            "tested": tested, "nonhost": nonhost}


def write_sample(d, s, total=10_000_000, before=200_000, passed=190_000, q30=0.9,
                 tested=100_000, nonhost=50_000):
    (d / f"{s}.triage_reads.txt").write_text(f"{total}\n", encoding="utf-8")
    (d / f"{s}.triage_qc.json").write_text(json.dumps({
        "summary": {"before_filtering": {"total_reads": before, "q30_rate": q30}},
        "filtering_result": {"passed_filter_reads": passed},
        "duplication": {"rate": 0.12}}), encoding="utf-8")
    (d / f"{s}.triage_host.tsv").write_text(f"tested\t{tested}\nnonhost\t{nonhost}\n", encoding="utf-8")


def test_ramp_is_half_at_threshold_and_clamped():
    assert tr.ramp(70, 70) == pytest.approx(0.5)
    assert tr.ramp(84, 70) == pytest.approx(1.0)   # +20%
    assert tr.ramp(56, 70) == pytest.approx(0.0)   # -20%
    assert tr.ramp(1e9, 70) == 1.0 and tr.ramp(0, 70) == 0.0


def test_clean_sample_passes_with_no_reasons():
    r = tr.evaluate(metrics(), **DEFAULTS)
    assert r["decision"] == "pass"
    assert r["reasons"] == ""
    assert r["host_pct"] == pytest.approx(50.0)
    assert r["est_nonhost_fragments"] == 4_750_000   # 10M * 0.95 * 0.5


def test_mostly_host_sample_is_excluded_and_explained():
    # 99% host: non-host share 1% vs the 5% floor -> far below the grey zone
    r = tr.evaluate(metrics(nonhost=1_000), **DEFAULTS)
    assert r["decision"] == "exclude"
    assert "host 99.0%" in r["reasons"]


def test_borderline_host_goes_to_review():
    # exactly 95% host -> non-host 5% == threshold -> sub-score 0.5 -> review
    # (large run, so the yield rule stays clearly passed and only the host rule is borderline)
    r = tr.evaluate(metrics(total=100_000_000, nonhost=5_000), **DEFAULTS)
    assert r["decision"] == "review"
    assert r["score"] == pytest.approx(0.5)


def test_low_yield_excludes_even_when_host_and_quality_are_fine():
    r = tr.evaluate(metrics(total=500_000), **DEFAULTS)   # ~237k non-host fragments
    assert r["decision"] == "exclude"
    assert "non-host fragments" in r["reasons"]


def test_low_quality_is_the_weakest_link():
    r = tr.evaluate(metrics(q30=60.0), **DEFAULTS)
    assert r["decision"] == "exclude"
    assert r["reasons"].startswith("Q30")


def test_italian_reasons():
    r = tr.evaluate(metrics(total=500_000), lang="it", **DEFAULTS)
    assert "frammenti non-host" in r["reasons"]


def test_cli_writes_table_and_flags_missing_files(tmp_path):
    indir = tmp_path / "triage"
    indir.mkdir()
    write_sample(indir, "GOOD")
    write_sample(indir, "HOSTY", nonhost=500)
    (indir / "HALF.triage_reads.txt").write_text("1000\n", encoding="utf-8")  # other two files missing
    out = tmp_path / "res" / "triage.tsv"
    p = subprocess.run([sys.executable, STEP, "--in", str(indir), "--out", str(out)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].split("\t") == tr.COLUMNS
    rows = {l.split("\t")[0]: dict(zip(tr.COLUMNS, l.split("\t"))) for l in lines[1:]}
    assert rows["GOOD"]["decision"] == "pass"
    assert rows["HOSTY"]["decision"] == "exclude"
    assert rows["HALF"]["decision"] == "review"
    assert "triage_qc.json" in rows["HALF"]["reasons"]
    assert "1 pass, 1 review, 1 exclude" in p.stdout


def test_cli_rejects_empty_dir(tmp_path):
    p = subprocess.run([sys.executable, STEP, "--in", str(tmp_path), "--out", str(tmp_path / "t.tsv")],
                       capture_output=True, text=True)
    assert p.returncode != 0
