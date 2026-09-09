"""Gate for P6-S2 — precedent reuse.

The product claim is that a practice stops rebuilding every appeal from scratch. The risk that
comes with it is precise: precedent is language that will be argued to a payer under a clinician's
name, so anything offered here has to have been approved by one.

`test_unapproved_appeals_are_never_returned` covers the obvious half. The half that matters just as
much is an appeal that *was* approved and then edited — the record is still attached, so a presence
check would pass it, and unapproved language would reach the next case wearing a signature. Only the
content hash catches that, which is why it is the bar rather than the record.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from attest.appeal.precedent import find_precedents, is_precedent, precedent_rebuttals
from attest.gates import content_hash
from attest.models import (
    Appeal,
    ApprovalRecord,
    Case,
    InsuranceInfo,
    Rebuttal,
    ServiceRequest,
)
from attest.store import load_appeal, load_case, save_appeal, save_case

pytestmark = pytest.mark.p6_s2

CRITERION = "ps-04b"


def make_case(case_id: str) -> Case:
    return Case(
        case_id=case_id,
        note_id=f"note-{case_id}",
        patient_ref=f"SYNTH-{case_id}",
        insurance=InsuranceInfo(payer="PacificSource", plan="Commercial", member_id="M-1"),
        service=ServiceRequest(service="TMS", cpt_codes=["90867"]),
        primary_diagnosis_code="F33.2",
        primary_diagnosis_text="Major depressive disorder, recurrent, severe",
        created_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )


def make_appeal(case_id: str, criterion_id: str = CRITERION, argument: str = "Adequate trial documented.") -> Appeal:
    return Appeal(
        appeal_id=f"A-{case_id}",
        case_id=case_id,
        denial_id=f"D-{case_id}",
        rebuttals=[
            Rebuttal(
                criterion_id=criterion_id,
                argument=argument,
                policy_citation="Section III.B",
                supporting_span_ids=["s1"],
            )
        ],
        deadline=date(2026, 12, 1),
    )


def approved(appeal: Appeal, when: datetime | None = None) -> Appeal:
    """Attach a real Gate 2 approval — hash included, exactly as the gate would."""
    signed = appeal.model_copy(
        update={
            "approval": ApprovalRecord(
                approver="Dr. L. Marchetti",
                approved_at=when or datetime(2026, 9, 9, tzinfo=timezone.utc),
                content_hash="placeholder",
            )
        }
    )
    return signed.model_copy(
        update={
            "approval": signed.approval.model_copy(update={"content_hash": content_hash(appeal)})
        }
    )


def seed(tmp_path, appeal: Appeal) -> None:
    save_case(make_case(appeal.case_id), tmp_path)
    save_appeal(appeal, tmp_path)


# ------------------------------------------------------------------ the two DoD tests


def test_seeded_precedent_is_retrieved(tmp_path):
    seed(tmp_path, approved(make_appeal("SYNTH-001")))

    found = find_precedents(CRITERION, tmp_path)

    assert [a.appeal_id for a in found] == ["A-SYNTH-001"]
    assert found[0].rebuttals[0].argument == "Adequate trial documented."


def test_unapproved_appeals_are_never_returned(tmp_path):
    """Only human-approved appeals become precedent."""
    seed(tmp_path, make_appeal("SYNTH-001"))  # drafted, never signed

    assert find_precedents(CRITERION, tmp_path) == []


# --------------------------------------------------------------------- the sharp edge


def test_an_appeal_edited_after_approval_is_not_precedent(tmp_path):
    """The record survives an edit; the hash does not. The hash is the bar.

    Without this, an appeal could be approved, reworded, and its new language offered to the next
    case as though a clinician had signed it.
    """
    signed = approved(make_appeal("SYNTH-001"))
    tampered = signed.model_copy(
        update={
            "rebuttals": [
                signed.rebuttals[0].model_copy(update={"argument": "Language nobody approved."})
            ]
        }
    )
    assert tampered.approval is not None  # the record is still attached

    seed(tmp_path, tampered)

    assert not is_precedent(tampered)
    assert find_precedents(CRITERION, tmp_path) == []


# ------------------------------------------------------------------------- retrieval


def test_precedent_is_scoped_to_the_criterion(tmp_path):
    """An argument for one criterion must never be offered for another."""
    seed(tmp_path, approved(make_appeal("SYNTH-001", criterion_id="ps-02")))

    assert find_precedents(CRITERION, tmp_path) == []
    assert [a.appeal_id for a in find_precedents("ps-02", tmp_path)] == ["A-SYNTH-001"]


def test_most_recently_approved_comes_first(tmp_path):
    """Payer policies churn, so the newest approved language is the most likely to still fit."""
    seed(tmp_path, approved(make_appeal("SYNTH-001"), when=datetime(2026, 3, 1, tzinfo=timezone.utc)))
    seed(tmp_path, approved(make_appeal("SYNTH-002"), when=datetime(2026, 8, 1, tzinfo=timezone.utc)))
    seed(tmp_path, approved(make_appeal("SYNTH-003"), when=datetime(2026, 1, 1, tzinfo=timezone.utc)))

    assert [a.appeal_id for a in find_precedents(CRITERION, tmp_path)] == [
        "A-SYNTH-002",
        "A-SYNTH-001",
        "A-SYNTH-003",
    ]


def test_an_empty_store_has_no_precedent(tmp_path):
    """The first case a practice ever runs. No precedent is an ordinary answer, not an error."""
    assert find_precedents(CRITERION, tmp_path) == []


def test_a_case_with_no_appeal_is_skipped(tmp_path):
    """Most stored cases never get appealed at all."""
    save_case(make_case("SYNTH-001"), tmp_path)

    assert find_precedents(CRITERION, tmp_path) == []


def test_precedent_rebuttals_returns_only_the_matching_argument(tmp_path):
    """An appeal argues several criteria; only the one asked about may come back."""
    signed = approved(
        make_appeal("SYNTH-001").model_copy(
            update={
                "rebuttals": [
                    Rebuttal(
                        criterion_id=CRITERION,
                        argument="The adequate trial is documented.",
                        policy_citation="Section III.B",
                        supporting_span_ids=["s1"],
                    ),
                    Rebuttal(
                        criterion_id="ps-02",
                        argument="The patient is over 18.",
                        policy_citation="Section III.A",
                        supporting_span_ids=["s2"],
                    ),
                ]
            }
        )
    )
    seed(tmp_path, signed)

    rebuttals = precedent_rebuttals(CRITERION, tmp_path)

    assert [r.criterion_id for r in rebuttals] == [CRITERION]
    assert rebuttals[0].argument == "The adequate trial is documented."


# ----------------------------------------------------------------------- store rules


def test_an_appeal_for_an_unstored_case_is_refused(tmp_path):
    """An appeal filed against no case is an orphan — its language has no patient behind it."""
    with pytest.raises(ValueError, match="not in the store"):
        save_appeal(approved(make_appeal("SYNTH-404")), tmp_path)


def test_saving_an_appeal_does_not_discard_the_case(tmp_path):
    """A case and its appeal share one session, so writing one must not overwrite the other."""
    case = make_case("SYNTH-001")
    save_case(case, tmp_path)
    save_appeal(approved(make_appeal("SYNTH-001")), tmp_path)

    assert load_case("SYNTH-001", tmp_path) == case
    assert load_appeal("SYNTH-001", tmp_path) is not None
