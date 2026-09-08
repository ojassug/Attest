"""Gate for P2-S2 — prior-authorization requirement lookup.

The negative test is the important one. Reporting "no authorization needed" because no policy was
found would cause a practice to deliver an unreimbursed service, so absence of a policy must
surface as UNKNOWN and never collapse into NOT_REQUIRED.
"""

import pytest

from attest.corpus import all_cases
from attest.models import PARequirement
from attest.tools.pa_lookup import check_pa_required

pytestmark = pytest.mark.p2_s2

CASES = all_cases()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_determination_matches_ground_truth(case):
    intake = case.intake
    got = check_pa_required(intake["cpt_codes"][0], intake["payer"], intake["plan"])
    assert got.requirement.value == case.raw["pa_required"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_determination_carries_a_citation(case):
    """A determination the practice cannot check against the source is not usable."""
    intake = case.intake
    got = check_pa_required(intake["cpt_codes"][0], intake["payer"], intake["plan"])
    assert got.policy_id == case.pack_id
    assert got.citation and str(case.pack.source_url) in got.citation
    assert got.rationale.strip()


def test_unmapped_cpt_returns_unknown_not_false():
    """The whole point of the three-state enum."""
    got = check_pa_required("00000", "PacificSource", "Commercial")
    assert got.requirement is PARequirement.UNKNOWN
    assert got.requirement is not PARequirement.NOT_REQUIRED
    assert got.policy_id is None


def test_unknown_payer_returns_unknown():
    got = check_pa_required("90867", "SomePayerWeHaveNeverHeardOf")
    assert got.requirement is PARequirement.UNKNOWN


def test_unknown_rationale_warns_against_misreading_it():
    """A bare UNKNOWN invites someone to treat it as 'probably fine'. The rationale must say
    plainly that it is not."""
    got = check_pa_required("00000", "PacificSource", "Commercial")
    text = got.rationale.lower()
    assert "not evidence" in text
    assert "confirm" in text


def test_wrong_plan_does_not_match_the_pack():
    """Criteria differ by plan, so a Commercial policy must not answer for a Medicaid member."""
    got = check_pa_required("90867", "PacificSource", "Medicaid")
    assert got.requirement is PARequirement.UNKNOWN


def test_plan_is_optional():
    """Omitting the plan matches on payer alone, for callers that do not know it yet."""
    got = check_pa_required("90867", "PacificSource")
    assert got.requirement is PARequirement.REQUIRED


def test_every_cpt_in_a_pack_resolves():
    for case in CASES:
        for cpt in case.pack.cpt_codes:
            got = check_pa_required(cpt, case.pack.payer, case.pack.plan)
            assert got.requirement is PARequirement.REQUIRED, f"{cpt} did not resolve"


def test_payer_match_is_case_insensitive():
    """Payer names arrive from extraction and vary in casing."""
    assert check_pa_required("90867", "pacificsource", "commercial").requirement is (
        PARequirement.REQUIRED
    )
