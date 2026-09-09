"""The two human-approval gates — a named clinician approves, or nothing leaves the building.

`Attest-PRODUCT.md` §6: the agent assembles and argues; humans decide and submit. That is a
product requirement, not UI logic, so each gate is enforced in two independent places:

* **The agent path** — a `HookProvider` interrupts on `BeforeToolCallEvent` before the emitting
  tool runs. Strands stops the event loop and returns the interrupt, so the gate holds even when
  the agent is driven headlessly, with no UI in the loop to remember to ask.
* **The emitter** — `emit_submission_artifact` and `emit_appeal_artifact` independently refuse to
  write without an `ApprovalRecord` whose hash matches. A gate that only guards the agent path is
  a gate with a door beside it.

**The hash is what makes an approval mean anything.** Without it an `ApprovalRecord` proves an
approval happened at *some* point. With it, it proves a clinician approved *this* content — so
editing a document after sign-off invalidates the approval rather than riding on it.

**The two gates are separate on purpose.** Gate 1 approves a submission packet; Gate 2 approves an
appeal. Neither fires on the other's tool, and because the hash covers the document, an approval
for one can never satisfy the other. Two gates that accept each other's approvals are one gate
wearing a disguise.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, ClassVar

from strands.hooks import BeforeToolCallEvent, HookProvider

from attest.models import Appeal, ApprovalRecord, Packet

APPROVAL_TOOL = "emit_submission_artifact"
"""The tool Gate 1 stands in front of."""

APPEAL_TOOL = "emit_appeal_artifact"
"""The tool Gate 2 stands in front of."""

INTERRUPT_NAME = "gate1_submission"
APPEAL_INTERRUPT_NAME = "gate2_appeal"

Approvable = Packet | Appeal
"""A document a clinician signs off: it carries an ``approval`` field and nothing else in common."""


class ApprovalRequired(RuntimeError):
    """Raised when an artifact would be written without a matching human approval."""


def content_hash(document: Approvable) -> str:
    """A stable SHA-256 over exactly the content a human is being asked to approve.

    ``approval`` is excluded deliberately. It is the *evidence* of approval rather than part of
    what was approved, and including it would be circular — attaching the record would change the
    hash stored inside that record.

    The dump is canonicalised (sorted keys, no incidental whitespace) so that the same document
    always hashes the same way, whatever order the fields happen to be built in.
    """
    content = document.model_dump(mode="json", exclude={"approval"})
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _ApprovalGate(HookProvider):
    """Shared machinery for both gates. Subclasses supply only what differs."""

    TOOL: ClassVar[str]
    INTERRUPT: ClassVar[str]
    PAYLOAD_KEY: ClassVar[str]
    DOCUMENT: ClassVar[type[Approvable]]
    LABEL: ClassVar[str]
    REFUSAL: ClassVar[str]

    def register_hooks(self, registry: Any, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self.require_approval)

    def require_approval(self, event: BeforeToolCallEvent) -> None:
        """Interrupt before the emitting tool; on resume, record who approved what.

        The first call raises ``InterruptException`` — Strands stops the loop and returns the
        interrupt to the caller, so the tool never executes. When the caller resumes with a
        response, this runs again and the same ``interrupt()`` call returns that response.

        An empty or blank approver is a refusal. It cancels the tool rather than falling through,
        because "nobody said yes" must never be treated as "nobody said no" — the same reasoning
        that gives ``PARequirement`` an ``UNKNOWN`` member.
        """
        if event.tool_use["name"] != self.TOOL:
            return

        document = self._document_from(event)

        reason: dict[str, Any] = {
            "gate": self.LABEL,
            "asks": "Reply with the approving clinician's name, or an empty string to refuse.",
        }
        if document is not None:
            reason |= self._summary(document) | {"content_hash": content_hash(document)}

        approver = event.interrupt(self.INTERRUPT, reason=reason)

        if not isinstance(approver, str) or not approver.strip():
            event.cancel_tool = self.REFUSAL
            return

        if document is not None:
            record = ApprovalRecord(
                approver=approver.strip(),
                approved_at=datetime.now(timezone.utc),
                content_hash=content_hash(document),
            )
            event.tool_use["input"][self.PAYLOAD_KEY]["approval"] = record.model_dump(mode="json")

    def _summary(self, document: Approvable) -> dict[str, Any]:
        """What the human is shown alongside the hash. Overridden per document type."""
        return {"case_id": document.case_id}

    def _document_from(self, event: BeforeToolCallEvent) -> Approvable | None:
        """The document the tool is about to emit, if the input carries one.

        Returns None rather than raising: a malformed input is the tool's problem to report, and
        the gate must still interrupt. Failing open here would let a bad payload skip the gate.
        """
        raw = event.tool_use.get("input", {}).get(self.PAYLOAD_KEY)
        if not isinstance(raw, dict):
            return None
        try:
            return self.DOCUMENT.model_validate(raw)
        except Exception:
            return None


class SubmissionGate(_ApprovalGate):
    """Gate 1 — stops the agent before it can emit a submission artifact."""

    TOOL = APPROVAL_TOOL
    INTERRUPT = INTERRUPT_NAME
    PAYLOAD_KEY = "packet"
    DOCUMENT = Packet
    LABEL = "Gate 1 — clinician approval before submission"
    REFUSAL = "Gate 1: submission was not approved by a named clinician."

    def _summary(self, document: Approvable) -> dict[str, Any]:
        assert isinstance(document, Packet)
        return {
            "case_id": document.case_id,
            "claims": len(document.justification.claims),
            "gaps": len(document.gaps),
        }


class AppealGate(_ApprovalGate):
    """Gate 2 — stops the agent before it can emit an appeal."""

    TOOL = APPEAL_TOOL
    INTERRUPT = APPEAL_INTERRUPT_NAME
    PAYLOAD_KEY = "appeal"
    DOCUMENT = Appeal
    LABEL = "Gate 2 — clinician approval before appeal"
    REFUSAL = "Gate 2: appeal was not approved by a named clinician."

    def _summary(self, document: Approvable) -> dict[str, Any]:
        assert isinstance(document, Appeal)
        return {
            "case_id": document.case_id,
            "denial_id": document.denial_id,
            "rebuttals": len(document.rebuttals),
            "deadline": document.deadline.isoformat(),
        }
