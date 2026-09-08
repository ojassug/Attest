"""Gate for P4-S3 — the submission artifact.

The artifact is what a payer actually receives, so it is the last surface where the product's
central claim has to hold: every clinical assertion in it traces to a quote that appears verbatim
in the source note.

Markdown is the checkable artifact and the assertions below are made against it. The PDF is a
rendering of the same packet — checked here for validity and for rendering without loss, because
fpdf2's core fonts cover latin-1 only and the corpus contains em-dashes. A renderer that quietly
substitutes characters inside a quoted passage would break the one promise this product makes, so
that case must fail loudly instead. See `test_unrenderable_quote_fails_rather_than_altering_it`.
"""

from datetime import datetime, timezone

import pytest

from attest.agents.intake import extract_case
from attest.corpus import all_cases
from attest.criteria.gaps import build_gap_list
from attest.criteria.match import match_all
from attest.gates import ApprovalRequired, content_hash
from attest.models import (
    ApprovalRecord,
    Claim,
    CriteriaCoverage,
    CriterionVerdict,
    EvidenceSpan,
    GapItem,
    Justification,
    Packet,
    Verdict,
)
from attest.packet.emit import ArtifactRenderError, emit_submission_artifact
from attest.packet.justification import build_justification
from attest.verifier import enforce_verification
from conftest import needs_model

pytestmark = pytest.mark.p4_s3


def span(span_id: str, quote: str) -> EvidenceSpan:
    return EvidenceSpan(
        span_id=span_id, note_id="note", quote=quote, verified=True, start=0, end=len(quote)
    )


def packet(*, quotes=(("ps-01-0", "PHQ-9 score is 21"),), gaps=()) -> Packet:
    spans = [span(i, q) for i, q in quotes]
    return Packet(
        case_id="SYNTH-001",
        coverage=CriteriaCoverage(
            case_id="SYNTH-001",
            pack_id="pacificsource-commercial-tms",
            verdicts=[
                CriterionVerdict(
                    criterion_id="ps-01", verdict=Verdict.MET, spans=spans, reasoning="documented"
                ),
                CriterionVerdict(
                    criterion_id="ps-04b", verdict=Verdict.INSUFFICIENT, reasoning="not stated"
                ),
            ],
        ),
        justification=Justification(
            claims=[Claim(text="Criterion ps-01 is met.", supporting_span_ids=[i for i, _ in quotes])]
        ),
        gaps=list(gaps),
    )


def approve(p: Packet) -> Packet:
    return p.model_copy(
        update={
            "approval": ApprovalRecord(
                approver="Dr. R. Okonkwo",
                approved_at=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
                content_hash=content_hash(p),
            )
        }
    )


# --------------------------------------------------------------------------- the DoD


