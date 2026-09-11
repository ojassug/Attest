"""Gate for P9-S11 — the deadline leads with the number a practice acts on.

Tests that:
- The days remaining metric agrees with the deadline on the appeal
- An undisclosed window still discloses that it is a placeholder
- A deadline already in the past does not render a negative countdown
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.paths import data_dir
from conftest import needs_model

pytestmark = pytest.mark.p9_s11

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


def run_to_appeal_draft(app: AppTest) -> AppTest:
    at = click(click(upload_note(app, "denial"), "Run intake"), "Match criteria")
    at.text_input(key="gate1_approver").set_value("Dr. L. Marchetti").run()
    at = click(at, "Approve and generate")
    at = upload(at, "denial_file", CORPUS / "denials" / "denial_001.md")
    return click(at, "Draft the appeal")


@needs_model
def test_the_days_remaining_agree_with_the_deadline_on_the_appeal(app):
    """Appeal deadline and days remaining are rendered as metrics agreeing with the appeal."""
    at = run_to_appeal_draft(app)
    assert not at.exception

    note_key = at.session_state["note_key"]
    state = at.session_state["results"][note_key]
    appeal = state["appeal"]

    today = datetime.now(timezone.utc).date()
    expected_days = max(0, (appeal.deadline - today).days)

    metrics = {m.label: m.value for m in at.metric}
    assert "Appeal deadline" in metrics
    assert metrics["Appeal deadline"] == appeal.deadline.isoformat()
    assert "Days remaining" in metrics
    assert metrics["Days remaining"] == f"{expected_days} days"


@needs_model
def test_an_undisclosed_window_still_says_it_is_a_placeholder(app):
    """The appeal section continues to disclose the window provenance and placeholder notice."""
    at = run_to_appeal_draft(app)
    assert not at.exception

    info_texts = "\n".join(i.value for i in at.info)
    assert "Window source:" in info_texts
    assert "Placeholder" in info_texts or "NOT STATED" in info_texts


@needs_model
def test_a_deadline_already_past_does_not_render_a_negative_countdown(app, monkeypatch):
    """A deadline set in the past renders as 0 days, never a negative number."""
    from attest.appeal import assemble as orig_assemble

    orig_build = orig_assemble.build_appeal

    def mock_build_appeal(denial, rebuttals, pack):
        real_appeal = orig_build(denial, rebuttals, pack)
        return real_appeal.model_copy(update={"deadline": date(2020, 1, 1)})

    monkeypatch.setattr("attest.appeal.assemble.build_appeal", mock_build_appeal)

    at = run_to_appeal_draft(app)
    assert not at.exception

    metrics = {m.label: m.value for m in at.metric}
    assert "Days remaining" in metrics
    assert metrics["Days remaining"] == "0 days"
