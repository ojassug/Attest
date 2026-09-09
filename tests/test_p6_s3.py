"""Gate for P6-S3 — the reviewer's console.

The Definition of Done asks for `test_app_imports_without_error`, and that is here. But an import
check only proves the file parses, and this is the screen a clinician approves from — so the rest
of this module drives the real app through Streamlit's `AppTest`, clicking the buttons a user
clicks.

What that buys, specifically: **the UI cannot be the place the gates get weakened.** Gate 1 and
Gate 2 are enforced in `attest.gates` and the emitters, and thirteen tests already hold them there.
The failure this module exists to catch is different — a UI that renders an approval control the
gate never sees, or writes a document before anyone pressed anything. Those tests pass in
`test_p4_s2.py` and would still pass with a broken screen in front of them.

The app replays from committed cassettes, so this runs offline with no API key, exactly as a judge
would see it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.packet.emit import ARTIFACT_NAME, PDF_NAME
from conftest import needs_model

pytestmark = pytest.mark.p6_s3

APP = str(Path(__file__).resolve().parents[1] / "app.py")

# The pipeline replays from cassettes rather than calling a model, but it still reads and matches
# every criterion in a pack. Streamlit's 3s default is tuned for widget scripts, not for this.
TIMEOUT = 90


@pytest.fixture
def app(tmp_path, monkeypatch):
    """The app, writing to a scratch directory instead of the repo."""
    monkeypatch.setenv("ATTEST_STORE_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("ATTEST_OUT_DIR", str(tmp_path / "out"))
    return AppTest.from_file(APP, default_timeout=TIMEOUT).run()


def click(at: AppTest, label: str) -> AppTest:
    """Press the button whose label starts with `label`, and re-run the script."""
    for button in at.button:
        if button.label.startswith(label):
            return button.click().run()
    raise AssertionError(f"no button labelled {label!r}; saw {[b.label for b in at.button]}")


def select_case(at: AppTest, name: str) -> AppTest:
    at.session_state["case_name"] = name
    return at.run()


def body_text(at: AppTest) -> str:
    return "\n".join(el.value for el in at.markdown) + "\n".join(el.value for el in at.caption)


# ------------------------------------------------------------------- the DoD test


def test_app_imports_without_error(app):
    assert not app.exception


# --------------------------------------------------------------------- it renders


def test_the_landing_screen_names_the_payer_and_the_policy(app):
    """A reviewer has to know which payer's rules are being applied before reading a verdict."""
    assert not app.exception
    assert "Prior authorization review" in [t.value for t in app.title]

    text = body_text(app)
    assert "PacificSource" in text
    assert "https://" in text  # the policy is linked, not merely named


def test_the_synthetic_data_banner_is_always_visible(app):
    """§7 requires the synthetic-data stance stated openly, not buried in a README."""
    assert any("Synthetic data only" in w.value for w in app.sidebar.warning)


@needs_model
def test_criteria_coverage_shows_a_verdict_and_its_evidence(app):
    """The product's core, on screen: per-criterion verdicts with the quotes behind them."""
    at = click(click(app, "Run intake"), "Match criteria")
    assert not at.exception

    labels = [e.label for e in at.expander]
    assert any("ps-01" in label for label in labels), labels

    # Every quote shown must have been verified, and the screen must say so.
    assert "verified verbatim" in body_text(at)

    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Criteria met"].endswith("/10")
    assert metrics["Verified verbatim"].split("/")[0] == metrics["Verified verbatim"].split("/")[1]


@needs_model
def test_the_gap_case_asks_the_practice_a_question(app):
    """A gap is a question for the practice, and the UI has to actually ask it."""
    at = click(click(select_case(app, "gap"), "Run intake"), "Match criteria")
    assert not at.exception

    text = body_text(at)
    assert "ps-04b" in text
    assert "?" in text


# ------------------------------------------------------------ the gates, on screen


@needs_model
def test_gate_1_writes_nothing_until_a_clinician_is_named(app, tmp_path):
    """The approval control exists, and it is inert until someone signs it.

    A UI that renders an enabled approve button with no approver would hand `emit_submission_artifact`
    a blank name — the emitter refuses that, but the reviewer would see a crash instead of a gate.
    """
    at = click(click(app, "Run intake"), "Match criteria")

    approve = [b for b in at.button if b.label.startswith("Approve and generate")]
    assert approve, "Gate 1 has no approval control"
    assert approve[0].disabled, "Gate 1 would emit without a named clinician"

    assert not list((tmp_path / "out").rglob(ARTIFACT_NAME)), "a document was written before approval"


@needs_model
def test_gate_1_emits_both_documents_once_approved(app, tmp_path):
    at = click(click(app, "Run intake"), "Match criteria")

    at.text_input(key="gate1_approver").set_value("Dr. L. Marchetti").run()
    at = click(at, "Approve and generate")
    assert not at.exception

    out = tmp_path / "out" / "SYNTH-001"
    assert (out / ARTIFACT_NAME).exists()
    assert (out / PDF_NAME).exists()

    # The approval that authorised it is persisted beside the document, naming who signed.
    assert "Marchetti" in (out / "approval.json").read_text(encoding="utf-8")

    assert [b.label for b in at.download_button] == [
        "Download submission (Markdown)",
        "Download submission (PDF)",
    ]


@needs_model
def test_gate_2_holds_the_appeal_the_same_way(app, tmp_path):
    """The denial case runs the second half of the loop, and stops at the second gate."""
    at = click(click(select_case(app, "denial"), "Run intake"), "Match criteria")
    at = click(at, "Draft the appeal")
    assert not at.exception

    text = body_text(at)
    assert "Appeal deadline" in "\n".join(i.value for i in at.info)
    assert "hho-" in text, "the appeal does not name the criteria it answers"

    approve = [b for b in at.button if b.label.startswith("Approve and send appeal")]
    assert approve and approve[0].disabled

    assert not list((tmp_path / "out").rglob("appeal.md")), "an appeal was written before approval"

    at.text_input(key="gate2_approver").set_value("Dr. L. Marchetti").run()
    at = click(at, "Approve and send appeal")
    assert not at.exception
    assert (tmp_path / "out" / "SYNTH-003" / "appeal.md").exists()


# ----------------------------------------------------------------------- the store


@needs_model
def test_running_a_case_files_it_in_the_case_store(app, tmp_path):
    """The sidebar's open-case list is the case store, not a UI-local list."""
    from attest.store import load_case

    at = click(app, "Run intake")
    assert not at.exception

    assert load_case("SYNTH-001", tmp_path / "sessions") is not None
    assert "SYNTH-001" in "\n".join(el.value for el in at.sidebar.markdown)
