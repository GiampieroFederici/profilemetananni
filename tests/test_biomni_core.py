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
Rare kraken\t0.0005\t0.0
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


def test_threshold_only_for_kraken(tables):
    """D128 (22/10): the threshold drops rare Kraken taxa only; MetaPhlAn is never filtered."""
    m, k = tables
    got = dict(core.select_taxa(m, k, threshold_pct=0.001, max_taxa=50))
    assert got["Rare bug"] == "metaphlan"
    assert "Rare kraken" not in got


def test_max_taxa_is_a_hard_cap(tables):
    m, k = tables
    got = core.select_taxa(m, k, threshold_pct=0.001, max_taxa=2)
    assert len(got) == 2


def test_no_tables_returns_empty():
    assert core.select_taxa("", "", threshold_pct=0.001, max_taxa=5) == []


REFS = (
    core.Citation("111", "Sakacin production in Latilactobacillus sakei", "2019"),
    core.Citation("222", "Biogenic amines in dry sausage", "2021"),
)


def _raw(**kw):
    base = dict(
        taxon="Latilactobacillus sakei",
        detected_by="metaphlan",
        claims=(core.Claim("ruolo", "starter wild-type", "noto", (1, 7)),),
        references=REFS,
    )
    base.update(kw)
    return core.RawDossier(**base)


def test_reference_number_out_of_range_is_removed():
    out, dropped = core.resolve_citations(_raw())
    assert out.claims[0].refs == (1,)
    assert dropped == 1


def test_claim_losing_all_references_keeps_an_empty_tuple():
    raw = _raw(claims=(core.Claim("resistoma", "tet(M)", "noto", (9,)),))
    out, dropped = core.resolve_citations(raw)
    assert out.claims[0].refs == ()
    assert dropped == 1


def test_zero_is_not_a_valid_reference_number():
    raw = _raw(claims=(core.Claim("ruolo", "x", "noto", (0,)),))
    out, _ = core.resolve_citations(raw)
    assert out.claims[0].refs == ()


def test_valid_references_survive_untouched():
    raw = _raw(claims=(core.Claim("ruolo", "x", "noto", (1, 2)),))
    out, dropped = core.resolve_citations(raw)
    assert out.claims[0].refs == (1, 2)
    assert dropped == 0


def test_unknown_category_is_rejected():
    with pytest.raises(ValueError):
        core.Claim("astrologia", "x", "noto", ())


def test_unknown_label_is_rejected():
    with pytest.raises(ValueError):
        core.Claim("ruolo", "x", "certissimo", ())


REAL = {
    "111": core.Citation("111", "Sakacin production in Latilactobacillus sakei", "2019"),
    "222": core.Citation("222", "Biogenic amines in dry sausage", "2021"),
}


def _fetch(pmid):
    return REAL.get(pmid)


def test_existing_pmids_are_confirmed():
    ok, dropped = core.verify_pmids({"111", "222"}, _fetch)
    assert set(ok) == {"111", "222"}
    assert dropped == []


def test_nonexistent_pmid_is_dropped():
    ok, dropped = core.verify_pmids({"111", "404404"}, _fetch)
    assert set(ok) == {"111"}
    assert dropped == ["404404"]


def test_network_failure_drops_rather_than_confirms():
    def boom(pmid):
        raise OSError("network down")

    ok, dropped = core.verify_pmids({"111"}, boom)
    assert ok == {}
    assert dropped == ["111"]


def test_noto_without_verified_citation_is_demoted():
    claims = (core.Claim("batteriocine", "sakacina", "noto", ()),)
    out = core.apply_labels(claims)
    assert out[0].label == "ipotesi"


def test_assente_without_verified_citation_is_demoted():
    claims = (core.Claim("ammine_biogene", "nessuna hdc", "assente", ()),)
    out = core.apply_labels(claims)
    assert out[0].label == "ipotesi"


def test_noto_with_verified_citation_survives():
    claims = (core.Claim("batteriocine", "sakacina", "noto", (1,)),)
    out = core.apply_labels(claims)
    assert out[0].label == "noto"


def test_atteso_is_left_alone_even_without_citations():
    claims = (core.Claim("cazymes", "inferito dal genere", "atteso", ()),)
    out = core.apply_labels(claims)
    assert out[0].label == "atteso"


