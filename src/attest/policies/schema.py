"""Policy pack schema.

A pack is the machine-readable form of one payer's published clinical policy for one
service. Packs are **data, never code** — that is what keeps the engine specialty-agnostic
and lets a new specialty ship without touching agent logic (see DECISIONS.md).

Every field that exists here to support citation is mandatory. A criterion the product
cannot attribute back to a named section of a named, retrievable policy is worthless in an
appeal, because the entire argument is "your own published policy says this".
"""

from __future__ import annotations

from datetime import date

from pydantic import ConfigDict, Field, HttpUrl, field_validator, model_validator

from attest.models import Base, Criterion


class PolicyPack(Base):
    model_config = ConfigDict(extra="forbid")

    pack_id: str
    payer: str
    plan: str
    service: str
    cpt_codes: list[str] = Field(min_length=1)

    source_url: HttpUrl = Field(description="Where the policy was published.")
    source_title: str
    retrieved_date: date = Field(description="Policies change; record when this was read.")

    pa_required: bool
    appeal_window_days: int = Field(gt=0, description="Days from denial to appeal deadline.")

    criteria: list[Criterion] = Field(min_length=1)

    @field_validator("source_url")
    @classmethod
    def source_must_be_https(cls, v: HttpUrl) -> HttpUrl:
        if v.scheme != "https":
            raise ValueError("policy source_url must be https")
        return v

    @model_validator(mode="after")
    def criterion_ids_must_be_unique(self) -> "PolicyPack":
        ids = [c.id for c in self.criteria]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate criterion ids in pack {self.pack_id!r}: {dupes}")
        return self

    def criterion(self, criterion_id: str) -> Criterion:
        for c in self.criteria:
            if c.id == criterion_id:
                return c
        raise KeyError(f"no criterion {criterion_id!r} in pack {self.pack_id!r}")

    @property
    def criterion_ids(self) -> list[str]:
        return [c.id for c in self.criteria]
