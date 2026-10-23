# -*- coding: utf-8 -*-
import json
import os
import stat
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "steps"))
import _biomni_consent as cs  # noqa: E402


def test_provider_is_detected_from_the_model_name():
    assert cs.provider_for("gpt-4o").env_var == "OPENAI_API_KEY"
    assert cs.provider_for("claude-sonnet-5").env_var == "ANTHROPIC_API_KEY"
    assert cs.provider_for("gemini-2.0-pro").env_var == "GEMINI_API_KEY"


def test_local_model_needs_no_key():
    p = cs.provider_for("ollama/llama3.1")
    assert p.local is True
    assert p.env_var == ""


def test_unknown_model_raises_instead_of_guessing():
    try:
        cs.provider_for("supermodello-3000")
    except ValueError:
        return
    raise AssertionError("an unknown model must not be silently accepted")


def test_consent_is_valid_only_for_the_same_model_and_provider(tmp_path):
    path = cs.consent_record_path(str(tmp_path))
    p = cs.provider_for("gpt-4o")
    cs.save_consent(path, "gpt-4o", p, n_taxa=5)
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert cs.consent_is_valid(rec, "gpt-4o", p) is True
    assert cs.consent_is_valid(rec, "claude-sonnet-5", cs.provider_for("claude-sonnet-5")) is False
    # Change ONLY the provider: with model and provider changed together, dropping the
    # provider half of the rule would go unnoticed. A different provider is a different
    # recipient of the data, so the same model name must not carry the consent over.
    other = cs.Provider("anthropic", "Anthropic", "ANTHROPIC_API_KEY",
                        "https://console.anthropic.com/settings/keys", False)
    assert cs.consent_is_valid(rec, "gpt-4o", other) is False


def test_missing_consent_is_not_valid():
    assert cs.consent_is_valid(None, "gpt-4o", cs.provider_for("gpt-4o")) is False


def test_consent_record_never_contains_a_key(tmp_path):
    path = cs.consent_record_path(str(tmp_path))
    cs.save_consent(path, "gpt-4o", cs.provider_for("gpt-4o"), n_taxa=5)
    text = path.read_text(encoding="utf-8").lower()
    assert "key" not in text and "sk-" not in text


def test_environment_wins_over_the_credentials_file(tmp_path):
    path = tmp_path / "credentials"
    cs.store_credential(path, "OPENAI_API_KEY", "from-file")
    p = cs.provider_for("gpt-4o")
    got = cs.resolve_api_key(p, {"OPENAI_API_KEY": "from-env"}, path)
    assert got == "from-env"


def test_credentials_file_is_used_when_the_environment_is_empty(tmp_path):
    path = tmp_path / "credentials"
    cs.store_credential(path, "OPENAI_API_KEY", "from-file")
    got = cs.resolve_api_key(cs.provider_for("gpt-4o"), {}, path)
    assert got == "from-file"


def test_a_local_model_needs_no_key_at_all(tmp_path):
    got = cs.resolve_api_key(cs.provider_for("ollama/llama3.1"), {}, tmp_path / "nope")
    assert got == ""


def test_a_world_readable_credentials_file_is_refused(tmp_path):
    if os.name != "posix":
        pytest.skip("POSIX permissions only: this rule is UNVERIFIED on this machine")
    path = tmp_path / "credentials"
    cs.store_credential(path, "OPENAI_API_KEY", "secret")
    os.chmod(path, 0o644)
    try:
        cs.read_credentials(path)
    except PermissionError:
        return
    raise AssertionError("a world-readable credentials file must be refused")


def test_store_credential_writes_0600_on_posix(tmp_path):
    if os.name != "posix":
        pytest.skip("POSIX permissions only: this rule is UNVERIFIED on this machine")
    path = tmp_path / "credentials"
    cs.store_credential(path, "OPENAI_API_KEY", "secret")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_store_credential_warns_only_where_permissions_cannot_be_locked_down(tmp_path):
    path = tmp_path / "credentials"
    warning = cs.store_credential(path, "OPENAI_API_KEY", "secret")
    if os.name == "posix":
        assert warning == ""
    else:
        assert warning != ""


def test_a_provider_we_cannot_check_says_so_instead_of_claiming_the_key_works():
    """None means 'unknown' - never a green light. Built by hand, because no shipped
    provider lacks an endpoint any more: the rule must survive the next one that does.
    No network here: the function returns before making any request."""
    unknown = cs.Provider("sgland", "Custom endpoint", "CUSTOM_API_KEY", "https://x", False)
    assert cs.check_api_key(unknown, "irrelevant") is None


def test_a_model_name_biomni_cannot_resolve_is_refused_here_not_20_minutes_later():
    """azure/* and bedrock/* were declared by us and rejected by Biomni: biomni/llm.py
    matches "azure-" and "anthropic.claude-"/"amazon.titan-"/..., so these names raise
    ValueError inside get_llm. Passing our gate and failing there would name the wrong
    provider in the consent box - the one line that has to be exact."""
    for name in ("azure/gpt-4o", "bedrock/claude", "anthropic.claude-3-sonnet", "azure-gpt-4o"):
        with pytest.raises(ValueError):
            cs.provider_for(name)


def test_provider_errors_are_translated_into_plain_language():
    assert "valida" in cs.translate_provider_error(401)
    assert "credito" in cs.translate_provider_error(429)
    assert "raggiungere" in cs.translate_provider_error(None)
