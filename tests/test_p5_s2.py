"""Gate for P5-S2 — drafting the rebuttal.

This is the document that argues back at the payer, and it is the last surface where a fabricated
clinical claim could reach them. So the split is deliberate: **the model writes only the prose.**

- `policy_citation` comes from the pack, not the model — so "every citation resolves to a real
  source_section" is true by construction rather than by instruction.
- `supporting_span_ids` come from the verified coverage, not the model — `Rebuttal` carries
  `min_length=1` on that field, and handing that constraint to a model is the recorded failure
  where a `min_length` on `cpt_codes` taught it to invent procedure codes. Here it would invent a
  span id, which is the worst thing an appeal could contain.
- The **argument** is the model's job, and even there, any passage it puts in quotation marks must
  appear verbatim in the note or in the payer's own criterion text.

A criterion with no verified evidence gets no rebuttal at all. You cannot argue a point you cannot
evidence, and pretending otherwise is what this product exists to prevent.
"""

import re

import pytest

from attest.appeal.draft import NoEvidenceError, draft_rebuttal, draft_rebuttals
from attest.appeal.parse import parse_denial
from attest.corpus import load_case
from attest.criteria.match import match_all
from attest.models import ContestedCriterion, Verdict
from attest.verifier import _normalise, enforce_verification
from conftest import needs_model

pytestmark = pytest.mark.p5_s2

CASE = load_case("denial")
PACK = CASE.pack


@pytest.fixture(scope="module")
def coverage():
    matched = match_all(PACK, CASE.note_text, case_id=CASE.case_id, note_id="denial")
    return enforce_verification(matched, CASE.note_text).coverage


@pytest.fixture(scope="module")
def contested():
    return parse_denial(CASE.denial_text, PACK, case_id=CASE.case_id).contested


@pytest.fixture(scope="module")
def rebuttals(contested, coverage):
    """One batched call for the module."""
    return draft_rebuttals(contested, coverage, PACK)


# --------------------------------------------------------------------------- the DoD


@needs_model
def test_rebuttal_cites_real_policy_section(rebuttals):
    """Every citation resolves to a source_section present in the pack."""
    sections = {c.source_section for c in PACK.criteria}

    assert rebuttals
    for r in rebuttals:
        assert r.policy_citation in sections


@needs_model
def test_rebuttal_cites_verified_spans_only(rebuttals, coverage):
    """Nothing may be cited that the verifier has not confirmed appears in the note."""
    verified = {s.span_id for v in coverage.verdicts for s in v.spans if s.verified}

    cited = {i for r in rebuttals for i in r.supporting_span_ids}
    assert cited
    assert cited <= verified


@needs_model
def test_every_contested_criterion_is_addressed(rebuttals, contested):
    """A contested criterion left unrebutted is the one the payer denies on again."""
    assert {r.criterion_id for r in rebuttals} == {c.criterion_id for c in contested}


# --------------------------------------------------------------------------- the argument itself


def _resolve_disclosed_case_change(quoted: str) -> list[str]:
    """Candidate readings of a quote, allowing only a *disclosed* leading case change.

    `"[f]our trials..."` is the standard convention for lowering a capital to embed a quote
    mid-sentence. The brackets announce the alteration, which makes it the opposite of a silent
    paraphrase - and the words themselves are untouched. Nothing else is forgiven: an elision, an
    inserted word, or a changed number still fails, and so does an *undisclosed* case change.

    Same shape of rule as the Markdown-markup decision in P3-S4 - lexical and narrow, about a
    marked convention rather than about meaning.
    """
    candidates = [quoted]
    match = re.match(r"^\[([A-Za-z])\](.*)$", quoted, flags=re.DOTALL)
    if match:
        letter, rest = match.groups()
        candidates += [letter.lower() + rest, letter.upper() + rest]
    return candidates


@needs_model
def test_the_argument_quotes_nothing_it_cannot_support(rebuttals):
    """Any passage in quotation marks must come from the note or the payer's own criterion.

    An appeal that misquotes the record hands the payer a reason to dismiss the whole thing, and
    it is the exact failure the span verifier exists to prevent - reappearing as prose at the last
    step rather than as a span.
    """
    haystack = _normalise(CASE.note_text) + " " + _normalise(
        " ".join(c.text for c in PACK.criteria)
    )

    for r in rebuttals:
        for quoted in re.findall(r'"([^"]{12,})"', r.argument):
            assert any(
                _normalise(c) in haystack for c in _resolve_disclosed_case_change(quoted)
            ), (
                f"{r.criterion_id}: argument quotes text found in neither the note nor the "
                f"policy: {quoted[:80]!r}"
            )


def test_an_undisclosed_alteration_would_still_fail():
    """Guard on the guard: the allowance covers marked case changes and nothing else."""
    assert _resolve_disclosed_case_change("[f]our trials") == [
        "[f]our trials",
        "four trials",
        "Four trials",
    ]
    assert _resolve_disclosed_case_change("four trials") == ["four trials"]
    assert _resolve_disclosed_case_change("[several] trials") == ["[several] trials"]


@needs_model
def test_each_rebuttal_argues_its_own_criterion(rebuttals):
    for r in rebuttals:
        assert r.argument.strip()
        assert len(r.argument) > 80, "a one-line rebuttal is not an argument"


@needs_model
def test_singular_and_batched_agree(contested, coverage, rebuttals):
    """`draft_rebuttal` exists for re-drafting one criterion after a practice answers a gap."""
    one = draft_rebuttal(contested[0], coverage, PACK)

    assert one.criterion_id == contested[0].criterion_id
    assert one.policy_citation == next(
        r.policy_citation for r in rebuttals if r.criterion_id == one.criterion_id
    )


# --------------------------------------------------------------------------- no evidence, no claim


def test_a_criterion_with_no_verified_evidence_raises(coverage):
    """Deterministic: you cannot argue a point you cannot evidence."""
    stripped = coverage.model_copy(
        update={
            "verdicts": [
                v.model_copy(update={"spans": [], "verdict": Verdict.INSUFFICIENT})
                for v in coverage.verdicts
            ]
        }
    )

    with pytest.raises(NoEvidenceError):
        draft_rebuttal(ContestedCriterion(criterion_id="hho-03", payer_reason="x"), stripped, PACK)


def test_a_criterion_absent_from_the_pack_raises(coverage):
    with pytest.raises(KeyError):
        draft_rebuttal(ContestedCriterion(criterion_id="hho-99", payer_reason="x"), coverage, PACK)
