"""Model provider selection — the single place the rest of the codebase learns which model to use.

Everything else calls ``build_model()``. Swapping providers (Gemini today, Bedrock once the AWS
account is set up) is a change here and nowhere else. See DECISIONS.md.

Two tiers, because the pipeline's demands are wildly uneven:

* ``fast`` — intake extraction and denial parsing. Structured field-pulling; almost any current
  model does it.
* ``reasoning`` — criterion matching and appeal drafting. Needs drug-class knowledge, therapeutic
  dose judgement, date arithmetic against a duration bar, and exact verbatim quoting (the
  verifier rejects paraphrase). This is the step the product lives or dies on.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"

Tier = Literal["fast", "reasoning"]

# Chosen by probing the live API on 2026-09-08, not from the Strands docs, which still name
# gemini-2.5-* — those are retired for new keys and 404.
#
# Pro-class models (gemini-3.1-pro-preview, gemini-pro-latest) return 429 RESOURCE_EXHAUSTED on
# the free tier: there is effectively no free Pro quota. Flash-class is what a free key can
# actually run, and Gemini 3.x flash is materially stronger than the 2.5 flash the docs assume.
# gemini-3.8-flash is newer but returned 503 on every attempt - persistently capacity-constrained
# on the free tier. 3.6 and 3.5 both work and both handle structured output correctly.
#
# If billing is ever enabled, point ATTEST_MODEL_REASONING at a Pro model and re-run the P3 gate.
DEFAULT_MODELS: dict[str, str] = {
    "fast": "gemini-3.5-flash-lite",
    "reasoning": "gemini-3.6-flash",
}

KEY_VARS = ("GOOGLE_API_KEY", "GEMINI_API_KEY")


def load_env(path: Path = ENV_FILE) -> None:
    """Read KEY=VALUE lines from .env into os.environ without overwriting real env vars.

    Deliberately dependency-free and deliberately non-overriding: a key exported in the shell
    or injected by a deployment beats the local file.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def api_key() -> str | None:
    load_env()
    for var in KEY_VARS:
        if os.environ.get(var):
            return os.environ[var]
    return None


def have_credentials() -> bool:
    """Used to skip live tests cleanly rather than fail them with an opaque auth error."""
    return api_key() is not None


def model_id(tier: Tier = "reasoning") -> str:
    """Resolved model id. ``ATTEST_MODEL_FAST`` / ``ATTEST_MODEL_REASONING`` override."""
    load_env()
    return os.environ.get(f"ATTEST_MODEL_{tier.upper()}", DEFAULT_MODELS[tier])


def build_model(tier: Tier = "reasoning", **params):
    """The configured Strands model for a tier.

    Raises with an actionable message rather than letting an auth failure surface deep inside
    an agent run, where it reads as a model quality problem instead of a setup problem.
    """
    from strands.models.gemini import GeminiModel

    key = api_key()
    if not key:
        raise RuntimeError(
            "No Gemini API key found.\n"
            f"  Looked for: {' or '.join(KEY_VARS)} in the environment and in {ENV_FILE}\n"
            "  Get a free key at https://aistudio.google.com/apikey, then put it in .env as:\n"
            "      GOOGLE_API_KEY=your-key-here\n"
            "  .env is gitignored. Never commit it."
        )

    return GeminiModel(
        client_args={"api_key": key},
        model_id=model_id(tier),
        params=params or None,
    )


# --------------------------------------------------------------------------- resilience

RETRYABLE_MARKERS = ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "500")


def is_retryable(exc: BaseException) -> bool:
    """Transient free-tier failures: capacity 503s and quota 429s.

    Matched on message content because the Google SDK raises the same exception classes for
    permanent and transient conditions, so the class alone does not distinguish them.
    """
    return any(m in str(exc) for m in RETRYABLE_MARKERS)


def with_retry(call, *, attempts: int = 4, base_delay: float = 2.0):
    """Run a model call, retrying transient failures with exponential backoff.

    The free tier returns 503 "high demand" unpredictably. A full P3 run makes roughly thirty
    model calls, so without this a single blip fails the gate and looks like a real regression.
    Permanent errors (bad key, retired model) are re-raised immediately rather than retried.
    """
    import time

    last: BaseException | None = None
    for attempt in range(attempts):
        try:
            return call()
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            if not is_retryable(exc):
                raise
            last = exc
            if attempt < attempts - 1:
                time.sleep(base_delay * (2**attempt))
    raise RuntimeError(
        f"model call failed after {attempts} attempts; last error: {last}"
    ) from last
