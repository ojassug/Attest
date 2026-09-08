"""Gate for P3-S4 — verifier enforcement in the pipeline.

P3-S3 proved a span can be checked. This step makes the check *binding*: a criterion whose
evidence does not verify cannot keep a favourable verdict, and the rejection has to be visible
afterwards. A verifier nothing is forced to obey is decoration.

The rule enforced here is deliberately blunt — any criterion carrying even one unverifiable span
drops to INSUFFICIENT. Evidence that is partly fabricated is not partly trustworthy, and
INSUFFICIENT is the honest verdict: we no longer know.
"""

import logging

import pytest

from attest.corpus import all_cases
from attest.criteria.match import match_all
from attest.models import CriteriaCoverage, CriterionVerdict, EvidenceSpan, Verdict
from attest.verifier import enforce_verification
from conftest import needs_model

pytestmark = pytest.mark.p3_s4


NOTE = """PROGRESS NOTE — 2026-08-14

PHQ-9 score is 21, consistent with severe major depression.  No history of
seizure disorder.
"""

REAL = "PHQ-9 score is 21"
FABRICATED = "Patient reports active suicidal ideation"


def span(quote: str, span_id: str) -> EvidenceSpan:
    return EvidenceSpan(span_id=span_id, note_id="note", quote=quote)


def coverage(*verdicts: CriterionVerdict) -> CriteriaCoverage:
    return CriteriaCoverage(
        case_id="SYNTH-001", pack_id="pacificsource-commercial-tms", verdicts=list(verdicts)
    )


def verdict(criterion_id: str, *spans: EvidenceSpan, value: Verdict = Verdict.MET):
    return CriterionVerdict(
        criterion_id=criterion_id, verdict=value, spans=list(spans), reasoning="test fixture"
    )


# --------------------------------------------------------------------------- the DoD


def test_unverifiable_span_downgrades_criterion():
    """A fabricated span must cost the criterion its verdict, not be quietly discarded."""
    result = enforce_verification(coverage(verdict("ps-01", span(FABRICATED, "bad"))), NOTE)

    (out,) = result.coverage.verdicts
    assert out.verdict == Verdict.INSUFFICIENT


def test_rejection_is_logged(caplog):
    """The audit log has to carry the offending quote, or the rejection is not auditable."""
    with caplog.at_level(logging.WARNING, logger="attest.audit"):
        enforce_verification(coverage(verdict("ps-01", span(FABRICATED, "bad"))), NOTE)

    assert FABRICATED in caplog.text
    assert "ps-01" in caplog.text


@needs_model
def test_no_unverified_span_survives():
    """Across all three cases, 100% of spans in the final coverage verify verbatim.

    Marked `needs_model` rather than `live`: this replays from cassettes, and DECISIONS.md
    reserves `live` for calls that genuinely cannot be replayed. Same precedent as P3-S2.
    """
    for case in all_cases():
        matched = match_all(case.pack, case.note_text, case_id=case.case_id, note_id=case.name)
        result = enforce_verification(matched, case.note_text)

        surviving = [s for v in result.coverage.verdicts for s in v.spans]
        assert surviving, f"{case.name}: enforcement left no evidence at all"
        assert all(s.verified for s in surviving), f"{case.name}: an unverified span survived"


# --------------------------------------------------------------------------- never silently dropped


def test_rejected_span_is_still_reachable_in_the_report():
    """Removed from the coverage so nothing can cite it — but not lost."""
    result = enforce_verification(coverage(verdict("ps-01", span(FABRICATED, "bad"))), NOTE)

    assert [r.span_id for r in result.report.rejected] == ["bad"]
    assert result.report.rejected[0].quote == FABRICATED


def test_rejected_span_does_not_survive_into_the_coverage():
    """P4 builds documents off the coverage, so an unverifiable quote must not be in it."""
    result = enforce_verification(coverage(verdict("ps-01", span(FABRICATED, "bad"))), NOTE)

    (out,) = result.coverage.verdicts
    assert out.spans == []


# --------------------------------------------------------------------------- the honest cases


def test_a_fully_verified_criterion_keeps_its_verdict():
    result = enforce_verification(coverage(verdict("ps-01", span(REAL, "good"))), NOTE)

    (out,) = result.coverage.verdicts
    assert out.verdict == Verdict.MET
    assert [s.span_id for s in out.spans] == ["good"]


def test_surviving_spans_carry_the_verified_flag_and_offsets():
    """models.py says only the verifier may set these. This is where they get set."""
    result = enforce_verification(coverage(verdict("ps-01", span(REAL, "good"))), NOTE)

    (kept,) = result.coverage.verdicts[0].spans
    assert kept.verified
    assert NOTE[kept.start : kept.end] == REAL


def test_a_criterion_with_one_bad_span_among_good_ones_is_still_downgraded():
    """Partly fabricated evidence is not partly trustworthy."""
    result = enforce_verification(
        coverage(verdict("ps-01", span(REAL, "good"), span(FABRICATED, "bad"))), NOTE
    )

    (out,) = result.coverage.verdicts
    assert out.verdict == Verdict.INSUFFICIENT


def test_only_the_offending_criterion_is_downgraded():
    """One bad criterion must not contaminate the rest of the case."""
    result = enforce_verification(
        coverage(
            verdict("ps-01", span(REAL, "good")),
            verdict("ps-02", span(FABRICATED, "bad")),
        ),
        NOTE,
    )

    by_id = {v.criterion_id: v.verdict for v in result.coverage.verdicts}
    assert by_id == {"ps-01": Verdict.MET, "ps-02": Verdict.INSUFFICIENT}


def test_an_insufficient_criterion_with_no_spans_is_untouched():
    """A gap is already the honest answer. Enforcement has nothing to do to it."""
    result = enforce_verification(
        coverage(verdict("ps-04b", value=Verdict.INSUFFICIENT)),
        NOTE,
    )

    (out,) = result.coverage.verdicts
    assert out.verdict == Verdict.INSUFFICIENT
    assert result.report.all_verified
