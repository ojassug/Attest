"""Gate for P3-S3 — the deterministic evidence-span verifier.

This is the step that converts "evidence-traceable by design" from a prompt instruction into a
property of the code. Every test here is deterministic: no model, no cassette, no quota.

The load-bearing test is `test_paraphrase_is_rejected`. A semantically identical paraphrase MUST
fail, because paraphrase is the hallucination failure mode being defended against. If a future
session finds the verifier "too strict" and loosens it, that test is the tripwire.
"""

import pytest

from attest.models import CriteriaCoverage, CriterionVerdict, EvidenceSpan, Verdict
from attest.verifier import verify_coverage, verify_span

pytestmark = pytest.mark.p3_s3


# A note shaped like the real corpus: an em-dash, sentences wrapped across lines, and a
# double space after a full stop. All three are things a model's quote will not reproduce
# byte-for-byte even when it is quoting honestly.
NOTE = """PROGRESS NOTE — 2026-08-14

Patient has failed two adequate antidepressant trials: sertraline 200 mg daily
for 10 weeks and venlafaxine XR 225 mg daily for 9 weeks.

PHQ-9 score is 21, consistent with severe major depression.  No history of
seizure disorder.
"""


def span(quote: str, span_id: str = "c-01-0") -> EvidenceSpan:
    return EvidenceSpan(span_id=span_id, note_id="note", quote=quote)


# --------------------------------------------------------------------------- the five DoD tests


def test_exact_quote_verifies():
    """A quote copied character-for-character off one line of the note."""
    result = verify_span(span("PHQ-9 score is 21"), NOTE)

    assert result.verified
    assert result.reason == ""


def test_paraphrase_is_rejected():
    """Semantically identical, not verbatim. This rejection is the entire point of the step."""
    result = verify_span(span("PHQ-9 score of 21"), NOTE)

    assert not result.verified
    assert result.start is None and result.end is None


def test_whitespace_and_newline_variants_verify():
    """Honest quotes flatten the note's line wrapping and repeated spaces. Those still verify."""
    across_a_line_break = "sertraline 200 mg daily for 10 weeks"
    across_a_double_space = "severe major depression. No history of seizure disorder."

    assert verify_span(span(across_a_line_break), NOTE).verified
    assert verify_span(span(across_a_double_space), NOTE).verified


def test_fabricated_quote_is_rejected():
    """Nothing resembling this sentence is in the note."""
    result = verify_span(span("Patient reports active suicidal ideation"), NOTE)

    assert not result.verified


def test_returned_offsets_are_correct():
    """Slicing the note at the returned offsets reproduces the quote.

    For a quote whose whitespace already matches the note, that is exact equality. For a quote
    that flattened a line break it is equality under the same normalisation the verifier allows —
    the offsets still bracket exactly the run of note text that was matched, and nothing more.
    """
    exact = verify_span(span("PHQ-9 score is 21"), NOTE)
    assert NOTE[exact.start : exact.end] == "PHQ-9 score is 21"

    wrapped = verify_span(span("sertraline 200 mg daily for 10 weeks"), NOTE)
    sliced = NOTE[wrapped.start : wrapped.end]
    assert sliced == wrapped.matched_text
    assert " ".join(sliced.split()) == "sertraline 200 mg daily for 10 weeks"
    assert "\n" in sliced, "this quote is supposed to span the note's line break"


# --------------------------------------------------------------------------- offsets and strictness


def test_offsets_index_the_original_note_not_a_normalised_copy():
    """The whole point of returning offsets is that a reader can find the quote in the real file."""
    result = verify_span(span("seizure disorder"), NOTE)

    assert NOTE[result.start : result.end] == "seizure disorder"
    assert result.start == NOTE.index("seizure disorder")


def test_case_difference_is_rejected():
    """'Verbatim' is case-sensitive on purpose.

    Deliberate, and guarded so it is not quietly relaxed: a verifier that forgives case has
    started forgiving things, and the next thing it forgives is a changed number.
    """
    assert not verify_span(span("phq-9 score is 21"), NOTE).verified


def test_quote_longer_than_the_note_is_rejected():
    result = verify_span(span(NOTE + " and then some"), NOTE)

    assert not result.verified


# --------------------------------------------------------------------------- rejection reporting


def test_rejected_span_carries_its_quote_and_a_reason():
    """P3-S4 has to log the offending quote. It can only do that if the rejection carries it."""
    result = verify_span(span("Patient reports active suicidal ideation"), NOTE)

    assert result.quote == "Patient reports active suicidal ideation"
    assert result.reason, "a rejection with no reason is not auditable"


# --------------------------------------------------------------------------- verify_coverage


def coverage_with(*spans: EvidenceSpan) -> CriteriaCoverage:
    return CriteriaCoverage(
        case_id="SYNTH-001",
        pack_id="pacificsource-commercial-tms",
        verdicts=[
            CriterionVerdict(
                criterion_id="ps-01",
                verdict=Verdict.MET,
                spans=list(spans),
                reasoning="test fixture",
            )
        ],
    )


def test_verify_coverage_returns_one_result_per_span():
    report = verify_coverage(
        coverage_with(span("PHQ-9 score is 21", "a"), span("seizure disorder", "b")), NOTE
    )

    assert [r.span_id for r in report.results] == ["a", "b"]
    assert report.all_verified


def test_verify_coverage_separates_verified_from_rejected():
    report = verify_coverage(
        coverage_with(span("PHQ-9 score is 21", "real"), span("severe agoraphobia", "fake")), NOTE
    )

    assert report.verified_ids == {"real"}
    assert [r.span_id for r in report.rejected] == ["fake"]
    assert not report.all_verified


def test_verify_coverage_on_a_coverage_with_no_spans_is_vacuously_verified():
    """An INSUFFICIENT verdict carries no spans. That is not a verification failure."""
    report = verify_coverage(coverage_with(), NOTE)

    assert report.results == []
    assert report.all_verified
