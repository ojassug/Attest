"""Access to the synthetic corpus and its committed ground truth.

Ground truth is written *before* any matching code exists (P1-S4, ahead of P3). That ordering
is deliberate: it makes every later Definition of Done falsifiable. Without it, "the criteria
matcher works" is a judgment call, and a session can mark a step done on vibes.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from attest.models import Verdict
from attest.paths import data_dir
from attest.policies.loader import PACKS_DIR, load_pack
from attest.policies.schema import PolicyPack

DATA_DIR = data_dir() / "synthetic"
EXPECTED_DIR = DATA_DIR / "expected"

CASE_NAMES = ("clean", "gap", "denial")


class ExpectedCase:
    """One synthetic case and what the pipeline is required to produce for it."""

    def __init__(self, name: str, raw: dict):
        self.name = name
        self.raw = raw

    @property
    def case_id(self) -> str:
        return self.raw["case_id"]

    @property
    def pack_id(self) -> str:
        return self.raw["pack_id"]

    @property
    def intake(self) -> dict:
        return self.raw["intake"]

    @property
    def note_text(self) -> str:
        return (DATA_DIR / self.raw["note_file"]).read_text(encoding="utf-8")

    @property
    def denial_text(self) -> str | None:
        f = self.raw.get("denial_file")
        return (DATA_DIR / f).read_text(encoding="utf-8") if f else None

    @property
    def verdicts(self) -> dict[str, Verdict]:
        return {k: Verdict(v) for k, v in self.raw["verdicts"].items()}

    @property
    def expected_gaps(self) -> list[str]:
        return list(self.raw["expected_gaps"])

    @property
    def pack(self) -> PolicyPack:
        return load_pack(PACKS_DIR / f"{self.pack_id}.yaml")

    def __repr__(self) -> str:
        return f"ExpectedCase({self.name})"


@lru_cache(maxsize=None)
def load_case(name: str) -> ExpectedCase:
    return ExpectedCase(name, json.loads((EXPECTED_DIR / f"{name}.json").read_text(encoding="utf-8")))


def all_cases() -> list[ExpectedCase]:
    return [load_case(n) for n in CASE_NAMES]
