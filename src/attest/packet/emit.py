"""Write the submission artifact — but only what a clinician actually approved.

This module is the second, independent half of Gate 1. `attest.gates.SubmissionGate` stops the
*agent* before it can emit; this refuses to write at all unless the packet carries an
`ApprovalRecord` whose hash matches the content in front of it. Either check alone would leave a
way around: the hook only guards the agent path, and the emitter only guards the filesystem.

Validation happens strictly before anything is created, so a refused emit leaves no directory, no
empty file, and nothing to mistake for a partial submission.

P4-S3 completes this module: the PDF rendering and the full artifact-content requirements land
there. What is here is what Gate 1 needs in order to mean something.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from attest.gates import ApprovalRequired, content_hash
from attest.models import EvidenceSpan, Packet

ARTIFACT_NAME = "submission.md"
APPROVAL_NAME = "approval.json"


def _spans(packet: Packet) -> dict[str, EvidenceSpan]:
    return {s.span_id: s for v in packet.coverage.verdicts for s in v.spans}


def _render(packet: Packet) -> str:
    """The submission document. Every quote comes from a verified span, never from prose."""
    spans = _spans(packet)
    approval = packet.approval
    assert approval is not None  # guaranteed by emit_submission_artifact

    lines = [
        f"# Prior authorization request — {packet.case_id}",
        "",
        "> SYNTHETIC DEMONSTRATION DATA. Not a real patient and not for clinical use.",
        "",
        f"- **Policy pack:** {packet.coverage.pack_id}",
        f"- **Approved by:** {approval.approver}",
        f"- **Approved at:** {approval.approved_at.isoformat()}",
        f"- **Content hash:** `{approval.content_hash}`",
        "",
        "## Medical-necessity justification",
        "",
    ]

    for claim in packet.justification.claims:
        lines += [f"- {claim.text}", ""]
        for span_id in claim.supporting_span_ids:
            span = spans.get(span_id)
            if span is not None:
                lines.append(f'  - Evidence `{span_id}` (note chars {span.start}–{span.end}): '
                             f'"{span.quote}"')
        lines.append("")

    lines += ["## Criteria coverage", "", "| Criterion | Verdict | Evidence spans |", "|---|---|---|"]
    for verdict in packet.coverage.verdicts:
        cited = ", ".join(s.span_id for s in verdict.spans) or "—"
        lines.append(f"| {verdict.criterion_id} | {verdict.verdict.value} | {cited} |")
    lines.append("")

    if packet.gaps:
        lines += ["## Outstanding questions for the practice", ""]
        for gap in packet.gaps:
            lines += [f"- **{gap.criterion_id}** — {gap.question}", ""]

    return "\n".join(lines).rstrip() + "\n"


def emit_submission_artifact(packet: Packet, out_dir: Path | str = Path("out")) -> Path:
    """Write the approved submission artifact, and the approval that authorised it.

    Raises `ApprovalRequired` — writing nothing at all — if the packet carries no approval, or if
    the approved content hash does not match the packet being emitted. The second case is the one
    that matters: it catches a packet edited after sign-off, which is exactly the failure an
    approval record exists to make impossible.
    """
    approval = packet.approval
    if approval is None:
        raise ApprovalRequired(
            f"case {packet.case_id}: no ApprovalRecord on the packet. Gate 1 requires a named "
            "clinician to approve a submission before it can be written."
        )

    actual = content_hash(packet)
    if approval.content_hash != actual:
        raise ApprovalRequired(
            f"case {packet.case_id}: the packet has changed since it was approved by "
            f"{approval.approver!r}. Approved {approval.content_hash[:12]}…, "
            f"emitting {actual[:12]}…. Re-approve the current content."
        )

    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)

    artifact = directory / ARTIFACT_NAME
    artifact.write_text(_render(packet), encoding="utf-8", newline="\n")

    (directory / APPROVAL_NAME).write_text(
        json.dumps(
            approval.model_dump(mode="json") | {"emitted_at": datetime.now(timezone.utc).isoformat()},
            indent=2,
        ),
        encoding="utf-8",
        newline="\n",
    )

    return artifact
