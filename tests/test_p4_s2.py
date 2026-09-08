"""Gate for P4-S2 — Gate 1, human approval before submission.

`Attest-PRODUCT.md` §6 makes this non-negotiable: the agent assembles and argues, humans decide
and submit. So the guarantee has to be structural in two independent places.

1. **The agent path.** A `BeforeToolCallEvent` hook interrupts before `emit_submission_artifact`,
   which stops the event loop and hands the packet to a human. This is Strands' first-class
   human-in-the-loop primitive, so the gate holds even when the agent runs headlessly.
2. **The emitter itself.** `emit_submission_artifact` refuses to write without an `ApprovalRecord`
   whose content hash matches what is actually being emitted. A gate that only guards the agent
   path is a gate with a door beside it.

The hash is what makes the approval mean anything. Without it the record proves an approval
happened at *some* point; with it, it proves the clinician approved *this* content.
"""

import json
from datetime import datetime, timezone

import pytest
from strands.hooks import BeforeToolCallEvent
from strands.interrupt import Interrupt, InterruptException, _InterruptState

from attest.gates import (
    APPROVAL_TOOL,
    ApprovalRequired,
    SubmissionGate,
    content_hash,
)
from attest.models import (
    ApprovalRecord,
    Claim,
    CriteriaCoverage,
    CriterionVerdict,
    EvidenceSpan,
    Justification,
    Packet,
    Verdict,
)
from attest.packet.emit import emit_submission_artifact

pytestmark = pytest.mark.p4_s2


def packet(case_id: str = "SYNTH-001") -> Packet:
    span = EvidenceSpan(
        span_id="ps-01-0",
        note_id="note",
        quote="PHQ-9 score is 21",
        verified=True,
        start=0,
        end=17,
    )
    return Packet(
        case_id=case_id,
        coverage=CriteriaCoverage(
            case_id=case_id,
            pack_id="pacificsource-commercial-tms",
            verdicts=[
                CriterionVerdict(
                    criterion_id="ps-01",
                    verdict=Verdict.MET,
                    spans=[span],
                    reasoning="documented",
                )
            ],
        ),
        justification=Justification(
            claims=[Claim(text="The record documents this.", supporting_span_ids=["ps-01-0"])]
        ),
    )


def approved(p: Packet, approver: str = "Dr. R. Okonkwo") -> Packet:
    return p.model_copy(
        update={
            "approval": ApprovalRecord(
                approver=approver,
                approved_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
                content_hash=content_hash(p),
            )
        }
    )


# --------------------------------------------------------------------------- the emitter


