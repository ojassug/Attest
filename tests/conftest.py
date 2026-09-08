"""Shared test helpers.

The important one is `model_available`. Tests that need a model should run whenever the call can
be *served* — from a committed cassette or from a live key — not only when a key is present.
That is what lets a judge clone the repo with no credentials and still reproduce every result,
which the rules require (`Attest-PRODUCT.md` §1.4).
"""

from __future__ import annotations

import pytest

from attest.cache import CACHE_DIR, mode
from attest.llm import have_credentials


def has_cassettes() -> bool:
    return CACHE_DIR.exists() and any(CACHE_DIR.rglob("*.json"))


def model_available() -> bool:
    """True if model-backed tests can run at all.

    Cassettes cannot serve a request when caching is off or being refreshed, so those modes
    require a real key.
    """
    if have_credentials():
        return True
    return mode() == "on" and has_cassettes()


needs_model = pytest.mark.skipif(
    not model_available(),
    reason="no GOOGLE_API_KEY (see P0-S1) and no cassettes to replay",
)
