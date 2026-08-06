# -*- coding: utf-8 -*-
# steps/_biomni_consent.py - provider detection, consent gate and credential handling
# for Phase C. No Biomni import: fully testable offline.
# Conda env: pmn_reports_py. Not meant to be run directly.
import json
import pathlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    env_var: str
    console_url: str
    local: bool


_PROVIDERS = (
    (("claude-",), Provider("anthropic", "Anthropic", "ANTHROPIC_API_KEY",
                            "https://console.anthropic.com/settings/keys", False)),
    (("gpt-", "o1-", "o3-"), Provider("openai", "OpenAI", "OPENAI_API_KEY",
                                      "https://platform.openai.com/api-keys", False)),
    (("gemini-",), Provider("google", "Google", "GEMINI_API_KEY",
                            "https://aistudio.google.com/apikey", False)),
    (("groq/",), Provider("groq", "Groq", "GROQ_API_KEY",
                          "https://console.groq.com/keys", False)),
    (("azure/",), Provider("azure", "Azure OpenAI", "AZURE_OPENAI_API_KEY",
                           "https://portal.azure.com", False)),
    (("bedrock/",), Provider("bedrock", "AWS Bedrock", "AWS_SECRET_ACCESS_KEY",
                             "https://console.aws.amazon.com/iam", False)),
    (("ollama/",), Provider("ollama", "Ollama (locale)", "", "https://ollama.com/download", True)),
)


def provider_for(llm: str) -> Provider:
    """Map a model name to its provider. Refuses to guess on an unknown name."""
    name = (llm or "").strip().lower()
    for prefixes, provider in _PROVIDERS:
        if any(name.startswith(p) for p in prefixes):
            return provider
    raise ValueError(
        f"unknown model '{llm}': use claude-*, gpt-*, gemini-*, groq/*, azure/*, "
        "bedrock/* or ollama/*"
    )


def consent_record_path(work_dir: str) -> pathlib.Path:
    return pathlib.Path(work_dir) / ".biomni_consent.json"


def consent_is_valid(record, llm: str, provider: Provider) -> bool:
    """Consent is tied to the exact model AND provider: change either and we ask again."""
    if not record:
        return False
    return record.get("llm") == llm and record.get("provider") == provider.key


def save_consent(path, llm: str, provider: Provider, n_taxa: int) -> None:
    """Record the consent. NEVER stores an API key."""
    from datetime import date
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"llm": llm, "provider": provider.key, "date": date.today().isoformat(),
             "authorised": "species names only", "n_taxa": n_taxa},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
