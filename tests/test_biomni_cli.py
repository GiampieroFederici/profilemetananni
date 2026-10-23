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

import _biomni_core as core        # noqa: E402
import _biomni_consent as consent  # noqa: E402

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


class EnvWatchingClient(FakeClient):
    """Records what the provider variable held at the moment the model was asked."""

    def __init__(self, environ):
        super().__init__()
        self._environ = environ
        self.seen = []

    def ask(self, taxon, detected_by):
        self.seen.append(self._environ.get("OPENAI_API_KEY"))
        return super().ask(taxon, detected_by)


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
    # 2 taxa x 1 NCBI-confirmed source, 2 taxa x 1 invented reference number ([9]).
    # The two counts are separate: FakeClient reports no NCBI refusals.
    assert meta["confirmed"] == 2
    assert meta["invented_refs"] == 2
    assert meta["ncbi_dropped"] == 0


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
    # consent has to be informed: the box lists the species themselves, not just a count
    assert any("Latilactobacillus sakei" in s for s in seen)
    assert any("Staphylococcus xylosus" in s for s in seen)


def test_a_yes_at_the_prompt_records_the_consent_once(tmp_path):
    client = FakeClient()
    _run(tmp_path, client=client, interactive=True, ask=lambda _p: "s", show=lambda _s: None)
    assert len(client.asked) == 2
    assert (tmp_path / ".biomni_consent.json").exists()


def test_an_unreadable_consent_file_asks_again_instead_of_crashing(tmp_path):
    """A truncated, empty or hand-edited .biomni_consent.json used to raise out of run().
    Unreadable consent must mean NO consent: ask again, send nothing until an explicit yes.
    """
    for broken in ('{"llm": "gpt-4o", "provi', "", "[]", "null", "not json at all"):
        (tmp_path / ".biomni_consent.json").write_text(broken, encoding="utf-8")
        client = FakeClient()
        rc = _run(tmp_path, client=client, interactive=True,
                  ask=lambda _p: "n", show=lambda _s: None)
        assert rc == 0, f"crashed or failed on {broken!r}"
        assert client.asked == [], f"sent taxa without consent on {broken!r}"


def test_a_key_from_the_credentials_file_reaches_the_provider(tmp_path):
    """The provider SDK reads the key from the environment: resolving it is not enough."""
    creds = tmp_path / "creds"
    consent.store_credential(creds, "OPENAI_API_KEY", "from-file")
    env = {}
    client = EnvWatchingClient(env)
    assert _run(tmp_path, client=client, assume_yes=True, environ=env, cred_path=creds) == 0
    assert client.seen == ["from-file", "from-file"]


def test_a_key_already_in_the_environment_is_never_overwritten(tmp_path):
    creds = tmp_path / "creds"
    consent.store_credential(creds, "OPENAI_API_KEY", "from-file")
    env = {"OPENAI_API_KEY": "from-env"}
    client = EnvWatchingClient(env)
    assert _run(tmp_path, client=client, assume_yes=True, environ=env, cred_path=creds) == 0
    assert client.seen == ["from-env", "from-env"]


def _wizard(tmp_path, answers, secret, status=0, **kw):
    """No key anywhere and a terminal to ask on: the guided setup takes over.

    `secret` is what the user pastes at the masked prompt, `answers` the visible replies
    (storage choice, then the consent prompt). check_key is stubbed: no network, no cost.
    """
    replies, seen = list(answers), []
    opts = dict(environ={}, interactive=True,
                ask=lambda _p: replies.pop(0), show=seen.append,
                ask_secret=lambda _p: secret, check_key=lambda _pr, _k: status)
    opts.update(kw)
    return _run(tmp_path, **opts), seen


def test_the_wizard_stores_the_pasted_key_and_the_run_uses_it(tmp_path):
    env = {}
    client = EnvWatchingClient(env)
    rc, _seen = _wizard(tmp_path, ["1", "s"], "sk-supersegretissima", client=client, environ=env)
    assert rc == 0
    assert (tmp_path / "creds").read_text(encoding="utf-8").strip() == \
        "OPENAI_API_KEY=sk-supersegretissima"
    assert client.seen == ["sk-supersegretissima", "sk-supersegretissima"]


def test_the_wizard_never_echoes_or_writes_the_key_anywhere_but_the_credentials_file(
        tmp_path, capsys):
    secret = "sk-supersegretissima"
    rc, seen = _wizard(tmp_path, ["1", "s"], secret)
    assert rc == 0
    captured = capsys.readouterr()
    assert secret not in captured.out and secret not in captured.err
    assert not any(secret in s for s in seen)
    assert secret not in (tmp_path / ".biomni_consent.json").read_text(encoding="utf-8")
    for name in ("dossier_taxa.md", "dossier_taxa.tsv", "run_meta.json"):
        assert secret not in (tmp_path / "o" / name).read_text(encoding="utf-8")


def test_the_wizard_can_use_the_key_for_this_run_without_storing_it(tmp_path):
    rc, _seen = _wizard(tmp_path, ["2", "s"], "sk-effimera")
    assert rc == 0
    assert not (tmp_path / "creds").exists()


def test_a_key_the_provider_refuses_stops_and_is_never_stored(tmp_path):
    client = FakeClient()
    rc, seen = _wizard(tmp_path, [], "sk-sbagliata", status=401, client=client)
    assert rc != 0
    assert client.asked == []
    assert not (tmp_path / "creds").exists()
    assert any("non è valida" in s for s in seen)


def test_a_terminal_that_cannot_be_read_gives_up_instead_of_raising(tmp_path):
    """isatty() can claim a terminal that yields nothing (Git Bash on Windows does);
    the wizard must end with the plain-language message, not a traceback."""
    def _eof(_prompt):
        raise EOFError
    client = FakeClient()
    rc = _run(tmp_path, client=client, environ={}, interactive=True,
              ask=_eof, show=lambda _s: None, ask_secret=_eof,
              check_key=lambda _pr, _k: 0)
    assert rc != 0
    assert client.asked == []
    assert not (tmp_path / "creds").exists()


def test_choosing_the_local_option_explains_how_and_sends_nothing(tmp_path):
    client = FakeClient()
    rc, seen = _wizard(tmp_path, [], "L", client=client)
    assert rc != 0
    assert client.asked == []
    assert any("ollama" in s.lower() for s in seen)


def test_dry_run_never_builds_the_real_biomni_agent(tmp_path):
    lazy = step50._LazyClient("gpt-4o")
    assert _run(tmp_path, client=lazy, dry_run=True) == 0
    assert lazy._client is None


def test_a_refused_consent_never_builds_the_real_biomni_agent(tmp_path):
    lazy = step50._LazyClient("gpt-4o")
    assert _run(tmp_path, client=lazy, dry_run=False, assume_yes=False, interactive=False) != 0
    assert lazy._client is None
