"""Domain models for the prior-authorization lifecycle.

Design rules encoded here, not left to prompts:

* An ``EvidenceSpan`` cannot hold an empty quote. Every clinical claim in every generated
  document traces back to one of these, so a blank quote is a traceability hole.
* ``Verdict`` and ``PARequirement`` are closed enums. In particular ``PARequirement`` has a
  third member, ``UNKNOWN`` — failing to find a policy must never be reported as "no prior
  authorization needed", because that causes an unreimbursed service.
* Spans carry ``verified`` and character offsets that only ``attest.verifier`` may set. A span
  is untrusted until the verifier has found it verbatim in the source note.

See DECISIONS.md for why these are invariants rather than conventions.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Verdict(str, Enum):
    """Whether the note supports a payer criterion."""

    MET = "met"
    UNMET = "unmet"
    INSUFFICIENT = "insufficient"


class PARequirement(str, Enum):
    """Whether prior authorization is required.

    ``UNKNOWN`` exists so that "we could not find a policy" is never collapsed into
    "no authorization is needed". See P2-S2.
    """

    REQUIRED = "required"
    NOT_REQUIRED = "not_required"
    UNKNOWN = "unknown"


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- intake


class InsuranceInfo(Base):
    payer: str
    plan: str
    member_id: str
    group_number: str | None = None


class ServiceRequest(Base):
    service: str
    cpt_codes: list[str] = Field(min_length=1)
    units_requested: int | None = None
    duration_weeks: int | None = None


class Case(Base):
    case_id: str
    note_id: str
    patient_ref: str = Field(description="Synthetic pseudonym. Never a real identifier.")
    insurance: InsuranceInfo
    service: ServiceRequest
    primary_diagnosis_code: str
    primary_diagnosis_text: str
    created_at: datetime


class PADetermination(Base):
    requirement: PARequirement
    policy_id: str | None = None
    citation: str | None = None
    rationale: str


# ------------------------------------------------------------------------- criteria


class Criterion(Base):
    id: str
    text: str = Field(description="Verbatim criterion text from the payer policy.")
    category: str
    source_section: str = Field(description="Where in the policy this criterion appears.")


class EvidenceSpan(Base):
    """A quote from the clinical note supporting a criterion.

    ``verified``, ``start`` and ``end`` are set only by ``attest.verifier``. A span that has
    not been through the verifier is untrusted and may not enter any generated document.
    """

    span_id: str
    note_id: str
    quote: str
    start: int | None = None
    end: int | None = None
    verified: bool = False

    @field_validator("quote")
    @classmethod
    def quote_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("evidence span quote may not be empty or whitespace-only")
        return v


class CriterionVerdict(Base):
    criterion_id: str
    verdict: Verdict
    spans: list[EvidenceSpan] = Field(default_factory=list)
    reasoning: str


class CriteriaCoverage(Base):
    case_id: str
    pack_id: str
    verdicts: list[CriterionVerdict] = Field(default_factory=list)


class GapItem(Base):
    criterion_id: str
    missing: str
    question: str = Field(description="Asked of the practice. Never guessed at.")


# --------------------------------------------------------------------------- packet


class Claim(Base):
    text: str
    supporting_span_ids: list[str] = Field(min_length=1)


class Justification(Base):
    claims: list[Claim] = Field(default_factory=list)


class ApprovalRecord(Base):
    """Proof a human approved this exact content.

    ``content_hash`` is what makes the gate meaningful: it shows that what was approved is
    what was emitted, rather than merely that an approval happened at some point.
    """

    approver: str
    approved_at: datetime
    content_hash: str


class Packet(Base):
    case_id: str
    coverage: CriteriaCoverage
    justification: Justification
    gaps: list[GapItem] = Field(default_factory=list)
    approval: ApprovalRecord | None = None


# --------------------------------------------------------------------------- appeal


class ContestedCriterion(Base):
    criterion_id: str
    payer_reason: str


class Denial(Base):
    denial_id: str
    case_id: str
    denial_date: date
    contested: list[ContestedCriterion] = Field(default_factory=list)
    unmapped_reasons: list[str] = Field(
        default_factory=list,
        description="Denial reasons that map to no known criterion. Surfaced, never dropped.",
    )


class Rebuttal(Base):
    criterion_id: str
    argument: str
    policy_citation: str
    supporting_span_ids: list[str] = Field(min_length=1)


class Appeal(Base):
    appeal_id: str
    case_id: str
    denial_id: str
    rebuttals: list[Rebuttal] = Field(default_factory=list)
    deadline: date
    approval: ApprovalRecord | None = None
