"""Gate for P4-S1 — the medical-necessity justification.

This is the document that argues the case to the payer, and it is the last place a fabricated
clinical claim could still get out. The defence is structural rather than instructed: a claim is
*built from* verified spans, so there is no code path that can produce one without evidence.

Deterministic on purpose. Every claim is derived from a criterion the matcher marked MET and the
spans the verifier confirmed, so `test_all_referenced_spans_are_verified` holds by construction
rather than by hope. It also costs no quota, which matters against a 20-request-per-day ceiling —
and it sidesteps `Claim.supporting_span_ids`' `min_length=1`, which would otherwise pressure a
model into inventing span ids to satisfy the schema. See DECISIONS.md.
"""

from datetime import datetime, timezone

import pytest

from attest.agents.intake import extract_case
from attest.corpus import all_cases
from attest.criteria.match import match_all
from attest.models import (
    Case,
    CriteriaCoverage,
    CriterionVerdict,
    EvidenceSpan,
    InsuranceInfo,
    ServiceRequest,
    Verdict,
)
from attest.packet.justification import build_justification
from attest.verifier import enforce_verification
from conftest import needs_model

pytestmark = pytest.mark.p4_s1

PACK_ID = "pacificsource-commercial-tms"
CASE_ID = "SYNTH-002"

NOTE = "PHQ-9 score is 21. The patient is 47 years old. No history of seizure disorder."


def case(case_id: str = CASE_ID) -> Case:
    return Case(
        case_id=case_id,
        note_id="note",
        patient_ref="PT-0002",
        insurance=InsuranceInfo(payer="PacificSource", plan="Commercial", member_id="M-1"),
        service=ServiceRequest(service="TMS", cpt_codes=["90867"]),
        primary_diagnosis_code="F33.2",
        primary_diagnosis_text="Major depressive disorder, recurrent, severe",
        created_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
    )


def span(quote: str, span_id: str, *, verified: bool) -> EvidenceSpan:
    return EvidenceSpan(
        span_id=span_id, note_id="note", quote=quote, verified=verified, start=0, end=len(quote)
    )


def verdict(criterion_id: str, value: Verdict, *spans: EvidenceSpan) -> CriterionVerdict:
    return CriterionVerdict(
        criterion_id=criterion_id, verdict=value, spans=list(spans), reasoning="test fixture"
    )


def coverage(*verdicts: CriterionVerdict, case_id: str = CASE_ID) -> CriteriaCoverage:
    return CriteriaCoverage(case_id=case_id, pack_id=PACK_ID, verdicts=list(verdicts))


def met(criterion_id: str, span_id: str = "s1") -> CriterionVerdict:
    return verdict(criterion_id, Verdict.MET, span(NOTE, span_id, verified=True))


# --------------------------------------------------------------------------- the DoD


def test_every_claim_has_supporting_spans():
    """A claim with no evidence is an assertion, and assertions are what this product refuses."""
    justification = build_justification(coverage(met("ps-01"), met("ps-02", "s2")), case())

    assert justification.claims
    for claim in justification.claims:
        assert claim.supporting_span_ids


def test_all_referenced_spans_are_verified():
    """Every cited span id must be in the verified set the verifier produced."""
    enforced = enforce_verification(
        coverage(verdict("ps-01", Verdict.MET, span("PHQ-9 score is 21", "s1", verified=False))),
        NOTE,
    )

    justification = build_justification(enforced.coverage, case())
    cited = {i for c in justification.claims for i in c.supporting_span_ids}

    assert cited
    assert cited <= enforced.report.verified_ids


# --------------------------------------------------------------------------- what becomes a claim


def test_one_claim_per_met_criterion():
    justification = build_justification(coverage(met("ps-01"), met("ps-02", "s2")), case())

    assert len(justification.claims) == 2


def test_insufficient_criterion_produces_no_claim():
    """A gap is a question for the practice, not an argument to the payer."""
    assert build_justification(coverage(verdict("ps-01", Verdict.INSUFFICIENT)), case()).claims == []


def test_unmet_criterion_produces_no_claim():
    """Arguing a criterion the note shows is unsatisfied would hand the payer the denial."""
    assert build_justification(coverage(verdict("ps-01", Verdict.UNMET)), case()).claims == []


def test_claims_follow_the_policy_order():
    """The reviewer reads this against the payer's own criteria list."""
    justification = build_justification(coverage(met("ps-03", "s3"), met("ps-01", "s1")), case())

    assert [c.supporting_span_ids for c in justification.claims] == [["s1"], ["s3"]]


# --------------------------------------------------------------------------- the safety property


def test_unverified_spans_are_never_cited():
    """The structural guarantee: only what the verifier blessed can be cited."""
    mixed = verdict(
        "ps-01",
        Verdict.MET,
        span("PHQ-9 score is 21", "good", verified=True),
        span("Patient reports suicidal ideation", "bad", verified=False),
    )

    (claim,) = build_justification(coverage(mixed), case()).claims

    assert claim.supporting_span_ids == ["good"]
    assert "bad" not in claim.supporting_span_ids


def test_a_coverage_that_never_went_through_the_verifier_yields_no_claims():
    """Fails safe, and loudly enough to notice: raw matcher output cites nothing.

    Spans default to verified=False, so skipping enforcement produces an empty justification
    rather than an unverified one.
    """
    raw = coverage(verdict("ps-01", Verdict.MET, span(NOTE, "s1", verified=False)))

    assert build_justification(raw, case()).claims == []


def test_a_claim_cites_only_its_own_criterions_spans():
    justification = build_justification(coverage(met("ps-01", "a"), met("ps-02", "b")), case())

    assert [c.supporting_span_ids for c in justification.claims] == [["a"], ["b"]]


# --------------------------------------------------------------------------- content and failure


def test_claim_quotes_the_payer_requirement():
    """The reviewer has to see the bar being claimed as met, in the payer's words."""
    from attest.corpus import load_case

    requirement = next(c for c in load_case("gap").pack.criteria if c.id == "ps-01").text

    (claim,) = build_justification(coverage(met("ps-01")), case()).claims

    assert requirement in claim.text


def test_case_id_mismatch_fails_loudly():
    """A justification built from another case's coverage would argue the wrong patient."""
    with pytest.raises(ValueError):
        build_justification(coverage(met("ps-01")), case(case_id="SOMEONE-ELSE"))


# --------------------------------------------------------------------------- real data


@needs_model
def test_every_case_justifies_only_from_verified_evidence():
    for expected in all_cases():
        matched = match_all(
            expected.pack, expected.note_text, case_id=expected.case_id, note_id=expected.name
        )
        enforced = enforce_verification(matched, expected.note_text)
        real_case = extract_case(expected.note_text, case_id=expected.case_id)

        justification = build_justification(enforced.coverage, real_case)
        cited = {i for c in justification.claims for i in c.supporting_span_ids}

        assert justification.claims, f"{expected.name}: no claims built"
        assert cited <= enforced.report.verified_ids, f"{expected.name}: cited an unverified span"
        assert all(c.supporting_span_ids for c in justification.claims)