def test_artifact_contains_every_criterion(tmp_path):
    """Including the ones that were not met. A packet that shows only wins is a sales document."""
    path = emit_submission_artifact(approve(packet()), out_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "ps-01" in text
    assert "ps-04b" in text


def test_artifact_contains_every_verified_quote(tmp_path):
    quotes = (("ps-01-0", "PHQ-9 score is 21"), ("ps-01-1", "Patient is 29 years of age."))
    path = emit_submission_artifact(approve(packet(quotes=quotes)), out_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    for _, quote in quotes:
        assert quote in text


def test_artifact_embeds_approval_hash(tmp_path):
    """A reader must be able to recompute what was approved from the document itself."""
    p = approve(packet())
    path = emit_submission_artifact(p, out_dir=tmp_path)

    assert content_hash(p) in path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- the PDF


def test_pdf_is_produced_alongside_the_markdown(tmp_path):
    path = emit_submission_artifact(approve(packet()), out_dir=tmp_path)
    pdf = path.with_suffix(".pdf")

    assert pdf.is_file()
    assert pdf.stat().st_size > 500


def test_pdf_is_structurally_valid(tmp_path):
    path = emit_submission_artifact(approve(packet()), out_dir=tmp_path)
    raw = path.with_suffix(".pdf").read_bytes()

    assert raw.startswith(b"%PDF-")
    assert raw.rstrip().endswith(b"%%EOF")


def test_unrenderable_quote_fails_rather_than_altering_it(tmp_path):
    """fpdf2's core fonts are latin-1 only, and the corpus contains em-dashes.

    Silently substituting a character inside a quoted passage would make the PDF disagree with the
    note it claims to quote — the exact failure the verifier exists to prevent, reintroduced at the
    last step. Refusing is the only honest option until a Unicode font is embedded.
    """
    p = approve(packet(quotes=(("ps-01-0", "PROGRESS NOTE — severe MDD"),)))

    with pytest.raises(ArtifactRenderError) as excinfo:
        emit_submission_artifact(p, out_dir=tmp_path)

    assert "—" in str(excinfo.value) or "2014" in str(excinfo.value).lower()


def test_nothing_is_left_behind_when_rendering_fails(tmp_path):
    """A half-written submission is worse than none — it looks like a real one."""
    p = approve(packet(quotes=(("ps-01-0", "PROGRESS NOTE — severe MDD"),)))

    with pytest.raises(ArtifactRenderError):
        emit_submission_artifact(p, out_dir=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_refused_emit_writes_neither_markdown_nor_pdf(tmp_path):
    """Gate 1 still governs: no approval means no artifact of any kind."""
    with pytest.raises(ApprovalRequired):
        emit_submission_artifact(packet(), out_dir=tmp_path)

    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------- content


def test_gaps_appear_in_the_artifact(tmp_path):
    """The payer should see what was asked of the practice, not just what was answered."""
    gap = GapItem(
        criterion_id="ps-04b", missing="No agent or dose stated.", question="Can you supply it?"
    )
    path = emit_submission_artifact(approve(packet(gaps=[gap])), out_dir=tmp_path)
    text = path.read_text(encoding="utf-8")

    assert "ps-04b" in text
    assert "Can you supply it?" in text


def test_evidence_on_an_unclaimed_criterion_still_appears(tmp_path):
    """An INSUFFICIENT criterion can still carry real evidence.

    `ps-04b` in the gap case is exactly this: the note says an augmentation trial happened but not
    with what, at what dose, or for how long. Omitting that quote would make the record look
    thinner than it is — the practice documented something, just not enough.
    """
    p = packet()
    p.coverage.verdicts[1].spans.append(span("ps-04b-0", "An augmentation trial was attempted."))

    text = emit_submission_artifact(approve(p), out_dir=tmp_path).read_text(encoding="utf-8")

    assert "An augmentation trial was attempted." in text


def test_each_verified_quote_appears_exactly_once(tmp_path):
    """Guard: evidence is shown under its claim, or in the coverage ledger — never both."""
    p = packet()
    p.coverage.verdicts[1].spans.append(span("ps-04b-0", "An augmentation trial was attempted."))

    text = emit_submission_artifact(approve(p), out_dir=tmp_path).read_text(encoding="utf-8")

    assert text.count("PHQ-9 score is 21") == 1
    assert text.count("An augmentation trial was attempted.") == 1


def test_artifact_is_utf8_with_lf_endings(tmp_path):
    """The encoding bug that opened this project started exactly here."""
    path = emit_submission_artifact(approve(packet()), out_dir=tmp_path)
    raw = path.read_bytes()

    assert raw.decode("utf-8")
    assert b"\r\n" not in raw


# --------------------------------------------------------------------------- real data


@needs_model
def test_every_case_emits_both_artifacts(tmp_path):
    for expected in all_cases():
        enforced = enforce_verification(
            match_all(
                expected.pack, expected.note_text, case_id=expected.case_id, note_id=expected.name
            ),
            expected.note_text,
        )
        case = extract_case(expected.note_text, case_id=expected.case_id)
        p = Packet(
            case_id=expected.case_id,
            coverage=enforced.coverage,
            justification=build_justification(enforced.coverage, case),
            gaps=build_gap_list(enforced.coverage),
        )

        out = tmp_path / expected.name
        path = emit_submission_artifact(approve(p), out_dir=out)
        text = path.read_text(encoding="utf-8")

        for verdict in enforced.coverage.verdicts:
            assert verdict.criterion_id in text
            for s in verdict.spans:
                assert s.quote in text, f"{expected.name}: quote missing from artifact"

        assert path.with_suffix(".pdf").is_file()
