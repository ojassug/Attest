"""Gate for P1-S1 — domain models.

The interesting tests here are the negative ones. The product's core promise is that no
clinical claim appears without traceable evidence, and these assert the type system refuses
the shapes that would let an untraceable claim through.
"""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from attest.models import (
    Appeal,
    ApprovalRecord,
    Case,
    Claim,
    ContestedCriterion,
    CriteriaCoverage,
    Criterion,
    CriterionVerdict,
    Denial,
    EvidenceSpan,
    GapItem,
    InsuranceInfo,
    Justification,
    PADetermination,
    PARequirement,
    Packet,
    Rebuttal,
    ServiceRequest,
    Verdict,
)

pytestmark = pytest.mark.p1_s1

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


def a_span(span_id: str = "s1") -> EvidenceSpan:
    return EvidenceSpan(span_id=span_id, note_id="n1", quote="PHQ-9 score of 22.")


def a_case() -> Case:
    return Case(
        case_id="c1",
        note_id="n1",
        patient_ref="SYNTH-001",
        insurance=InsuranceInfo(payer="PacificSource", plan="Commercial", member_id="M1"),
        service=ServiceRequest(service="rTMS", cpt_codes=["90867"], units_requested=36),
        primary_diagnosis_code="F33.2",
        primary_diagnosis_text="Major depressive disorder, recurrent, severe",
        created_at=NOW,
    )


SAMPLES = [
    a_case(),
    a_span(),
    Criterion(id="c-01", text="Patient is 18 years of age or older.", category="eligibility", source_section="IV.A.1"),
    CriterionVerdict(criterion_id="c-01", verdict=Verdict.MET, spans=[a_span()], reasoning="Age documented."),
    CriteriaCoverage(case_id="c1", pack_id="p1", verdicts=[]),
    GapItem(criterion_id="c-02", missing="No dose recorded.", question="What dose was prescribed?"),
    Claim(text="Patient is 34 years old.", supporting_span_ids=["s1"]),
    Justification(claims=[Claim(text="x", supporting_span_ids=["s1"])]),
    ApprovalRecord(approver="Dr. Vance", approved_at=NOW, content_hash="abc123"),
    PADetermination(requirement=PARequirement.REQUIRED, policy_id="p1", citation="IV.A", rationale="Listed."),
    Denial(denial_id="d1", case_id="c1", denial_date=date(2026, 9, 1)),
    ContestedCriterion(criterion_id="c-01", payer_reason="Not documented."),
    Rebuttal(criterion_id="c-01", argument="It is.", policy_citation="IV.A.1", supporting_span_ids=["s1"]),
    Appeal(appeal_id="a1", case_id="c1", denial_id="d1", deadline=date(2026, 10, 1)),
]


@pytest.mark.parametrize("obj", SAMPLES, ids=lambda o: type(o).__name__)
def test_models_roundtrip(obj):
    """Every model survives a JSON round trip unchanged — they cross process and session
    boundaries constantly (session store, artifacts, handoffs)."""
    assert type(obj).model_validate_json(obj.model_dump_json()) == obj


@pytest.mark.parametrize("blank", ["", "   ", "\n\t "])
def test_evidence_span_rejects_empty_quote(blank):
    with pytest.raises(ValidationError):
        EvidenceSpan(span_id="s1", note_id="n1", quote=blank)


def test_verdict_is_closed_enum():
    with pytest.raises(ValidationError):
        CriterionVerdict(criterion_id="c-01", verdict="probably", reasoning="x")


def test_pa_requirement_has_unknown():
    """Absence of a policy must be expressible as UNKNOWN, never as NOT_REQUIRED."""
    assert PARequirement.UNKNOWN.value == "unknown"
    assert {m.value for m in PARequirement} == {"required", "not_required", "unknown"}


def test_claim_requires_supporting_span():
    """A claim with no evidence is exactly what the product promises never to emit."""
    with pytest.raises(ValidationError):
        Claim(text="Patient has failed four antidepressants.", supporting_span_ids=[])


def test_rebuttal_requires_supporting_span():
    with pytest.raises(ValidationError):
        Rebuttal(criterion_id="c-01", argument="x", policy_citation="IV.A", supporting_span_ids=[])


def test_span_starts_unverified():
    """Spans are untrusted until the verifier says otherwise."""
    s = a_span()
    assert s.verified is False and s.start is None and s.end is None


def test_service_request_requires_a_cpt_code():
    with pytest.raises(ValidationError):
        ServiceRequest(service="rTMS", cpt_codes=[])


def test_unknown_fields_are_rejected():
    """extra='forbid' catches a model inventing fields during structured output."""
    with pytest.raises(ValidationError):
        Criterion(id="c-01", text="x", category="y", source_section="z", confidence=0.9)
