"""Gate for P3-S5 — the gap list.

The gap list is the product's answer to the question "what do we do when the note does not say
enough?". The answer is: ask the practice, and never guess.

The distinction this step turns on is INSUFFICIENT versus UNMET, and it is not cosmetic.
INSUFFICIENT means the note does not say enough to tell, which is a question for the practice.
UNMET means the note shows the requirement is genuinely not satisfied, which is an argument to
have with the payer. Only the first is a gap. Collapsing them would send practices chasing
documentation that cannot exist.
"""

import pytest

from attest.criteria.gaps import build_gap_list
from attest.corpus import all_cases, load_case
from attest.criteria.match import match_all
from attest.models import CriteriaCoverage, CriterionVerdict, EvidenceSpan, Verdict
from attest.verifier import enforce_verification
from conftest import needs_model

pytestmark = pytest.mark.p3_s5

PACK_ID = "pacificsource-commercial-tms"


def coverage(*verdicts: CriterionVerdict) -> CriteriaCoverage:
    return CriteriaCoverage(case_id="SYNTH-002", pack_id=PACK_ID, verdicts=list(verdicts))


def verdict(criterion_id: str, value: Verdict, reasoning: str = "test fixture", spans=()):
    return CriterionVerdict(
        criterion_id=criterion_id, verdict=value, spans=list(spans), reasoning=reasoning
    )


# --------------------------------------------------------------------------- the DoD


@needs_model
def test_gap_case_produces_expected_gap():
    """The criterion id flagged must match ground truth exactly.

    Flagging *a* gap is not enough — a gap list that names the wrong criterion sends the practice
    hunting for the wrong document. Marked `needs_model` rather than `live` because it replays
    from cassettes; see DECISIONS.md.
    """
    case = load_case("gap")
    matched = match_all(case.pack, case.note_text, case_id=case.case_id, note_id=case.name)

    gaps = build_gap_list(matched)

    assert [g.criterion_id for g in gaps] == case.expected_gaps == ["ps-04b"]


def test_every_gap_asks_a_question():
    """A gap that does not ask anything is a complaint, not a request."""
    gaps = build_gap_list(
        coverage(
            verdict("ps-04b", Verdict.INSUFFICIENT),
            verdict("ps-05a", Verdict.INSUFFICIENT),
        )
    )

    assert len(gaps) == 2
    for gap in gaps:
        assert gap.question.strip()
        assert gap.question.rstrip().endswith("?")


# --------------------------------------------------------------------------- INSUFFICIENT only


def test_met_criteria_are_not_gaps():
    assert build_gap_list(coverage(verdict("ps-01", Verdict.MET))) == []


def test_unmet_is_not_a_gap():
    """UNMET is an argument with the payer, not a question for the practice.

    The note answered the question; the answer was no. Asking the practice to document something
    the record shows is absent sends them chasing a document that cannot exist.
    """
    assert build_gap_list(coverage(verdict("ps-01", Verdict.UNMET))) == []


def test_gaps_preserve_pack_order():
    """The practice reads this as a checklist, so it should follow the policy's own order."""
    gaps = build_gap_list(
        coverage(
            verdict("ps-05a", Verdict.INSUFFICIENT),
            verdict("ps-01", Verdict.INSUFFICIENT),
        )
    )

    assert [g.criterion_id for g in gaps] == ["ps-01", "ps-05a"]


# --------------------------------------------------------------------------- content of a gap


def test_gap_says_what_is_missing_using_the_matchers_reasoning():
    """The matcher already worked out precisely what the note failed to establish.

    Reusing it costs no quota and is more specific than any template could be.
    """
    why = "The note does not document the agent, the dose, or the duration."
    (gap,) = build_gap_list(coverage(verdict("ps-04b", Verdict.INSUFFICIENT, reasoning=why)))

    assert gap.missing == why


def test_gap_question_quotes_the_payer_requirement():
    """The practice needs to see the bar it is being measured against, verbatim."""
    case = load_case("gap")
    requirement = next(c for c in case.pack.criteria if c.id == "ps-04b").text

    (gap,) = build_gap_list(coverage(verdict("ps-04b", Verdict.INSUFFICIENT)))

    assert requirement in gap.question


def test_gap_question_names_the_payer():
    (gap,) = build_gap_list(coverage(verdict("ps-04b", Verdict.INSUFFICIENT)))

    assert "PacificSource" in gap.question


# --------------------------------------------------------------------------- integration


@needs_model
def test_clean_and_denial_cases_have_no_gaps():
    """Both are fully documented. A gap list that invents work is worse than none."""
    for name in ("clean", "denial"):
        case = load_case(name)
        matched = match_all(case.pack, case.note_text, case_id=case.case_id, note_id=case.name)

        assert build_gap_list(matched) == []
        assert case.expected_gaps == []


@needs_model
def test_every_case_matches_its_ground_truth_gaps():
    for case in all_cases():
        matched = match_all(case.pack, case.note_text, case_id=case.case_id, note_id=case.name)

        assert [g.criterion_id for g in build_gap_list(matched)] == case.expected_gaps


def test_a_verifier_downgraded_criterion_becomes_a_gap():
    """P3-S4 downgrades unverifiable evidence to INSUFFICIENT. That must surface as a question.

    Otherwise a criterion can be quietly stripped of its evidence and never asked about — the
    silent drop the whole verifier design exists to prevent.
    """
    fabricated = EvidenceSpan(span_id="bad", note_id="gap", quote="Patient is 47 years old")
    enforced = enforce_verification(
        coverage(verdict("ps-01", Verdict.MET, spans=[fabricated])), "A note saying nothing."
    )

    gaps = build_gap_list(enforced.coverage)

    assert [g.criterion_id for g in gaps] == ["ps-01"]


# --------------------------------------------------------------------------- failure modes


def test_unknown_pack_fails_loudly():
    """A gap list built against the wrong pack would quote requirements at the wrong payer."""
    with pytest.raises(Exception):
        build_gap_list(
            CriteriaCoverage(
                case_id="X",
                pack_id="no-such-pack",
                verdicts=[verdict("ps-04b", Verdict.INSUFFICIENT)],
            )
        )


def test_criterion_absent_from_the_pack_fails_loudly():
    with pytest.raises(Exception):
        build_gap_list(coverage(verdict("not-a-real-criterion", Verdict.INSUFFICIENT)))
