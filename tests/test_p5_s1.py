"""Gate for P5-S1 — parsing a denial letter into contested criteria.

A denial letter is prose written by the payer. Turning it into `ContestedCriterion` entries is
what makes an appeal answerable: each contested criterion becomes an argument with evidence, and
anything that maps to no criterion becomes something the practice has to be told about.

Two properties matter more than accuracy here:

1. **A criterion id the model proposes is not a criterion id until the pack agrees.** The model
   suggests a mapping; code checks it against the pack. An id that is not in the pack becomes an
   unmapped reason, never a fabricated mapping — the same discipline the span verifier applies to
   quotes.
2. **No reason is ever dropped.** A payer reason that maps to nothing is the one most likely to
   sink a resubmission, because the practice never learns it was raised.
"""

from datetime import date

import pytest

from attest.appeal.parse import parse_denial, resolve_contested
from attest.corpus import load_case
from conftest import needs_model

pytestmark = pytest.mark.p5_s1


CASE = load_case("denial")
PACK = CASE.pack
GROUND_TRUTH = CASE.raw["denial"]


@pytest.fixture(scope="module")
def denial():
    """One model call for the whole module - denial letters are not cheap to re-parse."""
    return parse_denial(CASE.denial_text, PACK, case_id=CASE.case_id)


# --------------------------------------------------------------------------- the DoD


@needs_model
def test_contested_ids_match_ground_truth(denial):
    """The wrong criterion id sends the appeal arguing something the payer never raised."""
    assert sorted(c.criterion_id for c in denial.contested) == GROUND_TRUTH["expected_contested"]


@needs_model
def test_unmappable_reason_is_surfaced_not_dropped(denial):
    """The site-of-service reason maps to no criterion in the pack.

    It is also the reason most likely to sink a resubmission, because a practice that never hears
    about it will fix the two clinical criteria and be denied again for the same third thing.
    """
    assert len(denial.unmapped_reasons) == GROUND_TRUTH["expected_unmapped_reason_count"]
    assert any("site" in r.lower() for r in denial.unmapped_reasons)


# --------------------------------------------------------------------------- the parsed denial


@needs_model
def test_denial_date_is_parsed(denial):
    """P5-S4 computes the appeal deadline from this date. A wrong date is a missed appeal."""
    assert denial.denial_date == date.fromisoformat(GROUND_TRUTH["denial_date"])


@needs_model
def test_denial_is_bound_to_its_case(denial):
    assert denial.case_id == CASE.case_id
    assert denial.denial_id


@needs_model
def test_every_contested_criterion_carries_the_payer_reason(denial):
    """The rebuttal answers the payer's words, so they have to survive parsing."""
    for contested in denial.contested:
        assert contested.payer_reason.strip()


@needs_model
def test_no_reason_is_lost(denial):
    """Every reason in the letter ends up in exactly one of contested or unmapped."""
    assert len(denial.contested) + len(denial.unmapped_reasons) == 3


# --------------------------------------------------------------------------- the safety property

# Deterministic: these exercise the boundary where a model's proposal is checked against the pack.
# No model call, no quota.


def test_a_criterion_id_not_in_the_pack_becomes_an_unmapped_reason():
    """The model may propose an id. Only the pack can confirm one."""
    contested, unmapped = resolve_contested(
        [("hho-03", "four trials not documented"), ("hho-99", "invented criterion")], PACK
    )

    assert [c.criterion_id for c in contested] == ["hho-03"]
    assert unmapped == ["invented criterion"]


def test_an_empty_mapping_becomes_an_unmapped_reason():
    contested, unmapped = resolve_contested([("", "site of service requirement")], PACK)

    assert contested == []
    assert unmapped == ["site of service requirement"]


def test_resolve_contested_never_drops_a_reason():
    reasons = [("hho-03", "a"), ("hho-99", "b"), ("", "c"), ("hho-04", "d")]

    contested, unmapped = resolve_contested(reasons, PACK)

    assert len(contested) + len(unmapped) == len(reasons)


def test_duplicate_criterion_ids_are_collapsed():
    """Two payer paragraphs about the same criterion are one contested criterion."""
    contested, _ = resolve_contested(
        [("hho-03", "first paragraph"), ("hho-03", "second paragraph")], PACK
    )

    assert [c.criterion_id for c in contested] == ["hho-03"]
    assert "first paragraph" in contested[0].payer_reason
    assert "second paragraph" in contested[0].payer_reason


def test_contested_follows_pack_order():
    contested, _ = resolve_contested([("hho-04", "second"), ("hho-03", "first")], PACK)

    assert [c.criterion_id for c in contested] == ["hho-03", "hho-04"]