def test_artifact_blocked_without_approval(tmp_path):
    """No approval, no file. Not a warning, not an empty file — nothing."""
    with pytest.raises(ApprovalRequired):
        emit_submission_artifact(packet(), out_dir=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_artifact_written_after_approval(tmp_path):
    path = emit_submission_artifact(approved(packet()), out_dir=tmp_path)

    assert path.is_file()
    assert path.read_text(encoding="utf-8").strip()


def test_approval_record_persisted(tmp_path):
    """An approval nobody can produce later did not happen, as far as an auditor is concerned."""
    emit_submission_artifact(approved(packet()), out_dir=tmp_path)

    record = json.loads((tmp_path / "approval.json").read_text(encoding="utf-8"))

    assert record["approver"] == "Dr. R. Okonkwo"
    assert datetime.fromisoformat(record["approved_at"])  # ISO 8601, parseable
    assert record["content_hash"]


def test_content_hash_matches_emitted_artifact(tmp_path):
    """Proves what was approved is what was emitted."""
    p = approved(packet())
    emit_submission_artifact(p, out_dir=tmp_path)

    record = json.loads((tmp_path / "approval.json").read_text(encoding="utf-8"))

    assert record["content_hash"] == content_hash(p)


# --------------------------------------------------------------------------- the hash itself


def test_tampering_after_approval_is_refused(tmp_path):
    """The whole point of the hash: approve one packet, emit another, get caught."""
    p = approved(packet())
    tampered = p.model_copy(
        update={
            "justification": Justification(
                claims=[Claim(text="Something nobody approved.", supporting_span_ids=["ps-01-0"])]
            )
        }
    )

    with pytest.raises(ApprovalRequired):
        emit_submission_artifact(tampered, out_dir=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_hash_excludes_the_approval_itself():
    """Otherwise attaching the approval would invalidate the hash it contains."""
    p = packet()

    assert content_hash(approved(p)) == content_hash(p)


def test_hash_changes_when_content_changes():
    other = packet().model_copy(update={"case_id": "SYNTH-999"})

    assert content_hash(packet()) != content_hash(other)


# --------------------------------------------------------------------------- the agent-path hook


class _StubAgent:
    """Enough of an Agent for `event.interrupt()` — it touches only `_interrupt_state`."""

    def __init__(self) -> None:
        self._interrupt_state = _InterruptState()


def event_for(tool_name: str, agent: _StubAgent) -> BeforeToolCallEvent:
    return BeforeToolCallEvent(
        agent=agent,  # type: ignore[arg-type]
        selected_tool=None,
        tool_use={"toolUseId": "tu-1", "name": tool_name, "input": {}},
        invocation_state={},
    )


def test_gate_interrupts_before_the_emit_tool():
    """The agent loop stops and the packet goes to a human. The tool never runs."""
    event = event_for(APPROVAL_TOOL, _StubAgent())

    with pytest.raises(InterruptException):
        SubmissionGate().require_approval(event)


def test_gate_ignores_unrelated_tools():
    """Gate 1 guards submission only — it must not stop the agent doing its ordinary work."""
    event = event_for("check_prior_authorization", _StubAgent())

    SubmissionGate().require_approval(event)  # must not raise

    assert event.cancel_tool is False


def test_gate_lets_the_tool_run_once_a_human_approves():
    agent = _StubAgent()
    event = event_for(APPROVAL_TOOL, agent)
    interrupt_id = event._interrupt_id("gate1_submission")
    agent._interrupt_state.interrupts[interrupt_id] = Interrupt(
        interrupt_id, "gate1_submission", None, "Dr. R. Okonkwo"
    )

    SubmissionGate().require_approval(event)

    assert event.cancel_tool is False


def test_gate_cancels_the_tool_when_approval_is_refused():
    """A refusal must stop the emit, not fall through to it."""
    agent = _StubAgent()
    event = event_for(APPROVAL_TOOL, agent)
    interrupt_id = event._interrupt_id("gate1_submission")
    agent._interrupt_state.interrupts[interrupt_id] = Interrupt(
        interrupt_id, "gate1_submission", None, ""
    )

    SubmissionGate().require_approval(event)

    assert event.cancel_tool
    assert "approv" in str(event.cancel_tool).lower()


def test_gate_attaches_the_approval_record_to_the_tool_input():
    """The approval has to reach the emitter, or the agent path approves and then fails anyway.

    The hook is the only place that knows who approved and when, so it writes the record into the
    tool's input, hashed against the packet the human was actually shown.
    """
    agent = _StubAgent()
    p = packet()
    event = event_for(APPROVAL_TOOL, agent)
    event.tool_use["input"]["packet"] = p.model_dump(mode="json")

    interrupt_id = event._interrupt_id("gate1_submission")
    agent._interrupt_state.interrupts[interrupt_id] = Interrupt(
        interrupt_id, "gate1_submission", None, "Dr. R. Okonkwo"
    )

    SubmissionGate().require_approval(event)

    attached = event.tool_use["input"]["packet"]["approval"]
    assert attached["approver"] == "Dr. R. Okonkwo"
    assert attached["content_hash"] == content_hash(p)


def test_gate_registers_itself_on_before_tool_call():
    """A hook that is never registered is a comment."""
    registered: list = []

    class Registry:
        def add_callback(self, event_type, callback):
            registered.append(event_type)

    SubmissionGate().register_hooks(Registry())

    assert BeforeToolCallEvent in registered
