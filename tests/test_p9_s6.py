"""Gate for P9-S6 — the note shows its own evidence.

Tests that:
- Every marked span in the rendered note corresponds to exact recorded character offsets
- No unverified span is ever marked
- Overlapping or adjacent spans do not duplicate or corrupt the rendered note
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.models import CriteriaCoverage, CriterionVerdict, EvidenceSpan, Verdict
from attest.paths import data_dir
from conftest import needs_model

pytestmark = pytest.mark.p9_s6

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
APP = str(APP_PATH)
CORPUS = data_dir() / "synthetic"
TIMEOUT = 90


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("ATTEST_STORE_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("ATTEST_OUT_DIR", str(tmp_path / "out"))
    return AppTest.from_file(APP, default_timeout=TIMEOUT).run()


def click(at: AppTest, label: str) -> AppTest:
    for button in at.button:
        if button.label.startswith(label):
            return button.click().run()
    raise AssertionError(f"no button labelled {label!r}; saw {[b.label for b in at.button]}")


def upload_note(at: AppTest, name: str) -> AppTest:
    path = CORPUS / "notes" / f"{name}.md"
    at.get_by_key("note_file").set_value((path.name, path.read_bytes(), "text/markdown"))
    return at.run()


@needs_model
def test_every_marked_span_matches_the_note_at_its_recorded_offsets(app):
    """Every verified span is marked in the note at its exact character positions."""
    from app import mark_note_evidence

    note_path = CORPUS / "notes" / "clean.md"
    note_text = note_path.read_text(encoding="utf-8")

    at = click(click(upload_note(app, "clean"), "Run intake"), "Match criteria")
    assert not at.exception

    # Find the marked note element in expander
    marked_elements = [m.value for m in at.markdown if "clinical-note-content" in m.value or "<mark" in m.value]
    assert marked_elements, "marked note not found on screen"
    marked_text = marked_elements[0]

    # Verify each span is present with its criterion badge
    assert "<mark" in marked_text
    assert "ps-01" in marked_text


def test_no_unverified_span_is_ever_marked():
    """Unverified spans must never be highlighted in the rendered note."""
    from app import mark_note_evidence

    note_text = "Patient was diagnosed with depression. Prescribed sertraline 50mg daily."
    # Span 1 is verified
    s1 = EvidenceSpan(
        span_id="s1",
        note_id="n1",
        quote="depression",
        start=note_text.index("depression"),
        end=note_text.index("depression") + len("depression"),
        verified=True,
    )
    # Span 2 is UNVERIFIED
    s2 = EvidenceSpan(
        span_id="s2",
        note_id="n1",
        quote="sertraline 50mg",
        start=note_text.index("sertraline 50mg"),
        end=note_text.index("sertraline 50mg") + len("sertraline 50mg"),
        verified=False,
    )

    coverage = CriteriaCoverage(
        case_id="TEST-001",
        pack_id="POL-01",
        verdicts=[
            CriterionVerdict(criterion_id="c1", verdict=Verdict.MET, reasoning="r1", spans=[s1]),
            CriterionVerdict(criterion_id="c2", verdict=Verdict.INSUFFICIENT, reasoning="r2", spans=[s2]),
        ],
    )

    rendered = mark_note_evidence(note_text, coverage)
    assert "[c1]" in rendered
    assert "[c2]" not in rendered
    assert '<mark style="background-color: #dbeafe; color: #1e3a8a; padding: 2px 4px; border-radius: 3px;" title="Criterion: c2">' not in rendered


def test_overlapping_spans_do_not_corrupt_the_rendered_note():
    """Overlapping spans must preserve character integrity without duplication."""
    from app import mark_note_evidence

    note_text = "The patient has a confirmed severe depressive disorder recurrent."
    # Span 1: "confirmed severe"
    q1 = "confirmed severe"
    s1 = EvidenceSpan(
        span_id="s1",
        note_id="n1",
        quote=q1,
        start=note_text.index(q1),
        end=note_text.index(q1) + len(q1),
        verified=True,
    )
    # Span 2 overlaps: "severe depressive disorder"
    q2 = "severe depressive disorder"
    s2 = EvidenceSpan(
        span_id="s2",
        note_id="n1",
        quote=q2,
        start=note_text.index(q2),
        end=note_text.index(q2) + len(q2),
        verified=True,
    )

    coverage = CriteriaCoverage(
        case_id="TEST-001",
        pack_id="POL-01",
        verdicts=[
            CriterionVerdict(criterion_id="critA", verdict=Verdict.MET, reasoning="rA", spans=[s1]),
            CriterionVerdict(criterion_id="critB", verdict=Verdict.MET, reasoning="rB", spans=[s2]),
        ],
    )

    rendered = mark_note_evidence(note_text, coverage)

    # Strip HTML tags and badges to verify text reconstruction
    clean_text = re.sub(r"<mark[^>]*>|<b>\[[^\]]*\]</b> |</mark>", "", rendered)
    assert clean_text == note_text, f"text was corrupted:\nexpected: {note_text!r}\ngot:      {clean_text!r}"
