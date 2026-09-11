"""Gate for P9-S9 — red means one thing.

Tests that:
- REQUIRED prior authorization is not styled as a failure (renders via st.info, not st.error)
- UNKNOWN requirement is not styled as a success (renders via st.warning, never st.success)
- A clean intake renders no error elements at all on screen
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.models import PADetermination, PARequirement
from attest.paths import data_dir
from conftest import needs_model

pytestmark = pytest.mark.p9_s9

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
def test_a_required_authorization_is_not_styled_as_a_failure(app):
    """REQUIRED renders as an informational block (st.info), not an error (st.error)."""
    at = click(upload_note(app, "clean"), "Run intake")
    assert not at.exception

    # Check info blocks for "Required"
    info_texts = [i.value for i in at.info]
    assert any("Required" in text for text in info_texts), f"Required not found in info blocks: {info_texts}"
    # Verify no error blocks contain "Required"
    error_texts = [e.value for e in at.error]
    assert not any("Required" in text for text in error_texts), f"Required rendered as an error: {error_texts}"


@needs_model
def test_an_unknown_requirement_is_still_not_styled_as_a_success(app, monkeypatch):
    """UNKNOWN requirement must never render as st.success (which implies no PA needed)."""
    monkeypatch.setattr(
        "attest.tools.pa_lookup.check_pa_required",
        lambda *args, **kwargs: PADetermination(
            requirement=PARequirement.UNKNOWN,
            policy_id=None,
            citation=None,
            rationale="No policy found for payer.",
        ),
    )
    monkeypatch.setattr("attest.policies.loader.find_pack", lambda **kwargs: None)

    at = click(upload_note(app, "clean"), "Run intake")
    assert not at.exception

    # UNKNOWN renders as st.warning
    warning_texts = [w.value for w in at.warning]
    assert any("Unknown" in text for text in warning_texts)

    # UNKNOWN must not render in st.success
    success_texts = [s.value for s in at.success]
    assert not any("Unknown" in text for text in success_texts)


@needs_model
def test_a_clean_intake_renders_no_error_element_at_all(app):
    """On a clean case where nothing went wrong, no st.error element may appear."""
    at = click(upload_note(app, "clean"), "Run intake")
    assert not at.exception
    assert len(at.error) == 0, f"unexpected error elements on clean intake: {[e.value for e in at.error]}"
