"""Gate for P9-S12 — the sidebar's case list says something.

Tests that:
- A stored case is listed with its case ID and its payer
- The landing screen offers nothing to reset (no "Reset this case" button when no note is loaded)
- A case the store cannot read does not take the sidebar down (resilient listing across healthy cases)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.models import Case, InsuranceInfo, ServiceRequest
from attest.paths import data_dir
from attest.store import list_case_summaries, save_case

pytestmark = pytest.mark.p9_s12

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
APP = str(APP_PATH)
CORPUS = data_dir() / "synthetic"
TIMEOUT = 90


def a_case(case_id: str, payer: str) -> Case:
    return Case(
        case_id=case_id,
        note_id=case_id,
        patient_ref="SYNTH-PT",
        insurance=InsuranceInfo(payer=payer, plan="Commercial", member_id="M-1"),
        service=ServiceRequest(service="Repetitive TMS", cpt_codes=["90867"]),
        primary_diagnosis_code="F33.2",
        primary_diagnosis_text="Major depressive disorder, recurrent, severe",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def store(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("ATTEST_STORE_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("ATTEST_OUT_DIR", str(tmp_path / "out"))
    return tmp_path / "sessions"


@pytest.fixture
def app(store):
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


def test_a_stored_case_is_listed_with_its_payer(store):
    """`SYNTH-001` alone is not a case list. The payer is the field that makes it one."""
    save_case(a_case("SYNTH-001", "PacificSource"))
    save_case(a_case("SYNTH-003", "Highmark Health Options"))

    summaries = list_case_summaries()

    assert [s.case_id for s in summaries] == ["SYNTH-001", "SYNTH-003"], "not sorted by case id"
    assert [s.payer for s in summaries] == ["PacificSource", "Highmark Health Options"]
    assert all(s.service for s in summaries), "a listing with no service names nothing useful"

    # Also verify on screen that the sidebar renders payer beside case ID
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    assert not at.exception
    text = "\n".join(el.value for el in at.markdown)
    assert "SYNTH-001" in text and "PacificSource" in text
    assert "SYNTH-003" in text and "Highmark Health Options" in text


def test_the_landing_screen_offers_nothing_to_reset(app):
    """Before an upload or sample is loaded, 'Reset this case' is not rendered."""
    assert not app.exception
    reset_buttons = [b for b in app.button if b.label.startswith("Reset this case")]
    assert len(reset_buttons) == 0, "Reset this case button was rendered on landing screen"

    # Once a note is uploaded, the reset button appears
    at = upload_note(app, "clean")
    assert not at.exception
    reset_buttons_after = [b for b in at.button if b.label.startswith("Reset this case")]
    assert len(reset_buttons_after) == 1


def test_a_case_the_store_cannot_read_does_not_take_the_sidebar_down(store):
    """A corrupted case snapshot is skipped and does not crash the sidebar on render."""
    save_case(a_case("SYNTH-001", "PacificSource"))
    save_case(a_case("SYNTH-003", "Highmark Health Options"))

    damaged = [p for p in store.rglob("*.json") if "SYNTH-001" in str(p)]
    assert damaged, "the fixture did not write the snapshot this test damages"
    for path in damaged:
        path.write_text(
            json.dumps({"agent_id": "x", "state": {"attest_case": {"not": "a case"}}}),
            encoding="utf-8",
        )

    # list_case_summaries skips damaged case
    summaries = list_case_summaries()
    assert [s.case_id for s in summaries] == ["SYNTH-003"]

    # Streamlit app renders without exception and displays the healthy case in the sidebar
    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    assert not at.exception
    text = "\n".join(el.value for el in at.markdown)
    assert "SYNTH-003" in text and "Highmark Health Options" in text
    assert "SYNTH-001" not in text
