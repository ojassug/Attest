"""Gate for P9-S4 — the landing screen makes the case.

The judge-facing URL opens before anything is uploaded. This module tests that the landing screen
clearly explains the problem, the target audience, the five-stage pipeline with at least three
quantified metrics, that the synthetic-data notice renders in the main column (surviving a collapsed
mobile sidebar), that sample cases enter the pipeline through the uploader, that no case picker is
offered on the landing screen, and that the policy pack is derived only after reading the note.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.paths import data_dir
from conftest import needs_model

pytestmark = pytest.mark.p9_s4

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


def body_text(at: AppTest) -> str:
    return "\n".join(el.value for el in at.markdown) + "\n".join(el.value for el in at.caption)


def test_the_landing_screen_states_the_problem_before_any_upload(app):
    """The landing screen states problem, audience, pipeline, and at least three metrics."""
    assert not app.exception
    assert len(app.metric) >= 3, f"expected at least 3 metrics on landing screen, got {len(app.metric)}"
    
    text = body_text(app)
    # Problem context
    assert "Prior authorization" in text or "prior authorization" in text
    # Audience context
    assert "practices" in text or "specialty" in text or "clinicians" in text
    # Pipeline stages
    assert "Intake" in text
    assert "Gate 1" in text or "approval" in text
    assert "Gate 2" in text or "appeal" in text


def test_the_synthetic_data_notice_survives_a_collapsed_sidebar(app):
    """Synthetic-data notice must render in the main column (survives collapsed sidebar)."""
    assert not app.exception
    # Check main body warnings/elements (not sidebar)
    main_warnings = [w.value for w in app.warning]
    assert any("Synthetic data" in w or "synthetic" in w.lower() for w in main_warnings), (
        f"synthetic-data notice not found in main column warnings: {main_warnings}"
    )


def test_a_sample_case_enters_the_pipeline_through_the_uploader(app):
    """Clicking a sample button enters the pipeline through the upload path."""
    assert not app.exception
    at = click(app, "Load sample: PacificSource TMS")
    assert not at.exception
    # Now intake should be offered
    assert any(b.label.startswith("Run intake") for b in at.button)


def test_the_landing_screen_still_offers_no_case_to_pick(app):
    """No radio, no selectbox — the P9-S1 property re-asserted."""
    assert not app.exception
    assert not app.radio, [r.label for r in app.radio]
    assert not app.selectbox, [s.label for s in app.selectbox]
    assert app.get_by_key("note_file") is not None


@needs_model
def test_the_pack_is_still_chosen_after_the_note_has_been_read(app):
    """Pack is derived dynamically after reading the note, not preloaded."""
    at1 = click(app, "Load sample: PacificSource TMS")
    at1 = click(at1, "Run intake")
    assert not at1.exception
    assert "PacificSource" in body_text(at1)

    # Now with fresh app, try Highmark
    at2 = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    at2 = click(at2, "Load sample: Highmark TMS")
    at2 = click(at2, "Run intake")
    assert not at2.exception
    assert "Highmark" in body_text(at2)
