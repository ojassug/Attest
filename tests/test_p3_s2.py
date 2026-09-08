"""Gate for P3-S2 — criterion matching.

Graded against ground truth committed in P1-S4, before any matching code existed. Two of those
expectations turned out to be wrong and the model was right: `denial.md` stated no CPT codes, and
neither `clean.md` nor `gap.md` stated the patient's age. Both notes were corrected rather than
the expectations relaxed — see DECISIONS.md.

The gap test is the one that matters. Flagging *a* gap is worthless; it has to flag the right
criterion, for the right reason, and as INSUFFICIENT rather than UNMET — the note asserts an
augmentation trial happened but names no agent, dose or duration, which is a question for the
practice, not an argument with the payer.
"""

import pytest

from attest.corpus import all_cases, load_case
from attest.criteria.match import match_all, match_criterion
from attest.models import Polarity, Verdict
from conftest import needs_model

pytestmark = pytest.mark.p3_s2

CASES = all_cases()


@pytest.fixture(scope="module")
def coverage():
    return {
        c.name: match_all(c.pack, c.note_text, case_id=c.case_id, note_id=c.name) for c in CASES
    }


@needs_model
def test_clean_case_all_criteria_met(coverage):
    cov = coverage["clean"]
    not_met = [(v.criterion_id, v.verdict.value) for v in cov.verdicts if v.verdict is not Verdict.MET]
    assert not not_met, f"fully documented case has unmet criteria: {not_met}"


@needs_model
def test_gap_case_flags_the_expected_criterion(coverage):
    """The right criterion, not merely some criterion."""
    case = load_case("gap")
    cov = coverage["gap"]
    flagged = {v.criterion_id for v in cov.verdicts if v.verdict is not Verdict.MET}
    assert flagged == set(case.expected_gaps), (
        f"expected exactly {case.expected_gaps} to be flagged, got {sorted(flagged)}"
    )


@needs_model
def test_gap_is_insufficient_not_unmet(coverage):
    """An undocumented fact is a question for the practice. Calling it UNMET would start an
    argument with the payer over something the note simply never said."""
    verdict = next(v for v in coverage["gap"].verdicts if v.criterion_id == "ps-04b")
    assert verdict.verdict is Verdict.INSUFFICIENT


@needs_model
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_all_verdicts_match_ground_truth(case, coverage):
    want = case.verdicts
    wrong = [
        (v.criterion_id, v.verdict.value, want[v.criterion_id].value)
        for v in coverage[case.name].verdicts
        if v.verdict != want[v.criterion_id]
    ]
    assert not wrong, f"{case.name}: {wrong}"


@needs_model
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_every_criterion_receives_exactly_one_verdict(case, coverage):
    ids = [v.criterion_id for v in coverage[case.name].verdicts]
    assert ids == case.pack.criterion_ids


@needs_model
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_met_verdicts_carry_evidence(case, coverage):
    """A criterion asserted as met with no quote is untraceable, which is the thing the product
    promises never to produce."""
    bare = [
        v.criterion_id
        for v in coverage[case.name].verdicts
        if v.verdict is Verdict.MET and not v.spans
    ]
    assert not bare, f"{case.name}: met with no supporting evidence: {bare}"


@needs_model
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_every_verdict_has_reasoning(case, coverage):
    for v in coverage[case.name].verdicts:
        assert v.reasoning.strip(), f"{v.criterion_id} has no reasoning"


@needs_model
def test_contraindications_are_met_by_documented_absence(coverage):
    """Polarity handled correctly: 'No history of seizure disorder' satisfies an exclusion."""
    case = load_case("denial")
    absent_ids = {c.id for c in case.pack.criteria if c.polarity is Polarity.ABSENT}
    assert absent_ids, "the denial pack has no contraindications to exercise"
    for v in coverage["denial"].verdicts:
        if v.criterion_id in absent_ids:
            assert v.verdict is Verdict.MET, f"{v.criterion_id} should be met by documented absence"


def test_missing_verdict_degrades_to_insufficient():
    """If the model skips a criterion, it must not read as satisfied. No API call."""
    from attest.criteria.match import DraftCoverage, DraftVerdict, _to_verdict

    draft = DraftVerdict(
        criterion_id="x", verdict=Verdict.INSUFFICIENT, quotes=[], reasoning="not assessed"
    )
    assert _to_verdict(draft, "n").verdict is Verdict.INSUFFICIENT


def test_blank_quotes_are_dropped_not_stored():
    """An empty span would be an untraceable claim wearing evidence's clothing."""
    from attest.criteria.match import DraftVerdict, _to_verdict

    draft = DraftVerdict(
        criterion_id="x", verdict=Verdict.MET, quotes=["   ", "", "real quote"], reasoning="r"
    )
    spans = _to_verdict(draft, "n").spans
    assert [s.quote for s in spans] == ["real quote"]


def test_criteria_are_rendered_with_their_polarity():
    """The model cannot judge a contraindication correctly if it is not told it is one."""
    from attest.criteria.match import _render_criteria

    case = load_case("denial")
    rendered = _render_criteria(case.pack.criteria)
    assert "must be ABSENT (contraindication)" in rendered
    assert "must be PRESENT" in rendered
