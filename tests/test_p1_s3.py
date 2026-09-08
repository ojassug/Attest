"""Gate for P1-S3 — the shipped TMS policy packs.

These packs are the citation backbone of every appeal, so the tests here are about
traceability rather than behaviour: each criterion must be attributable to a named section of
a named, retrievable policy, and the two packs must actually differ — shipping two packs that
say the same thing would not demonstrate that criteria are payer-specific.
"""

import pytest

from attest.models import Polarity
from attest.policies.loader import find_pack, list_packs

pytestmark = pytest.mark.p1_s3

PACKS = list_packs()
MIN_CRITERIA = 8


def test_both_packs_load():
    assert len(PACKS) == 2, f"expected 2 shipped packs, found {[p.pack_id for p in PACKS]}"


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.pack_id)
def test_packs_have_minimum_criteria(pack):
    assert len(pack.criteria) >= MIN_CRITERIA


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.pack_id)
def test_every_criterion_traceable(pack):
    """No criterion may enter an appeal without text, a category, and a policy section."""
    for c in pack.criteria:
        assert c.text.strip(), f"{pack.pack_id}/{c.id} has no text"
        assert c.category.strip(), f"{pack.pack_id}/{c.id} has no category"
        assert c.source_section.strip(), f"{pack.pack_id}/{c.id} has no source_section"


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.pack_id)
def test_source_urls_are_https(pack):
    assert pack.source_url.scheme == "https"


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.pack_id)
def test_appeal_window_states_its_source(pack):
    """An invented appeal deadline is worse than no deadline. Both packs currently declare
    their window as unconfirmed; this test exists so that stays visible rather than decaying
    into an assumed fact."""
    assert pack.appeal_window_source.strip()


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.pack_id)
def test_contraindications_are_marked_absent(pack):
    """A contraindication is satisfied when the finding is *absent*. If it were marked
    'present' the matcher would report every healthy patient as failing it."""
    for c in pack.criteria:
        if c.category == "contraindication":
            assert c.polarity is Polarity.ABSENT, f"{pack.pack_id}/{c.id} has wrong polarity"


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.pack_id)
def test_pack_covers_the_tms_cpt_codes(pack):
    assert {"90867", "90868", "90869"} <= set(pack.cpt_codes)


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.pack_id)
def test_pa_is_required(pack):
    """Both source policies state prior authorization is required. If this ever flips, the
    demo's premise changed and someone needs to notice."""
    assert pack.pa_required is True


def test_packs_are_from_different_payers():
    assert len({p.payer for p in PACKS}) == 2


def test_packs_impose_materially_different_criteria():
    """The product's claim is that criteria are payer-specific. Two identical packs would make
    that claim untestable, so assert the treatment-resistance bar actually differs."""
    by_payer = {p.payer: p for p in PACKS}
    highmark = by_payer["Highmark Health Options"]
    pacificsource = by_payer["PacificSource"]

    hho_tr = " ".join(c.text for c in highmark.criteria if c.category == "treatment_resistance")
    ps_tr = " ".join(c.text for c in pacificsource.criteria if c.category == "treatment_resistance")

    assert "four (4) trials" in hho_tr, "Highmark's four-trial bar is missing"
    assert "at least 8 weeks" in ps_tr, "PacificSource's 8-week duration bar is missing"
    assert hho_tr != ps_tr


def test_highmark_requires_psychotherapy_failure_and_pacificsource_does_not():
    """A concrete payer difference the demo leans on: the same patient can clear one payer's
    bar and fail the other's."""
    by_payer = {p.payer: p for p in PACKS}
    assert any(c.category == "psychotherapy" for c in by_payer["Highmark Health Options"].criteria)
    assert not any(c.category == "psychotherapy" for c in by_payer["PacificSource"].criteria)


def test_find_pack_resolves_a_real_cpt():
    pack = find_pack(cpt="90867", payer="PacificSource", plan="Commercial")
    assert pack is not None and pack.pack_id == "pacificsource-commercial-tms"


def test_criterion_ids_are_unique_across_packs():
    """Coverage records reference criterion ids; collisions across packs would silently
    misattribute evidence."""
    ids = [f"{c.id}" for p in PACKS for c in p.criteria]
    assert len(ids) == len(set(ids)), "criterion ids collide across packs"
