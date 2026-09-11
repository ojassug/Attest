"""Gate for P9-S1 — the case arrives by upload, and routes itself.

P6-S3 built the reviewer's console around three committed corpus cases chosen from a radio. That
made the screen easy to test and impossible to believe: the payer, the policy pack and the case id
were all settled before the model read a word, so the demo could never show the step that actually
matters — Attest working out *by itself* whose rules apply to a document it has never seen.

This module holds the two halves of that change:

**Nothing is preloaded.** `app.py` no longer has a path to `attest.corpus`. The only way a case
reaches the screen is a file someone uploads.

**The pack is derived, not chosen.** `find_pack` is called with the payer, plan and CPT the model
extracted, so uploading a PacificSource note and a Highmark note into the same unchanged screen
produces two different policies. And when no pack matches, the review stops rather than proceeding
against criteria we do not have — the same rule `check_pa_required` already follows for UNKNOWN.

The corpus is not gone; it still backs every other gate in this suite. It is simply no longer
wired into the UI. Uploads here read the committed files byte-for-byte, so the cassettes still hit
and this whole module runs offline with no API key.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.paths import data_dir
from attest.policies.loader import find_pack
from conftest import needs_model

pytestmark = pytest.mark.p9_s1

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


def has_button(at: AppTest, label: str) -> bool:
    return any(b.label.startswith(label) for b in at.button)


def upload(at: AppTest, key: str, path: Path) -> AppTest:
    at.get_by_key(key).set_value((path.name, path.read_bytes(), "text/markdown"))
    return at.run()


def upload_note(at: AppTest, name: str) -> AppTest:
    return upload(at, "note_file", CORPUS / "notes" / f"{name}.md")


def body_text(at: AppTest) -> str:
    return "\n".join(el.value for el in at.markdown) + "\n".join(el.value for el in at.caption)


# --------------------------------------------------------------- nothing preloaded


def test_the_app_cannot_reach_the_corpus_at_all():
    """The strongest form of "nothing is preloaded" is that the import is absent.

    Asserted against the source rather than the rendered screen because a corpus import that is
    only *usually* unused would still be one edit away from putting a case back on the rails.
    """
    source = APP_PATH.read_text(encoding="utf-8")
    assert "attest.corpus" not in source
    assert "load_case" not in source
    assert "CASE_NAMES" not in source


def test_the_landing_screen_offers_no_case_to_pick(app):
    """No radio, no selectbox — the only control that starts a review is the uploader."""
    assert not app.exception
    assert not app.radio, [r.label for r in app.radio]
    assert not app.selectbox, [s.label for s in app.selectbox]
    assert app.get_by_key("note_file") is not None


def test_the_landing_screen_hands_a_stranger_a_note_to_try(app):
    """P6-S4 put this app on a public URL for judges.

    A judge has no clinical note on their machine, so an upload-only screen with nothing to upload
    would be untestable by exactly the audience it was deployed for. The samples are offered as
    downloads, never loaded into the pipeline.
    """
    labels = [b.label for b in app.download_button]
    assert any("PacificSource" in label for label in labels), labels
    assert any("Denial letter" in label for label in labels), labels


# ------------------------------------------------------------ the pack is derived


@needs_model
def test_an_uploaded_note_routes_itself_to_its_payers_policy(app):
    """The headline claim: same screen, no configuration, two payers, two policies."""
    at = click(upload_note(app, "clean"), "Run intake")
    assert not at.exception
    assert "PacificSource" in body_text(at)


@needs_model
def test_a_different_payer_routes_to_a_different_policy(app):
    """The other half of the claim. If this passed while the previous one did also, the screen is
    reading the note rather than remembering a setting."""
    at = click(upload_note(app, "denial"), "Run intake")
    assert not at.exception

    text = body_text(at)
    assert "Highmark" in text
    assert "PacificSource" not in text


@needs_model
def test_the_matched_policy_is_named_and_linked_before_any_verdict(app):
    """A verdict is only meaningful next to the rules it was judged against."""
    at = click(upload_note(app, "clean"), "Run intake")

    assert any("Policy matched" in s.value for s in at.success)
    assert "https://" in body_text(at)


def test_the_router_the_app_calls_has_no_answer_for_an_unlisted_payer():
    """The routing decision itself, isolated from the screen.

    `find_pack` returning None is the whole reason the UI has a stopping branch, so it is asserted
    directly rather than inferred from what rendered.
    """
    assert find_pack(cpt="90867", payer="Aetna", plan="Commercial") is None


@needs_model
def test_an_unlisted_payer_stops_the_review_instead_of_guessing(app, monkeypatch):
    """No pack means no criteria — and no criteria must never render as nothing-to-answer.

    Both bindings are patched because `pa_lookup` imported `find_pack` by name at its own import
    time; patching only the loader would leave the screen claiming a policy was found while the
    router said otherwise, which is not a state the app can actually be in.
    """
    monkeypatch.setattr("attest.policies.loader.find_pack", lambda **kwargs: None)
    monkeypatch.setattr("attest.tools.pa_lookup.find_pack", lambda **kwargs: None)

    at = click(upload_note(app, "clean"), "Run intake")
    assert not at.exception

    assert any("No policy on file" in w.value for w in at.warning)
    assert not has_button(at, "Match criteria"), "the review continued without a policy"

    # The intake it already produced is still on screen: the run is stopped, not discarded.
    assert "SYNTH-001" in body_text(at)


# ------------------------------------------------- the denial is its own document


@needs_model
def test_the_appeal_waits_for_a_separately_uploaded_denial(app):
    """A denial arrives days after the note, so it cannot ride along with it."""
    at = click(click(upload_note(app, "denial"), "Run intake"), "Match criteria")
    at.text_input(key="gate1_approver").set_value("Dr. L. Marchetti").run()
    at = click(at, "Approve and generate")
    assert not at.exception

    assert at.get_by_key("denial_file") is not None
    assert not has_button(at, "Draft the appeal"), "an appeal was offered with no denial letter"


@needs_model
def test_uploading_the_denial_letter_unlocks_the_appeal(app):
    at = click(click(upload_note(app, "denial"), "Run intake"), "Match criteria")
    at.text_input(key="gate1_approver").set_value("Dr. L. Marchetti").run()
    at = click(at, "Approve and generate")
    at = upload(at, "denial_file", CORPUS / "denials" / "denial_001.md")
    assert not at.exception

    assert has_button(at, "Draft the appeal")

    at = click(at, "Draft the appeal")
    assert not at.exception
    assert "hho-" in body_text(at)
