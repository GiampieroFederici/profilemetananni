# -*- coding: utf-8 -*-
import importlib.util
import json
import os
import sys

STEPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "steps")
sys.path.insert(0, STEPS)
_spec = importlib.util.spec_from_file_location("step50", os.path.join(STEPS, "50_biomni_dossier.py"))
step50 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(step50)

import _biomni_core as core  # noqa: E402

MPA = """clade_name\tS1
k__Bacteria|s__Latilactobacillus_sakei\t40.0
k__Bacteria|s__Staphylococcus_xylosus\t5.0
"""


class FakeClient:
    """Stands in for Biomni: fixed answers, zero cost, no network.

    One claim cites reference [1] (which exists) and one cites [9] (which does not) — so every
    run exercises both the surviving path and the automatic demotion to 'ipotesi'.
    """
    def __init__(self):
        self.asked = []

    def ask(self, taxon, detected_by):
        self.asked.append(taxon)
        return core.RawDossier(
            taxon=taxon, detected_by=detected_by,
            claims=(core.Claim("batteriocine", "sakacina", "noto", (1,)),
                    core.Claim("resistoma", "tet(M)", "noto", (9,))),
            references=(core.Citation("111", "Sakacin production", "2019"),),
        )


def _tables(tmp_path):
    m = tmp_path / "merged.txt"
    m.write_text(MPA, encoding="utf-8")
    return str(m)


def _run(tmp_path, client=None, **kw):
    """Hermetic call: cred_path always points inside tmp_path, never at the real home."""
    opts = dict(metaphlan=_tables(tmp_path), kraken="", out=str(tmp_path / "o"),
                llm="gpt-4o", work_dir=str(tmp_path), threshold_pct=0.001, max_taxa=5,
                dry_run=False, assume_yes=False, client=client or FakeClient(),
                environ={"OPENAI_API_KEY": "x"}, interactive=False,
                cred_path=tmp_path / "creds")
    opts.update(kw)
    return step50.run(**opts)


def test_dry_run_sends_nothing_and_needs_no_consent(tmp_path, capsys):
    client = FakeClient()
    assert _run(tmp_path, client=client, dry_run=True) == 0
    assert client.asked == []
    assert "Latilactobacillus sakei" in capsys.readouterr().out


def test_without_consent_and_without_a_terminal_it_stops(tmp_path):
    client = FakeClient()
    assert _run(tmp_path, client=client) != 0
    assert client.asked == []


def test_with_yes_flag_it_runs_and_writes_all_three_files(tmp_path):
    out = tmp_path / "o"
    assert _run(tmp_path, assume_yes=True) == 0
    assert (out / "dossier_taxa.md").exists()
    assert (out / "dossier_taxa.tsv").exists()
    meta = json.loads((out / "run_meta.json").read_text(encoding="utf-8"))
    assert meta["confirmed"] == 2 and meta["dropped"] == 2


def test_max_taxa_is_respected(tmp_path):
    client = FakeClient()
    _run(tmp_path, client=client, assume_yes=True, max_taxa=1)
    assert len(client.asked) == 1


def test_a_missing_key_stops_before_any_request(tmp_path):
    client = FakeClient()
    assert _run(tmp_path, client=client, assume_yes=True, environ={}) != 0
    assert client.asked == []


def test_the_key_never_appears_in_the_output(tmp_path):
    out = tmp_path / "o"
    _run(tmp_path, assume_yes=True, environ={"OPENAI_API_KEY": "sk-supersegreta"})
    for name in ("dossier_taxa.md", "dossier_taxa.tsv", "run_meta.json"):
        assert "sk-supersegreta" not in (out / name).read_text(encoding="utf-8")


def test_the_prompt_states_the_cost_and_a_no_sends_nothing(tmp_path):
    client, seen = FakeClient(), []
    rc = _run(tmp_path, client=client, interactive=True,
              ask=lambda _p: "n", show=seen.append)
    assert rc == 0
    assert client.asked == []
    assert any("COSTA SOLDI" in s for s in seen)


def test_a_yes_at_the_prompt_records_the_consent_once(tmp_path):
    client = FakeClient()
    _run(tmp_path, client=client, interactive=True, ask=lambda _p: "s", show=lambda _s: None)
    assert len(client.asked) == 2
    assert (tmp_path / ".biomni_consent.json").exists()


def test_dry_run_never_builds_the_real_biomni_agent(tmp_path):
    lazy = step50._LazyClient("gpt-4o")
    assert _run(tmp_path, client=lazy, dry_run=True) == 0
    assert lazy._client is None


def test_a_refused_consent_never_builds_the_real_biomni_agent(tmp_path):
    lazy = step50._LazyClient("gpt-4o")
    assert _run(tmp_path, client=lazy, dry_run=False, assume_yes=False, interactive=False) != 0
    assert lazy._client is None
