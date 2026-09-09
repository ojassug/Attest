"""Intake — turn a clinical note into a structured Case.

The model extracts; the code does bookkeeping. Identifiers and timestamps are generated here
rather than asked for, because a model asked to produce a case id will happily invent one, and an
invented identifier is indistinguishable from a real one downstream.

Extraction is deliberately conservative: fields absent from the note come back as null rather
than as a plausible guess. Guessing here would poison every later phase, since the criteria
matcher would then be checking the payer's rules against facts nobody wrote down.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import Field, ValidationError
from strands import Agent

from attest.cache import cached_structured
from attest.llm import build_model, model_id, with_retry
from attest.models import Base, Case, InsuranceInfo, ServiceRequest

SYSTEM_PROMPT = """\
You extract structured facts from clinical notes for a prior-authorization workflow.

Rules:
- Extract only what the note states. Never infer, complete, or normalise a value that is not
  written down.
- If a field is not stated in the note, return null for it. A null is correct and useful; a
  plausible guess is harmful, because downstream steps treat these as documented facts.
- Copy identifiers, codes and payer names exactly as they appear.
- Collect every CPT/HCPCS code the note requests, not just the first.
"""


class ExtractedCase(Base):
    """What the model is asked for. Note the absence of ids and timestamps — those are ours."""

    patient_ref: str = Field(description="Patient reference or pseudonym as written in the note.")
    payer: str = Field(description="Insurance payer name exactly as written.")
    plan: str = Field(description="Plan name, e.g. Commercial or Medicaid.")
    member_id: str = Field(description="Member/subscriber identifier as written.")
    group_number: str | None = Field(default=None, description="Group number, or null.")

    service: str = Field(description="The service being requested, in the note's own terms.")
    cpt_codes: list[str] = Field(
        description=(
            "Every CPT/HCPCS procedure code the note requests, e.g. 90867. Look anywhere in the "
            "note, including the treatment plan. Return an empty list if the note states none - "
            "do NOT supply codes that are typical for the service but absent from this note."
        ),
    )
    units_requested: int | None = Field(
        default=None, description="Total treatment units or sessions requested, or null."
    )
    duration_weeks: int | None = Field(default=None, description="Treatment duration, or null.")

    primary_diagnosis_code: str = Field(description="Primary ICD-10 code, e.g. F33.2.")
    primary_diagnosis_text: str = Field(description="Primary diagnosis in words.")


def _extract(note_text: str, attempts: int = 3) -> ExtractedCase:
    """Run the extraction, retrying when the model returns an unusable object.

    Free-tier flash models are intermittently sloppy with structured output — the same note can
    yield a complete extraction on one call and an empty ``cpt_codes`` on the next. That is model
    flakiness, not a documentation gap, and silently accepting it would surface later as a bogus
    "no procedure codes found" result. ``with_retry`` handles transport failures; this handles
    schema failures.
    """
    prompt = f"Extract the prior-authorization case from this clinical note.\n\n{note_text}"

    def produce() -> ExtractedCase:
        agent = Agent(model=build_model("fast"), system_prompt=SYSTEM_PROMPT)
        last: Exception | None = None
        for _ in range(attempts):
            try:
                return with_retry(
                    lambda: agent(prompt, structured_output_model=ExtractedCase)
                ).structured_output
            except ValidationError as exc:
                last = exc
        raise RuntimeError(
            f"extraction produced an invalid ExtractedCase after {attempts} attempts: {last}"
        ) from last

    return cached_structured(
        "intake", "fast", SYSTEM_PROMPT + prompt, ExtractedCase, produce
    )


class MissingFactError(RuntimeError):
    """A fact the request cannot proceed without is absent from the note.

    Raised rather than papered over. The product's rule is to ask the practice, never to assume -
    see Attest-PRODUCT.md section 6. Callers surface this as a question, not as a failure.
    """


def extract_case(
    note_text: str,
    insurance: InsuranceInfo | None = None,
    *,
    note_id: str = "note",
    case_id: str | None = None,
) -> Case:
    """Extract a Case from a clinical note.

    ``insurance`` overrides what the note says. In a real practice the coverage details come from
    the practice management system and are more reliable than the note header; passing None makes
    the model read them from the note, which is what the tests exercise.
    """
    extracted = _extract(note_text)

    if not extracted.cpt_codes:
        raise MissingFactError(
            "The note states no CPT/HCPCS procedure codes, so there is nothing to request "
            "authorization for. Ask the practice which codes are being billed - do not infer "
            "them from the service description."
        )

    return Case(
        case_id=case_id or extracted.patient_ref,
        note_id=note_id,
        patient_ref=extracted.patient_ref,
        insurance=insurance
        or InsuranceInfo(
            payer=extracted.payer,
            plan=extracted.plan,
            member_id=extracted.member_id,
            group_number=extracted.group_number,
        ),
        service=ServiceRequest(
            service=extracted.service,
            cpt_codes=extracted.cpt_codes,
            units_requested=extracted.units_requested,
            duration_weeks=extracted.duration_weeks,
        ),
        primary_diagnosis_code=extracted.primary_diagnosis_code,
        primary_diagnosis_text=extracted.primary_diagnosis_text,
        created_at=datetime.now(timezone.utc),
    )
