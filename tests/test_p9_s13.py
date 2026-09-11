"""Gate for P9-S13 — the routing moment says it was derived, not configured.

Tests that:
- The policy match panel names the extracted payer, plan, and CPT and states the pack was derived/selected
- Two notes with different payers reach two different policy packs dynamically through the unchanged screen
- An unlisted payer still stops the review without claiming a policy match
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.paths import data_dir
from conftest import needs_model

pytestmark = pytest.mark.p9_s13

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
APP = str(APP_PATH)
CORPUS = data_dir() / "synthetic"
TIMEOUT = 90


@pytest.fixture
def new_app(tmp_path, monkeypatch):
    def make() -> AppTest:
        monkeypatch.setenv("ATTEST_STORE_DIR", str(tmp_path / "sessions"))
        monkeypatch.setenv("ATTEST_OUT_DIR", str(tmp_path / "out"))
        return AppTest.from_file(APP, default_timeout=TIMEOUT).run()

    return make


@pytest.fixture
def app(new_app):
    return new_app()


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


@needs_model
def test_the_policy_panel_shows_what_the_match_was_made_from(app):
    """The match panel displays extracted payer, plan, CPT and derivation provenance."""
    at = click(upload_note(app, "clean"), "Run intake")
    assert not at.exception

    note_key = at.session_state["note_key"]
    case = at.session_state["results"][note_key]["case"]

    success_texts = "\n".join(s.value for s in at.success)
    assert "Policy matched" in success_texts
    assert case.insurance.payer in success_texts
    assert case.insurance.plan in success_texts
    assert any(cpt in success_texts for cpt in case.service.cpt_codes)
    assert "Derived" in success_texts or "selected" in success_texts.lower()


@needs_model
def test_two_payers_reach_two_packs_through_the_same_screen(new_app):
    """Two different notes dynamically route to two distinct policy packs without configuration."""
    at_pacific = click(upload_note(new_app(), "clean"), "Run intake")
    assert not at_pacific.exception
    pacific_success = "\n".join(s.value for s in at_pacific.success)
    assert "PacificSource" in pacific_success
    assert "Highmark" not in pacific_success

    at_highmark = click(upload_note(new_app(), "denial"), "Run intake")
    assert not at_highmark.exception
    highmark_success = "\n".join(s.value for s in at_highmark.success)
    assert "Highmark" in highmark_success
    assert "PacificSource" not in highmark_success


@needs_model
def test_an_unlisted_payer_still_stops_the_review(app, monkeypatch):
    """An unlisted payer stops the review with a clear warning and renders no match success."""
    monkeypatch.setattr("attest.policies.loader.find_pack", lambda **kwargs: None)

    at = click(upload_note(app, "clean"), "Run intake")
    assert not at.exception

    # No policy match success box
    assert not any("Policy matched" in s.value for s in at.success)

    # Warning indicating no policy on file
    warnings = [w.value for w in at.warning]
    assert any("No policy on file" in w for w in warnings)

    # Pipeline stops: Match criteria button is not rendered
    assert not any(b.label.startswith("Match criteria") for b in at.button)
