"""Gate for P2-S1 — note to structured Case.

Graded against `data/synthetic/expected/*.json`, which was committed in P1-S4 before any
extraction code existed. Codes, payer and plan are asserted exactly; the free-text service name
is asserted loosely, because "rTMS" and "transcranial magnetic stimulation" are both correct and
pinning the wording would test phrasing rather than extraction.
"""

import pytest

from attest.agents.intake import ExtractedCase, extract_case
from attest.corpus import all_cases
from attest.llm import have_credentials
from attest.models import Case
from conftest import model_available, needs_model

pytestmark = pytest.mark.p2_s1

CASES = all_cases()
needs_key = needs_model


@pytest.fixture(scope="module")
def extracted() -> dict[str, Case]:
    """One extraction per case, reused across assertions — these are billed API calls."""
    if not model_available():
        pytest.skip("no key and no cassettes")
    return {c.name: extract_case(c.note_text, note_id=c.name) for c in CASES}


@pytest.mark.live
@needs_key
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_extraction_matches_ground_truth(case, extracted):
    got = extracted[case.name]
    want = case.intake

    assert got.insurance.payer == want["payer"]
    assert got.insurance.plan == want["plan"]
    assert got.primary_diagnosis_code == want["primary_diagnosis_code"]
    assert set(got.service.cpt_codes) == set(want["cpt_codes"]), (
        f"{case.name}: expected {want['cpt_codes']}, got {got.service.cpt_codes}"
    )

    service = got.service.service.lower()
    assert "tms" in service or "transcranial" in service, (
        f"{case.name}: service {got.service.service!r} does not name the requested treatment"
    )


@pytest.mark.live
@needs_key
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_patient_ref_is_the_synthetic_pseudonym(case, extracted):
    """Extraction must carry the note's own pseudonym through, not invent an identifier."""
    assert extracted[case.name].patient_ref == case.case_id


@pytest.mark.live
@needs_key
def test_supplied_insurance_overrides_the_note(extracted):
    """A practice's coverage details beat the note header, so an explicit InsuranceInfo wins."""
    from attest.models import InsuranceInfo

    case = CASES[0]
    override = InsuranceInfo(payer="OverridePayer", plan="OverridePlan", member_id="X-1")
    got = extract_case(case.note_text, override, note_id=case.name)
    assert got.insurance == override


def test_extraction_model_has_no_identifier_fields():
    """Ids and timestamps are generated in code. If they ever appear in the schema the model
    starts inventing them, and an invented case id is indistinguishable from a real one."""
    fields = set(ExtractedCase.model_fields)
    for forbidden in ("case_id", "note_id", "created_at"):
        assert forbidden not in fields


def test_optional_fields_default_to_none():
    """Absent facts must be expressible as null. If these were required the model would be
    forced to guess, and downstream steps treat extracted values as documented fact."""
    for optional in ("group_number", "units_requested", "duration_weeks"):
        assert ExtractedCase.model_fields[optional].default is None


@pytest.mark.live
@needs_key
def test_absent_codes_are_reported_not_invented():
    """The anti-hallucination rule, at the intake boundary.

    A note that names no procedure codes must produce a question for the practice, never a
    plausible guess. This regressed once already: a `min_length=1` constraint added to fix
    flakiness quietly forced the model to fabricate codes for a note that had none.
    """
    from attest.agents.intake import MissingFactError

    note = (
        "> **SYNTHETIC — NOT REAL PATIENT DATA.**\n\n"
        "Patient reference: SYNTH-999. Payer: PacificSource. Plan: Commercial. "
        "Member ID: PS-0000-0000.\n"
        "Diagnosis: Major depressive disorder, recurrent, severe (ICD-10 F33.2).\n"
        "Plan: refer for transcranial magnetic stimulation.\n"
    )

    with pytest.raises(MissingFactError, match="no CPT"):
        extract_case(note, note_id="no-codes")


def test_cpt_codes_are_not_forced_to_be_nonempty():
    """Guards the fix above at the schema level: if the field ever regains a min_length, the
    model is once again forced to invent rather than report absence."""
    from annotated_types import MinLen

    meta = ExtractedCase.model_fields["cpt_codes"].metadata
    assert not any(isinstance(m, MinLen) for m in meta), (
        "cpt_codes has a minimum-length constraint, which forces fabrication when a note "
        "genuinely states no codes"
    )
