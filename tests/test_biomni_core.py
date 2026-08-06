# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "steps"))
import _biomni_core as core  # noqa: E402


MPA = """#mpa_vJan21
clade_name\tS1\tS2
k__Bacteria|s__Latilactobacillus_sakei\t40.0\t10.0
k__Bacteria|s__Staphylococcus_xylosus\t5.0\t0.0
k__Bacteria|s__Rare_bug\t0.0005\t0.0
"""

KRK = """taxon\tS1\tS2
Latilactobacillus sakei\t35.0\t12.0
Brochothrix thermosphacta\t2.0\t1.0
"""


@pytest.fixture()
def tables(tmp_path):
    m = tmp_path / "merged.txt"
    k = tmp_path / "kraken.tsv"
    m.write_text(MPA, encoding="utf-8")
    k.write_text(KRK, encoding="utf-8")
    return str(m), str(k)


def test_metaphlan_only(tables):
    m, _ = tables
    got = core.select_taxa(m, "", threshold_pct=0.001, max_taxa=50)
    assert ("Latilactobacillus sakei", "metaphlan") in got
    assert all(src == "metaphlan" for _, src in got)


def test_union_marks_shared_taxa(tables):
    m, k = tables
    got = dict(core.select_taxa(m, k, threshold_pct=0.001, max_taxa=50))
    assert got["Latilactobacillus sakei"] == "metaphlan+kraken"
    assert got["Staphylococcus xylosus"] == "metaphlan"
    assert got["Brochothrix thermosphacta"] == "kraken"


def test_threshold_drops_rare_taxa(tables):
    m, _ = tables
    got = dict(core.select_taxa(m, "", threshold_pct=0.001, max_taxa=50))
    assert "Rare bug" not in got


def test_max_taxa_is_a_hard_cap(tables):
    m, k = tables
    got = core.select_taxa(m, k, threshold_pct=0.001, max_taxa=2)
    assert len(got) == 2


def test_no_tables_returns_empty():
    assert core.select_taxa("", "", threshold_pct=0.001, max_taxa=5) == []
