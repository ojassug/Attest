"""On-disk cache for model responses.

Two reasons this exists, and the second matters more than the first.

1. **Quota.** The Gemini free tier allows 20 requests per day *per model*. A full pipeline run
   over three cases makes roughly thirty calls, so without caching the test suite cannot be run
   twice in a day, let alone iterated on.

2. **Judge-testability.** The rules require the project to be testable by judges for free. With
   cassettes committed, `./scripts/verify.sh ALL` reproduces every result with no API key at all.
   That is worth more than the quota saving.

Cache keys hash the **tier** and the full input — deliberately not the model id. Free-tier daily
quotas are per model, so models get rotated when one is exhausted; keying on the model id would
discard every cassette each time that happens. The model that produced an entry is recorded
*inside* it instead, so results stay attributable for the P8-S3 metrics without being fragile.

Changing a prompt, a schema or a note still invalidates the entry automatically — a stale
cassette can never silently mask a regression.

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


def _key(namespace: str, tier: str, payload: str) -> str:
    digest = hashlib.sha256(f"{namespace}\0{tier}\0{payload}".encode()).hexdigest()
    return digest[:32]


def path_for(namespace: str, tier: str, payload: str) -> Path:
    return CACHE_DIR / namespace / f"{_key(namespace, tier, payload)}.json"


def cached_structured(
    namespace: str,
    tier: str,
    payload: str,
    result_type: type[T],
    produce: Callable[[], T],
) -> T:
    """Return a cached structured result, or produce and record one.

    A cassette that fails to parse is treated as a miss and overwritten, so a schema change never
    leaves the suite stuck on an unreadable entry.
    """
    import json
    from datetime import datetime, timezone

    from attest.llm import model_id as resolve_model

    current = mode()
    entry = path_for(namespace, tier, payload)

    if current not in ("off", "refresh") and entry.exists():
        try:
            body = json.loads(entry.read_text(encoding="utf-8"))
            return result_type.model_validate(body["value"])
        except Exception:
            pass  # stale or malformed - fall through and re-record

    result = produce()

    if current != "off":
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text(
            json.dumps(
                {
                    "tier": tier,
                    "model_id": resolve_model(tier),  # attribution, not part of the key
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "value": result.model_dump(mode="json"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    return result


def is_cached(namespace: str, tier: str, payload: str) -> bool:
    return path_for(namespace, tier, payload).exists()
