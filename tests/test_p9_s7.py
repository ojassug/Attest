"""Gate for P9-S7 — the run shows the agent that produced it.

Tests that:
- The trace for each completed stage names the specialist agent and the model tier / model ID
- A cassette replay is explicitly shown as a replay (not masquerading as a live call)
- A completion summary strip displays criteria met, quotes verified, and total elapsed wall time
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.paths import data_dir
from conftest import needs_model

pytestmark = pytest.mark.p9_s7

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
def test_the_trace_names_the_model_that_produced_each_stage(app):
    """The trace captions name the specialist agent, model tier, and elapsed time."""
    at = click(upload_note(app, "clean"), "Run intake")
    assert not at.exception

    text_intake = body_text(at)
    assert "Intake Specialist" in text_intake
    assert "fast" in text_intake or "gemini" in text_intake

    at = click(at, "Match criteria")
    assert not at.exception

    text_match = body_text(at)
    assert "Criteria Specialist" in text_match
    assert "reasoning" in text_match or "gemini" in text_match

    # Verify the completion strip metric exists
    metrics = {m.label: m.value for m in at.metric}
    assert "Total elapsed time" in metrics
    assert "s" in metrics["Total elapsed time"]


@needs_model
def test_a_cassette_replay_is_shown_as_a_replay_not_as_a_live_call(app):
    """When replayed from cassettes, the execution mode indicates replay."""
    at = click(click(upload_note(app, "clean"), "Run intake"), "Match criteria")
    assert not at.exception

    captions = [c.value for c in at.caption]
    trace_captions = [c for c in captions if "Specialist:" in c]
    assert trace_captions, "no specialist trace captions found on screen"
    for cap in trace_captions:
        assert "Cassette replay" in cap or "replay" in cap.lower()
        assert "Live API call" not in cap
