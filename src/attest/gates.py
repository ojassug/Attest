"""Gate 1 — a named human approves the submission, or nothing is submitted.

`Attest-PRODUCT.md` §6: the agent assembles and argues; humans decide and submit. That is a
product requirement, not UI logic, so it is enforced in two independent places:

* **The agent path** — `SubmissionGate` interrupts on `BeforeToolCallEvent` before the emit tool
  runs. Strands stops the event loop and returns the interrupt, so the gate holds even when the
  agent is driven headlessly, with no UI in the loop to forget to ask.
* **The emitter** — `emit_submission_artifact` independently refuses to write without an
  `ApprovalRecord` whose hash matches. A gate that only guards the agent path is a gate with a
  door beside it.

**The hash is what makes the approval mean anything.** Without it an `ApprovalRecord` proves an
approval happened at *some* point. With it, it proves a clinician approved *this* content — so
editing the packet after sign-off invalidates the approval instead of riding on it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from strands.hooks import BeforeToolCallEvent, HookProvider

from attest.models import ApprovalRecord, Packet

APPROVAL_TOOL = "emit_submission_artifact"
"""The tool this gate stands in front of."""

INTERRUPT_NAME = "gate1_submission"


class ApprovalRequired(RuntimeError):
    """Raised when a submission artifact would be written without a matching human approval."""


def content_hash(packet: Packet) -> str:
    """A stable SHA-256 over exactly the content a human is being asked to approve.

    ``approval`` is excluded deliberately. It is the *evidence* of approval rather than part of
    what was approved, and including it would be circular — attaching the record would change the
    hash stored inside that record.

    The dump is canonicalised (sorted keys, no incidental whitespace) so that the same packet
    always hashes the same way, whatever order the fields happen to be built in.
    """
    content = packet.model_dump(mode="json", exclude={"approval"})
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SubmissionGate(HookProvider):
    """Stops the agent before it can emit a submission artifact, and asks a human."""

    def register_hooks(self, registry: Any, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.require_approval)

    def require_approval(self, event: BeforeToolCallEvent) -> None:
        """Interrupt before the emit tool; on resume, record who approved what.

        The first call raises ``InterruptException`` — Strands stops the loop and returns the
        interrupt to the caller, so the tool never executes. When the caller resumes with a
        response, this runs again and the same ``interrupt()`` call returns that response.

        An empty or blank approver is a refusal. It cancels the tool rather than falling through,
        because "nobody said yes" must never be treated as "nobody said no".
        """
        if event.tool_use["name"] != APPROVAL_TOOL:
            return

        packet = self._packet_from(event)

        reason: dict[str, Any] = {
            "gate": "Gate 1 — clinician approval before submission",
            "asks": "Reply with the approving clinician's name, or an empty string to refuse.",
        }
        if packet is not None:
            reason |= {
                "case_id": packet.case_id,
                "claims": len(packet.justification.claims),
                "gaps": len(packet.gaps),
                "content_hash": content_hash(packet),
            }

        approver = event.interrupt(INTERRUPT_NAME, reason=reason)

        if not isinstance(approver, str) or not approver.strip():
            event.cancel_tool = "Gate 1: submission was not approved by a named clinician."
            return

        if packet is not None:
            record = ApprovalRecord(
                approver=approver.strip(),
                approved_at=datetime.now(timezone.utc),
                content_hash=content_hash(packet),
            )
            event.tool_use["input"]["packet"]["approval"] = record.model_dump(mode="json")

    @staticmethod
    def _packet_from(event: BeforeToolCallEvent) -> Packet | None:
        """The packet the tool is about to emit, if the input carries one.

        Returns None rather than raising: a malformed input is the tool's problem to report, and
        the gate must still interrupt. Failing open here would let a bad payload skip the gate.
        """
        raw = event.tool_use.get("input", {}).get("packet")
        if not isinstance(raw, dict):
            return None
        try:
            return Packet.model_validate(raw)
        except Exception:
            return None