def test_build_dossier_runs_all_the_rules():
    raw = core.RawDossier(
        taxon="Latilactobacillus sakei",
        detected_by="metaphlan+kraken",
        claims=(
            core.Claim("batteriocine", "sakacina", "noto", (1,)),
            core.Claim("resistoma", "tet(M)", "noto", (9,)),
        ),
        references=REFS,
    )
    d = core.build_dossier(raw)
    assert d.claims[0].label == "noto"
    assert d.claims[1].label == "ipotesi"
    assert d.dropped_refs == 1
    assert d.references == REFS


META = {
    "model": "gpt-4o", "provider": "OpenAI", "date": "2026-08-06",
    "n_taxa": 1, "confirmed": 1, "ncbi_dropped": 0, "invented_refs": 1,
}


def _one_dossier():
    raw = core.RawDossier(
        taxon="Latilactobacillus sakei",
        detected_by="metaphlan+kraken",
        claims=(core.Claim("batteriocine", "sakacina", "noto", (1,)),
                core.Claim("resistoma", "tet(M)", "noto", (9,))),
        references=REFS,
    )
    return core.build_dossier(raw)


def test_markdown_header_declares_the_llm_and_the_taxa_count():
    """n_taxa is given a value no other META field has, so putting the wrong count on
    that line is caught. The three source counts are pinned by the next test."""
    head = core.render_markdown([_one_dossier()], dict(META, n_taxa=2)).split("## ")[0]
    assert "LLM" in head
    assert "gpt-4o" in head and "OpenAI" in head
    assert "Taxa analizzati: 2" in head


def test_the_header_keeps_ncbi_refusals_apart_from_invented_reference_numbers():
    """Two different failures, two different lines: a PMID NCBI would not confirm is not
    the same thing as a reference number the model made up."""
    raw = core.RawDossier(
        taxon="Latilactobacillus sakei", detected_by="metaphlan",
        claims=(core.Claim("batteriocine", "sakacina", "noto", (1,)),),
        references=REFS, ncbi_dropped=7,
    )
    d = core.build_dossier(raw)
    assert d.ncbi_dropped == 7
    head = core.render_markdown(
        [d], dict(META, confirmed=3, ncbi_dropped=7, invented_refs=5)
    ).split("## ")[0]
    assert "3 confermate" in head
    assert "7 rifiutate" in head
    assert "scartati: 5" in head


def test_the_bibliography_lists_every_retrieved_source_even_uncited_ones():
    """The old name promised a leak check it could not perform: it asserted a PMID that
    appears in no fixture and on no code path. The leak rule is pinned, per claim, by the
    two tests below. What this one really checks is the other half: "Fonti consultate" is
    the full list of what WE retrieved, so 222 must appear even though no surviving claim
    cites it."""
    md = core.render_markdown([_one_dossier()], META)
    biblio = md.split("Fonti consultate:")[1]
    assert "PMID 111" in biblio
    assert "PMID 222" in biblio


def test_tsv_has_one_row_per_claim_and_the_right_header():
    tsv = core.render_tsv([_one_dossier()])
    lines = tsv.strip().split("\n")
    assert lines[0].split("\t") == [
        "taxon", "rilevato_da", "categoria", "affermazione",
        "etichetta", "citazioni_verificate",
    ]
    assert len(lines) == 3


def test_tsv_marks_the_demoted_claim_as_ipotesi():
    tsv = core.render_tsv([_one_dossier()])
    assert "\tipotesi\t" in tsv


def test_demoted_claim_shows_no_pmid_on_its_own_line():
    """A claim with no surviving reference (resistoma, refs=(9,) -> dropped -> ipotesi)
    must not print any PMID as evidence, on its own markdown line or its own TSV cell.
    The document as a whole legitimately lists every reference under "Fonti consultate",
    so the check has to be scoped to the claim's own line/cell, not the whole output."""
    d = _one_dossier()
    md = core.render_markdown([d], META)
    line = next(l for l in md.split("\n") if l.startswith("- resistoma:"))
    assert "PMID" not in line

    tsv = core.render_tsv([d])
    row = next(r for r in tsv.split("\n") if "\tresistoma\t" in r)
    assert row.split("\t")[-1] == ""


def test_claim_shows_only_its_own_pmid_not_a_sibling_claims_reference():
    """The batteriocine claim cites only reference 1 (PMID 111). Reference 2 (PMID 222)
    exists in the dossier and is cited by nothing, so it must not show up on this claim's
    line even though it legitimately appears elsewhere in the document (Fonti consultate)."""
    d = _one_dossier()
    md = core.render_markdown([d], META)
    line = next(l for l in md.split("\n") if l.startswith("- batteriocine:"))
    assert "PMID 111" in line
    assert "PMID 222" not in line
