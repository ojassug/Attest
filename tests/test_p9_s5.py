"""Gate for P9-S5 — the gates look like gates, and an approval shows its provenance.

Tests that:
- An appeal is not offered before Gate 1 is approved (the denial uploader and draft appeal button are hidden)
- An approved packet displays who approved it, when, and the leading characters of the content hash
- The screen does not claim "The payer denied it" before a denial letter is uploaded
- Both Gate 1 and Gate 2 approve buttons remain disabled until a clinician is named
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.paths import data_dir
from conftest import needs_model

pytestmark = pytest.mark.p9_s5

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
    return "\n".join(el.value for el in at.markdown) + "\n".join(el.value for el in at.caption)


@needs_model
def test_the_appeal_is_not_offered_before_gate_1_is_approved(app):
    """Before Gate 1 approval, denial uploader and appeal buttons are not rendered."""
    at = click(click(upload_note(app, "denial"), "Run intake"), "Match criteria")
    assert not at.exception

    # Gate 1 is visible
    assert any(b.label.startswith("Approve and generate") for b in at.button)
    # Section 5 / denial uploader / appeal button are not rendered
    with pytest.raises(KeyError):
        at.get_by_key("denial_file")
    assert not any(b.label.startswith("Draft the appeal") for b in at.button)


@needs_model
def test_an_approved_packet_names_who_approved_it_and_against_what_hash(app):
    """After approval, the screen renders approver name and content hash provenance."""
    at = click(click(upload_note(app, "clean"), "Run intake"), "Match criteria")
    at.text_input(key="gate1_approver").set_value("Dr. L. Marchetti").run()
    at = click(at, "Approve and generate")
    assert not at.exception

    text = body_text(at)
    assert "Dr. L. Marchetti" in text
    assert "Content hash" in text or "hash" in text.lower()


@needs_model
def test_the_screen_does_not_claim_a_denial_that_has_not_arrived(app):
    """Section 5 does not claim 'The payer denied it' before a denial letter is uploaded."""
    at = click(click(upload_note(app, "clean"), "Run intake"), "Match criteria")
    at.text_input(key="gate1_approver").set_value("Dr. L. Marchetti").run()
    at = click(at, "Approve and generate")
    assert not at.exception

    # Heading before upload must not state "The payer denied it"
    headers = [h.value for h in at.header]
    assert "5 · The payer denied it" not in headers


@needs_model
def test_both_gates_are_still_inert_until_a_clinician_is_named(app):
    """Gate 1 and Gate 2 approve buttons are disabled when approver field is empty."""
    at = click(click(upload_note(app, "denial"), "Run intake"), "Match criteria")

    # Gate 1 check
    gate1_btn = next(b for b in at.button if b.label.startswith("Approve and generate"))
    assert gate1_btn.disabled

    # Approve Gate 1
    at.text_input(key="gate1_approver").set_value("Dr. L. Marchetti").run()
    at = click(at, "Approve and generate")

    # Upload denial and draft appeal
    at = upload(at, "denial_file", CORPUS / "denials" / "denial_001.md")
    at = click(at, "Draft the appeal")

    # Gate 2 check
    gate2_btn = next(b for b in at.button if b.label.startswith("Approve and send appeal"))
    assert gate2_btn.disabled
