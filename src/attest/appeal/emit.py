"""Write the appeal — but only what a clinician actually approved.

The second half of Gate 2, mirroring `attest.packet.emit` for submissions. `attest.gates.AppealGate`
stops the *agent* before it can emit; this refuses to write at all unless the appeal carries an
`ApprovalRecord` whose hash matches the document in front of it. Either check alone leaves a way
around: the hook guards only the agent path, the emitter only the filesystem.

Validation happens strictly before anything is created, so a refused emit leaves no directory, no
empty file, and nothing that could be mistaken for a sent appeal.

P5-S4 completes this module: the deadline computation and the artifact-content requirements land
there. What is here is what Gate 2 needs in order to mean something.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from attest.gates import ApprovalRequired, content_hash
from attest.models import Appeal

ARTIFACT_NAME = "appeal.md"
APPROVAL_NAME = "approval.json"


def _render(appeal: Appeal) -> str:
    """The appeal letter. Every argument carries the policy section it answers."""
    approval = appeal.approval
    assert approval is not None  # guaranteed by emit_appeal_artifact

    lines = [
        f"# Appeal of adverse benefit determination - {appeal.case_id}",
        "",
        "> SYNTHETIC DEMONSTRATION DATA. Not a real patient and not for clinical use.",
        "",
        f"- **Appeal reference:** {appeal.appeal_id}",
        f"- **Denial reference:** {appeal.denial_id}",
        f"- **Appeal deadline:** {appeal.deadline.isoformat()}",
        f"- **Approved by:** {approval.approver}",
        f"- **Approved at:** {approval.approved_at.isoformat()}",
        f"- **Content hash (SHA-256):** {approval.content_hash}",
        "",
    ]

    # The deadline's provenance sits with the deadline, not in a footnote. Neither payer's policy
    # states an appeal window, and an invented deadline is worse than no deadline - so a reader
    # has to be able to tell a policy-stated date from our placeholder without opening the pack.
    if appeal.deadline_source:
        lines += [f"> **Appeal window source:** {appeal.deadline_source}", ""]

    lines += ["## Grounds for appeal", ""]

    for rebuttal in appeal.rebuttals:
        lines += [
            f"### {rebuttal.criterion_id} - {rebuttal.policy_citation}",
            "",
            rebuttal.argument,
            "",
            f"*Supporting evidence: {', '.join(rebuttal.supporting_span_ids)}*",
            "",
        ]

    # Objections that map to no clinical criterion are not rebutted - nothing in the record speaks
    # to them - but the practice has to be told they were raised, or it will fix the clinical
    # objections and be denied again for the same administrative one.
    if appeal.unmapped_reasons:
        lines += [
            "## Payer objections outside the clinical criteria",
            "",
            "These were raised in the determination but map to no criterion in the policy, so they "
            "are not answered above. They need a separate response from the practice.",
            "",
        ]
        lines += [f"- {reason}" for reason in appeal.unmapped_reasons] + [""]

    return "\n".join(lines).rstrip() + "\n"


def emit_appeal_artifact(appeal: Appeal, out_dir: Path | str = Path("out")) -> Path:
    """Write the approved appeal, and the approval that authorised it.

    Raises `ApprovalRequired` — writing nothing at all — if the appeal carries no approval, or if
    the approved hash does not match the appeal being emitted. The second case catches an appeal
    edited after sign-off, and also an approval borrowed from a different document: the hash covers
    the case id, so one patient's approval can never authorise another's appeal.
    """
    approval = appeal.approval
    if approval is None:
        raise ApprovalRequired(
            f"case {appeal.case_id}: no ApprovalRecord on the appeal. Gate 2 requires a named "
            "clinician to approve an appeal before it can be written."
        )

    actual = content_hash(appeal)
    if approval.content_hash != actual:
        raise ApprovalRequired(
            f"case {appeal.case_id}: the appeal has changed since it was approved by "
            f"{approval.approver!r}, or the approval belongs to a different document. "
            f"Approved {approval.content_hash[:12]}..., emitting {actual[:12]}.... "
            "Re-approve the current content."
        )

    markdown = _render(appeal)

    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)

    artifact = directory / ARTIFACT_NAME
    artifact.write_text(markdown, encoding="utf-8", newline="\n")

    (directory / APPROVAL_NAME).write_text(
        json.dumps(
            approval.model_dump(mode="json")
            | {"emitted_at": datetime.now(timezone.utc).isoformat()},
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )

    return artifact
