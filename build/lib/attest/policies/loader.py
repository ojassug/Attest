"""Loading and indexing policy packs."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from attest.policies.schema import PolicyPack

PACKS_DIR = Path(__file__).parent / "packs"


def load_pack(path: str | Path) -> PolicyPack:
    """Load and validate one pack. Raises on any schema violation — a malformed pack must
    fail loudly at load time rather than produce a half-cited appeal later."""
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a YAML mapping")
    return PolicyPack.model_validate(data)


def list_packs(packs_dir: str | Path | None = None) -> list[PolicyPack]:
    """Every pack on disk, ordered by pack_id."""
    directory = Path(packs_dir) if packs_dir is not None else PACKS_DIR
    packs = [load_pack(p) for p in sorted(directory.glob("*.yaml"))]
    return sorted(packs, key=lambda p: p.pack_id)


def find_pack(cpt: str, payer: str, plan: str | None = None) -> PolicyPack | None:
    """The pack covering this CPT for this payer, or None.

    Returning None is meaningful: the caller must translate it to PARequirement.UNKNOWN,
    never to "no prior authorization needed". See P2-S2.
    """
    for pack in list_packs():
        if cpt not in pack.cpt_codes:
            continue
        if pack.payer.lower() != payer.lower():
            continue
        if plan is not None and pack.plan.lower() != plan.lower():
            continue
        return pack
    return None
