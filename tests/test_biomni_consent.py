# -*- coding: utf-8 -*-
import json
import os
import sys

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


def test_missing_consent_is_not_valid():
    assert cs.consent_is_valid(None, "gpt-4o", cs.provider_for("gpt-4o")) is False


def test_consent_record_never_contains_a_key(tmp_path):
    path = cs.consent_record_path(str(tmp_path))
    cs.save_consent(path, "gpt-4o", cs.provider_for("gpt-4o"), n_taxa=5)
    text = path.read_text(encoding="utf-8").lower()
    assert "key" not in text and "sk-" not in text
