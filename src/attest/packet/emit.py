"""Write the submission artifact — but only what a clinician actually approved.

This module is the second, independent half of Gate 1. `attest.gates.SubmissionGate` stops the
*agent* before it can emit; this refuses to write at all unless the packet carries an
`ApprovalRecord` whose hash matches the content in front of it. Either check alone would leave a
way around: the hook only guards the agent path, and the emitter only guards the filesystem.

**Markdown and PDF render from one block list**, not from two hand-written templates. A payer
reads the PDF and a machine checks the Markdown, so the two drifting apart would mean the
checkable artifact is no longer the one that was sent.

**Nothing is written until everything renders.** Both documents are built in memory first, so a
refused or unrenderable emit leaves no directory, no empty file, and nothing that could be
mistaken for a partial submission.

**On the latin-1 limit.** fpdf2's core fonts cover latin-1 only, and this corpus contains
em-dashes. Substituting a character inside a quoted passage would make the PDF disagree with the
note it claims to quote — reintroducing, at the very last step, the exact failure the verifier
exists to prevent. So an unrenderable character raises `ArtifactRenderError` instead. The fix,
when a real note needs it, is to embed a Unicode TTF via `FPDF.add_font` and select it; that is a
few lines here plus a font file, and deliberately not done speculatively.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from attest.gates import ApprovalRequired, content_hash
from attest.models import EvidenceSpan, Packet

ARTIFACT_NAME = "submission.md"
PDF_NAME = "submission.pdf"
APPROVAL_NAME = "approval.json"

Block = tuple[str, str]
"""(kind, text) — kind is one of h1, h2, note, bullet, sub."""


class ArtifactRenderError(RuntimeError):
    """The artifact could not be rendered faithfully, so it was not written at all."""


def _spans(packet: Packet) -> dict[str, EvidenceSpan]:
    return {s.span_id: s for v in packet.coverage.verdicts for s in v.spans}


def _blocks(packet: Packet) -> list[Block]:
    """The document's content, once, in the order it is read.

    Deliberately ASCII in everything this module writes itself. Quotes and payer criteria are
    passed through untouched — they are evidence, and evidence is not reformatted to suit a
    renderer.
    """
    spans = _spans(packet)
    approval = packet.approval
    assert approval is not None  # guaranteed by emit_submission_artifact

    blocks: list[Block] = [
        ("h1", f"Prior authorization request - {packet.case_id}"),
        ("note", "SYNTHETIC DEMONSTRATION DATA. Not a real patient and not for clinical use."),
        ("h2", "Approval"),
        ("bullet", f"Policy pack: {packet.coverage.pack_id}"),
        ("bullet", f"Approved by: {approval.approver}"),
        ("bullet", f"Approved at: {approval.approved_at.isoformat()}"),
        ("bullet", f"Content hash (SHA-256): {approval.content_hash}"),
        ("h2", "Medical-necessity justification"),
    ]

    def evidence(span: EvidenceSpan) -> Block:
        return (
            "sub",
            f'Evidence {span.span_id} (note chars {span.start} to {span.end}): "{span.quote}"',
        )

    shown: set[str] = set()

    for claim in packet.justification.claims:
        blocks.append(("bullet", claim.text))
        for span_id in claim.supporting_span_ids:
            span = spans.get(span_id)
            if span is not None:
                blocks.append(evidence(span))
                shown.add(span_id)

    blocks.append(("h2", "Criteria coverage"))
    for verdict in packet.coverage.verdicts:
        cited = ", ".join(s.span_id for s in verdict.spans) or "no evidence cited"
        blocks.append(
            ("bullet", f"{verdict.criterion_id}: {verdict.verdict.value.upper()} ({cited})")
        )
        # Evidence on a criterion no claim argued - an INSUFFICIENT one, typically - still belongs
        # in the packet. It shows the practice documented something, just not enough, and omitting
        # it would make the record look thinner than it is. Shown once, here, if not shown above.
        for span in verdict.spans:
            if span.span_id not in shown:
                blocks.append(evidence(span))
                shown.add(span.span_id)

    if packet.gaps:
        blocks.append(("h2", "Outstanding questions for the practice"))
        for gap in packet.gaps:
            blocks.append(("bullet", f"{gap.criterion_id}: {gap.question}"))
            blocks.append(("sub", f"Missing: {gap.missing}"))

    return blocks


def _render_markdown(blocks: list[Block]) -> str:
    prefix = {"h1": "# ", "h2": "\n## ", "note": "> ", "bullet": "- ", "sub": "  - "}
    return "\n".join(f"{prefix[kind]}{text}" for kind, text in blocks).strip() + "\n"


def _render_pdf(blocks: list[Block]) -> bytes:
    """Render the same blocks to PDF, refusing rather than substituting characters."""
    from fpdf import FPDF

    for _, text in blocks:
        for char in text:
            if ord(char) > 0xFF:
                raise ArtifactRenderError(
                    f"cannot render {char!r} (U+{ord(char):04X}) in the PDF: fpdf2's core fonts "
                    f"cover latin-1 only. Substituting it would make the PDF disagree with the "
                    f"note it quotes, so nothing was written. Embed a Unicode TTF with "
                    f"FPDF.add_font to support it."
                )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    styles = {
        "h1": ("helvetica", "B", 15),
        "h2": ("helvetica", "B", 12),
        "note": ("helvetica", "I", 9),
        "bullet": ("helvetica", "", 10),
        "sub": ("helvetica", "", 9),
    }
    indents = {"sub": 8.0}
    bullets = {"bullet": "- ", "sub": "- "}

    for kind, text in blocks:
        family, style, size = styles[kind]
        pdf.set_font(family, style, size)
        pdf.set_left_margin(10.0 + indents.get(kind, 0.0))
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5, f"{bullets.get(kind, '')}{text}" or " ")
        pdf.ln(1 if kind in ("bullet", "sub") else 2)

    return bytes(pdf.output())


def emit_submission_artifact(packet: Packet, out_dir: Path | str = Path("out")) -> Path:
    """Write the approved submission artifact as Markdown and PDF, plus its approval record.

    Returns the path to the Markdown document; the PDF sits beside it with the same stem.

    Raises `ApprovalRequired` if the packet carries no approval, or if the approved content hash
    does not match the packet being emitted — the second case catches a packet edited after
    sign-off, which is exactly the failure an approval record exists to make impossible.
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
            f"{approval.approver!r}. Approved {approval.content_hash[:12]}..., "
            f"emitting {actual[:12]}.... Re-approve the current content."
        )

    # Render both documents before touching the filesystem, so a failure leaves nothing behind.
    blocks = _blocks(packet)
    markdown = _render_markdown(blocks)
    pdf_bytes = _render_pdf(blocks)

    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)

    artifact = directory / ARTIFACT_NAME
    artifact.write_text(markdown, encoding="utf-8", newline="\n")
    (directory / PDF_NAME).write_bytes(pdf_bytes)
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
