"""Gate for P5-S3 — Gate 2, human approval before an appeal is sent.

The same two-place enforcement as Gate 1, for the same reason: `Attest-PRODUCT.md` §6 makes human
approval non-negotiable, and non-negotiable must not depend on which entry point was used.

* `AppealGate` interrupts on `BeforeToolCallEvent` before `emit_appeal_artifact`, so a headless
  agent stops and hands the appeal to a clinician.
* `emit_appeal_artifact` independently refuses to write without an `ApprovalRecord` whose hash
  matches the appeal in front of it.

The property this file adds beyond Gate 1 is **separation**: approving a submission packet must
not authorise an appeal, and neither gate may fire on the other's tool. Two gates that can be
satisfied by each other's approvals are one gate wearing a disguise.
"""

import json
from datetime import date, datetime, timezone

import pytest
from strands.hooks import BeforeToolCallEvent
from strands.interrupt import Interrupt, InterruptException, _InterruptState

from attest.appeal.emit import emit_appeal_artifact
from attest.gates import (
    APPEAL_TOOL,
    APPROVAL_TOOL,
    AppealGate,
    ApprovalRequired,
    SubmissionGate,
    content_hash,
)
from attest.models import Appeal, ApprovalRecord, Rebuttal

pytestmark = pytest.mark.p5_s3


def appeal(case_id: str = "SYNTH-003") -> Appeal:
    return Appeal(
        appeal_id="AP-001",
        case_id=case_id,
        denial_id=f"{case_id}-denial-2026-08-03",
        rebuttals=[
            Rebuttal(
                criterion_id="hho-03",
                argument="The record documents four psychopharmacologic trials.",
                policy_citation="POLICY POSITION, medical necessity list, bullet 3",
                supporting_span_ids=["hho-03-0"],
            )
        ],
        deadline=date(2026, 10, 2),
    )


def approved(a: Appeal, approver: str = "Dr. L. Marchetti") -> Appeal:
    return a.model_copy(
        update={
            "approval": ApprovalRecord(
                approver=approver,
                approved_at=datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc),
                content_hash=content_hash(a),
            )
        }
    )


# --------------------------------------------------------------------------- the DoD


def test_appeal_blocked_without_approval(tmp_path):
    """An unapproved appeal is not a draft on disk. It is nothing on disk."""
    with pytest.raises(ApprovalRequired):
        emit_appeal_artifact(appeal(), out_dir=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_appeal_written_after_approval(tmp_path):
    path = emit_appeal_artifact(approved(appeal()), out_dir=tmp_path)

    assert path.is_file()
    assert path.read_text(encoding="utf-8").strip()


def test_appeal_approval_record_persisted(tmp_path):
    emit_appeal_artifact(approved(appeal()), out_dir=tmp_path)

    record = json.loads((tmp_path / "approval.json").read_text(encoding="utf-8"))

    assert record["approver"] == "Dr. L. Marchetti"
    assert datetime.fromisoformat(record["approved_at"])
    assert record["content_hash"] == content_hash(appeal())


# --------------------------------------------------------------------------- the hash


def test_tampering_after_approval_is_refused(tmp_path):
    """Approve one appeal, send another, get caught."""
    tampered = approved(appeal()).model_copy(
        update={
            "rebuttals": [
                Rebuttal(
                    criterion_id="hho-03",
                    argument="An argument nobody approved.",
                    policy_citation="POLICY POSITION, medical necessity list, bullet 3",
                    supporting_span_ids=["hho-03-0"],
                )
            ]
        }
    )

    with pytest.raises(ApprovalRequired):
        emit_appeal_artifact(tampered, out_dir=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_hash_excludes_the_approval_itself():
    a = appeal()

    assert content_hash(approved(a)) == content_hash(a)


# --------------------------------------------------------------------------- separation of gates


def test_an_approval_for_a_different_case_is_refused(tmp_path):
    """A clinician approved one patient's appeal. It does not authorise another's."""
    other = approved(appeal(case_id="SYNTH-999"))
    swapped = appeal().model_copy(update={"approval": other.approval})

    with pytest.raises(ApprovalRequired):
        emit_appeal_artifact(swapped, out_dir=tmp_path)


class _StubAgent:
    def __init__(self) -> None:
        self._interrupt_state = _InterruptState()


def event_for(tool_name: str, agent: _StubAgent) -> BeforeToolCallEvent:
    return BeforeToolCallEvent(
        agent=agent,  # type: ignore[arg-type]
        selected_tool=None,
        tool_use={"toolUseId": "tu-1", "name": tool_name, "input": {}},
        invocation_state={},
    )


def test_gate2_interrupts_before_the_appeal_tool():
    with pytest.raises(InterruptException):
        AppealGate().require_approval(event_for(APPEAL_TOOL, _StubAgent()))


def test_gate2_does_not_fire_on_the_submission_tool():
    """Each gate guards its own tool. Otherwise one approval silently satisfies both."""
    event = event_for(APPROVAL_TOOL, _StubAgent())

    AppealGate().require_approval(event)

    assert event.cancel_tool is False


def test_gate1_does_not_fire_on_the_appeal_tool():
    event = event_for(APPEAL_TOOL, _StubAgent())

    SubmissionGate().require_approval(event)

    assert event.cancel_tool is False


def test_gate2_ignores_unrelated_tools():
    event = event_for("check_prior_authorization", _StubAgent())

    AppealGate().require_approval(event)

    assert event.cancel_tool is False


# --------------------------------------------------------------------------- resume behaviour


def _armed(tool: str, response) -> tuple[_StubAgent, BeforeToolCallEvent]:
    agent = _StubAgent()
    event = event_for(tool, agent)
    interrupt_id = event._interrupt_id("gate2_appeal")
    agent._interrupt_state.interrupts[interrupt_id] = Interrupt(
        interrupt_id, "gate2_appeal", None, response
    )
    return agent, event


def test_gate2_lets_the_tool_run_once_a_human_approves():
    _, event = _armed(APPEAL_TOOL, "Dr. L. Marchetti")

    AppealGate().require_approval(event)

    assert event.cancel_tool is False


def test_gate2_cancels_the_tool_when_approval_is_refused():
    _, event = _armed(APPEAL_TOOL, "")

    AppealGate().require_approval(event)

    assert event.cancel_tool
    assert "approv" in str(event.cancel_tool).lower()


def test_gate2_attaches_the_approval_record_to_the_tool_input():
    a = appeal()
    _, event = _armed(APPEAL_TOOL, "Dr. L. Marchetti")
    event.tool_use["input"]["appeal"] = a.model_dump(mode="json")

    AppealGate().require_approval(event)

    attached = event.tool_use["input"]["appeal"]["approval"]
    assert attached["approver"] == "Dr. L. Marchetti"
    assert attached["content_hash"] == content_hash(a)


def test_gate2_registers_itself_on_before_tool_call():
    registered: list = []

    class Registry:
        def add_callback(self, event_type, callback):
            registered.append(event_type)

    AppealGate().register_hooks(Registry())

    assert BeforeToolCallEvent in registered
