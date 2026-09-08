"""On-disk cache for model responses.

Two reasons this exists, and the second matters more than the first.

1. **Quota.** The Gemini free tier allows 20 requests per day *per model*. A full pipeline run
   over three cases makes roughly thirty calls, so without caching the test suite cannot be run
   twice in a day, let alone iterated on.

2. **Judge-testability.** The rules require the project to be testable by judges for free. With
   cassettes committed, `./scripts/verify.sh ALL` reproduces every result with no API key at all.
   That is worth more than the quota saving.

Cache keys hash the model id and the full input, so changing a prompt, a schema or a note
invalidates the entry automatically — a stale cassette can never silently mask a regression.

Control with `ATTEST_CACHE`:
  ``on`` (default) — read from cache, write on miss
  ``off``          — bypass entirely, always call the API
  ``refresh``      — ignore existing entries and re-record them
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Callable, TypeVar

from pydantic import BaseModel

from attest.llm import load_env

T = TypeVar("T", bound=BaseModel)

CACHE_DIR = Path(__file__).resolve().parents[2] / "cassettes"


def mode() -> str:
    load_env()
    return os.environ.get("ATTEST_CACHE", "on").lower()


def _key(namespace: str, model_id: str, payload: str) -> str:
    digest = hashlib.sha256(f"{namespace}\0{model_id}\0{payload}".encode()).hexdigest()
    return digest[:32]


def path_for(namespace: str, model_id: str, payload: str) -> Path:
    return CACHE_DIR / namespace / f"{_key(namespace, model_id, payload)}.json"


def cached_structured(
    namespace: str,
    model_id: str,
    payload: str,
    result_type: type[T],
    produce: Callable[[], T],
) -> T:
    """Return a cached structured result, or produce and record one.

    A cassette that fails to parse is treated as a miss and overwritten, so a schema change never
    leaves the suite stuck on an unreadable entry.
    """
    current = mode()
    entry = path_for(namespace, model_id, payload)

    if current != "off" and current != "refresh" and entry.exists():
        try:
            return result_type.model_validate_json(entry.read_text())
        except Exception:
            pass  # stale or malformed - fall through and re-record

    result = produce()

    if current != "off":
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text(result.model_dump_json(indent=2))

    return result


def is_cached(namespace: str, model_id: str, payload: str) -> bool:
    return path_for(namespace, model_id, payload).exists()
