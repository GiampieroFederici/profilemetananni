# -*- coding: utf-8 -*-
# steps/_biomni_consent.py - provider detection, consent gate and credential handling
# for Phase C. No Biomni import: fully testable offline.
# Conda env: pmn_reports_py. Not meant to be run directly.
import json
import os
import pathlib
import stat as _stat
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
    (("ollama/",), Provider("ollama", "Ollama (locale)", "", "https://ollama.com/download", True)),
)
# azure/* and bedrock/* used to be listed here. They were removed because Biomni does not
# accept them: biomni/llm.py matches Azure on the prefix "azure-" (not "azure/") and reads
# OPENAI_API_KEY + OPENAI_ENDPOINT (not AZURE_OPENAI_API_KEY), and reaches Bedrock only from
# model names like "anthropic.claude-*" / "amazon.titan-*", never from a "bedrock/" prefix.
# Anything else raises ValueError inside get_llm. Declaring them here let a config pass our
# consent gate and fail later, deeper, with the provider named wrongly in the consent box -
# the one place that must be exact. Supporting them properly needs an Azure or AWS account to
# test against; until then, refusing the name up front is the honest behaviour.


def provider_for(llm: str) -> Provider:
    """Map a model name to its provider. Refuses to guess on an unknown name."""
    name = (llm or "").strip().lower()
    for prefixes, provider in _PROVIDERS:
        if any(name.startswith(p) for p in prefixes):
            return provider
    raise ValueError(
        f"unknown model '{llm}': use claude-*, gpt-*, gemini-*, groq/* or ollama/*"
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


def credentials_path() -> pathlib.Path:
    return pathlib.Path.home() / ".pmn" / "credentials"


def read_credentials(path) -> dict:
    """Read VAR=value lines. On POSIX a file wider than 0600 is REFUSED, not fixed."""
    path = pathlib.Path(path)
    if not path.exists():
        return {}
    if os.name == "posix":
        mode = _stat.S_IMODE(os.stat(path).st_mode)
        if mode != 0o600:
            raise PermissionError(
                f"{path} has permissions {oct(mode)}; expected 0600. "
                f"Fix it with: chmod 600 {path}"
            )
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def store_credential(path, env_var: str, value: str) -> str:
    """Write/replace one VAR=value line, 0600 on POSIX.

    Returns a warning to show the user (SPEC 6.4), or "" when none is needed: on Windows
    there is no POSIX chmod, so the file cannot be locked down to the current account and
    anyone else who can log into the machine could read it. The caller decides whether/how
    to display it; this module never prints.
    """
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lines = []
    if path.exists():
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                 if not ln.strip().startswith(f"{env_var}=")]
    lines.append(f"{env_var}={value}")
    # P18: il file nasce già 0600 (con write_text era 0644 fino al chmod); il chmod stringe un file vecchio più largo
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    if os.name == "posix":   # file che c'era già, più largo: si stringe PRIMA di scriverci la chiave
        os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    if os.name == "posix":
        os.chmod(path, 0o600)
        return ""
    return (
        f"ATTENZIONE: su Windows questo file ({path}) non può essere protetto come su "
        f"Linux/Mac (permessi 0600) — altri account sullo stesso computer potrebbero "
        f"leggerlo. Più sicuro: non salvare qui la chiave, ma impostare la variabile "
        f"d'ambiente {env_var}."
    )


def resolve_api_key(provider: Provider, environ, path):
    """Environment first, credentials file second. Local models need no key ('')."""
    if provider.local:
        return ""
    from_env = (environ or {}).get(provider.env_var, "")
    if from_env:
        return from_env
    return read_credentials(path).get(provider.env_var) or None


def check_api_key(provider: Provider, key: str):
    """SPEC 6.4 Passo 4: one minimal call to the provider, to fail in 2 seconds and not
    after 20 minutes of work.

    Returns 0 when the key is accepted, the HTTP status when the provider refuses it, -1
    when the provider cannot be reached at all, and None when no single call can check this
    provider. None means UNKNOWN and is never treated as a green light. Never raises: an
    exception escaping here could carry the request - and with it the key - into a
    traceback. The key travels in a header, never in the URL.
    """
    import urllib.error
    import urllib.request

    endpoints = {
        "openai": ("https://api.openai.com/v1/models",
                   {"Authorization": f"Bearer {key}"}),
        "groq": ("https://api.groq.com/openai/v1/models",
                 {"Authorization": f"Bearer {key}"}),
        "anthropic": ("https://api.anthropic.com/v1/models",
                      {"x-api-key": key, "anthropic-version": "2023-06-01"}),
        "google": ("https://generativelanguage.googleapis.com/v1beta/models",
                   {"x-goog-api-key": key}),
    }
    endpoint = endpoints.get(provider.key)
    if endpoint is None:
        return None
    url, headers = endpoint
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=headers, method="GET"), timeout=20
        ) as r:
            code = r.getcode()
        return 0 if 200 <= code < 300 else code
    except urllib.error.HTTPError as e:
        return int(e.code)
    except Exception:
        return -1


def translate_provider_error(status) -> str:
    """Turn a provider HTTP status into something a non-programmer can act on."""
    if status in (401, 403):
        return ("La chiave non è valida. Forse è incompleta o è stata revocata: "
                "creane una nuova e reincollala.")
    if status in (402, 429):
        return ("La chiave è valida ma l'account non ha credito o un metodo di pagamento "
                "attivo. Controlla la sezione fatturazione del fornitore.")
    return ("Non riesco a raggiungere il fornitore: controlla la connessione a internet "
            "o le impostazioni del proxy.")
