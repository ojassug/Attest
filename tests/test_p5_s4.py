"""Gate for P5-S4 — the appeal artifact and its deadline.

Two things carry real consequence here.

**The deadline.** It is the denial date plus the pack's `appeal_window_days`, read from the pack
rather than assumed — the two shipped packs disagree (60 days and 180), so a constant would be
wrong half the time and silently so. A missed appeal window is an appeal that never happens.

**Where the window came from.** Neither payer's policy states one, and both packs say so in
`appeal_window_source`. `PolicyPack` puts the reason plainly: "an invented deadline on an appeal is
worse than no deadline." So the artifact discloses the source verbatim. A practice reading this
must be able to tell a policy-stated deadline from our placeholder without going back to the pack.
"""

from datetime import date, datetime, timezone

import pytest

from attest.appeal.assemble import appeal_deadline, build_appeal
from attest.appeal.emit import emit_appeal_artifact
from attest.appeal.parse import parse_denial
from attest.corpus import load_case
from attest.criteria.match import match_all
from attest.gates import content_hash
from attest.models import ApprovalRecord, ContestedCriterion, Denial, Rebuttal
from attest.verifier import enforce_verification
from conftest import needs_model

pytestmark = pytest.mark.p5_s4

CASE = load_case("denial")
PACK = CASE.pack
GROUND_TRUTH = CASE.raw["denial"]


def rebuttal(criterion_id: str, span_id: str = "s1") -> Rebuttal:
    return Rebuttal(
        criterion_id=criterion_id,
        argument=f"The record documents {criterion_id}.",
        policy_citation=next(c.source_section for c in PACK.criteria if c.id == criterion_id),
        supporting_span_ids=[span_id],
    )


def denial(*criterion_ids: str, unmapped: tuple[str, ...] = ()) -> Denial:
    return Denial(
        denial_id="D-1",
        case_id=CASE.case_id,
        denial_date=date(2026, 8, 3),
        contested=[ContestedCriterion(criterion_id=i, payer_reason="not established") for i in criterion_ids],
        unmapped_reasons=list(unmapped),
    )


def approve(a):
    return a.model_copy(
        update={
            "approval": ApprovalRecord(
                approver="Dr. L. Marchetti",
                approved_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
                content_hash=content_hash(a),
            )
        }
    )


# --------------------------------------------------------------------------- the DoD


def test_appeal_deadline_computed():
    """Denial date plus the pack's appeal_window_days."""
    assert appeal_deadline(date(2026, 8, 3), PACK) == date(2026, 10, 2)  # 60 days


def test_appeal_contains_rebuttal_per_contested_criterion():
    appeal = build_appeal(denial("hho-03", "hho-04"), [rebuttal("hho-03"), rebuttal("hho-04")], PACK)

    assert [r.criterion_id for r in appeal.rebuttals] == ["hho-03", "hho-04"]


# --------------------------------------------------------------------------- the deadline


def test_deadline_reads_the_window_from_the_pack_not_a_constant():
    """The two shipped packs disagree - 60 days and 180. A constant is wrong half the time."""
    other = load_case("gap").pack

    assert PACK.appeal_window_days != other.appeal_window_days
    assert appeal_deadline(date(2026, 8, 3), PACK) != appeal_deadline(date(2026, 8, 3), other)


def test_deadline_is_carried_onto_the_appeal():
    appeal = build_appeal(denial("hho-03"), [rebuttal("hho-03")], PACK)

    assert appeal.deadline == appeal_deadline(date(2026, 8, 3), PACK)


def test_every_contested_criterion_must_have_a_rebuttal():
    """An appeal that answers two of three objections is denied on the third."""
    with pytest.raises(ValueError):
        build_appeal(denial("hho-03", "hho-04"), [rebuttal("hho-03")], PACK)


# --------------------------------------------------------------------------- the artifact


def test_artifact_discloses_the_appeal_window_source(tmp_path):
    """Neither payer states a window. A reader must see that without opening the pack.

    `PolicyPack.appeal_window_source` exists because an invented deadline on an appeal is worse
    than no deadline, and that warning is worthless if it never reaches the document.
    """
    appeal = approve(build_appeal(denial("hho-03"), [rebuttal("hho-03")], PACK))
    text = emit_appeal_artifact(appeal, out_dir=tmp_path).read_text(encoding="utf-8")

    assert PACK.appeal_window_source in text
    assert "NOT STATED" in text


def test_artifact_contains_every_policy_citation(tmp_path):
    appeal = approve(build_appeal(denial("hho-03", "hho-04"), [rebuttal("hho-03"), rebuttal("hho-04")], PACK))
    text = emit_appeal_artifact(appeal, out_dir=tmp_path).read_text(encoding="utf-8")

    for r in appeal.rebuttals:
        assert r.policy_citation in text


def test_artifact_cites_every_supporting_span(tmp_path):
    appeal = approve(build_appeal(denial("hho-03"), [rebuttal("hho-03", "hho-03-0")], PACK))
    text = emit_appeal_artifact(appeal, out_dir=tmp_path).read_text(encoding="utf-8")

    assert "hho-03-0" in text


def test_unmapped_reasons_reach_the_artifact(tmp_path):
    """The reason that maps to no criterion is the one most likely to sink a resubmission.

    P5-S1 surfaces it on `Denial.unmapped_reasons` precisely so it is never silently dropped. If it
    stops there it is dropped anyway - just later, and where nobody is looking.
    """
    site_of_service = "The member has not satisfied the plan's site-of-service requirement."
    appeal = approve(
        build_appeal(denial("hho-03", unmapped=(site_of_service,)), [rebuttal("hho-03")], PACK)
    )

    text = emit_appeal_artifact(appeal, out_dir=tmp_path).read_text(encoding="utf-8")

    assert site_of_service in text


def test_artifact_is_utf8_with_lf_endings(tmp_path):
    appeal = approve(build_appeal(denial("hho-03"), [rebuttal("hho-03")], PACK))
    raw = emit_appeal_artifact(appeal, out_dir=tmp_path).read_bytes()

    assert raw.decode("utf-8")
    assert b"\r\n" not in raw


# --------------------------------------------------------------------------- real data


@needs_model
def test_the_real_denial_produces_a_complete_appeal(tmp_path):
    from attest.appeal.draft import draft_rebuttals

    coverage = enforce_verification(
        match_all(PACK, CASE.note_text, case_id=CASE.case_id, note_id="denial"), CASE.note_text
    ).coverage
    parsed = parse_denial(CASE.denial_text, PACK, case_id=CASE.case_id)
    rebuttals = draft_rebuttals(parsed.contested, coverage, PACK)

    appeal = build_appeal(parsed, rebuttals, PACK)

    assert appeal.deadline == date(2026, 10, 2)
    assert {r.criterion_id for r in appeal.rebuttals} == set(GROUND_TRUTH["expected_contested"])

    text = emit_appeal_artifact(approve(appeal), out_dir=tmp_path).read_text(encoding="utf-8")
    for reason in parsed.unmapped_reasons:
        assert reason in text
