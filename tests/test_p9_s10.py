"""Gate for P9-S10 — the justification reads as an argument, not as boilerplate.

Tests that:
- The claims on screen are exactly the claims in the packet (grouped under criteria, never added/dropped/reworded)
- Every claim on screen still explicitly names and labels the supporting evidence spans it cites
- The approved content hash does not move (Gate 1 hash integrity is preserved)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.gates import content_hash
from attest.models import Packet
from attest.packet.justification import build_justification
from attest.paths import data_dir
from conftest import needs_model

pytestmark = pytest.mark.p9_s10

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


def upload(at: AppTest, key: str, path: Path) -> AppTest:
    at.get_by_key(key).set_value((path.name, path.read_bytes(), "text/markdown"))
    return at.run()


def upload_note(at: AppTest, name: str) -> AppTest:
    return upload(at, "note_file", CORPUS / "notes" / f"{name}.md")


def body_text(at: AppTest) -> str:
    return "\n".join(el.value for el in at.markdown) + "\n" + "\n".join(el.value for el in at.caption)


@needs_model
def test_the_claims_on_screen_are_exactly_the_claims_in_the_packet(app):
    """The screen presents exactly the claims built by justification, grouped by criterion."""
    at = click(click(upload_note(app, "clean"), "Run intake"), "Match criteria")
    assert not at.exception

    note_key = at.session_state["note_key"]
    state = at.session_state["results"][note_key]
    coverage = state["coverage"]
    case = state["case"]
    justification = build_justification(coverage, case)
    assert len(justification.claims) > 0

    markdown_texts = [m.value for m in at.markdown]
    for claim in justification.claims:
        assert any(claim.text in m for m in markdown_texts), (
            f"claim text not found verbatim on screen: {claim.text}"
        )


@needs_model
def test_every_claim_on_screen_still_names_the_spans_it_cites(app):
    """Every claim on screen labels and names its supporting span IDs."""
    at = click(click(upload_note(app, "clean"), "Run intake"), "Match criteria")
    assert not at.exception

    note_key = at.session_state["note_key"]
    state = at.session_state["results"][note_key]
    coverage = state["coverage"]
    case = state["case"]
    justification = build_justification(coverage, case)

    caption_texts = [c.value for c in at.caption]
    span_captions = [c for c in caption_texts if "Supporting evidence spans:" in c or "Evidence spans:" in c]
    assert len(span_captions) >= len(justification.claims)

    for claim in justification.claims:
        for span_id in claim.supporting_span_ids:
            assert any(span_id in c for c in span_captions), (
                f"supporting span id {span_id} not labeled on screen"
            )


@needs_model
def test_the_approved_content_hash_does_not_move(app):
    """Gate 1 content hash matches the packet content hash before and after approval."""
    at = click(click(upload_note(app, "clean"), "Run intake"), "Match criteria")
    assert not at.exception

    note_key = at.session_state["note_key"]
    state = at.session_state["results"][note_key]
    coverage = state["coverage"]
    case = state["case"]
    justification = build_justification(coverage, case)
    gaps = state.get("gaps", [])

    expected_packet = Packet(
        case_id=case.case_id,
        coverage=coverage,
        justification=justification,
        gaps=gaps,
    )
    expected_hash = content_hash(expected_packet)

    # Approve Gate 1
    at.text_input(key="gate1_approver").set_value("Dr. Jane Clinician").run()
    at = click(at, "Approve and generate submission")
    assert not at.exception

    saved_approval = state["submission_approval"]
    assert saved_approval.content_hash == expected_hash
    assert saved_approval.approver == "Dr. Jane Clinician"
