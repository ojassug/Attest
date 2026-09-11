"""Gate for P9-S2 — the console survives a note it has never seen.

Two failures, one shape: a Python traceback rendered inside the page, which is the first entry
under *Fail conditions* in `docs/ui-checklist.md`.

**Line endings.** Every reader in this codebase except one goes through `Path.read_text`, whose
universal-newline handling collapses `\\r\\n` to `\\n` before anything sees it — so that is the
text the cassettes were recorded against. `read_upload` is the exception: an upload arrives as raw
bytes. With `.gitattributes` pinning only `*.sh`, a Markdown note checked out on Windows reached
the pipeline as a *different string* — 2424 characters where the recorded one is 2371 — which
missed the cassette, made a live call, and failed with no key. `verify.sh ALL --offline` failed 13
tests on Windows and passed on Linux, which is the worst shape a bug can take on a project that
alternates machines. Fixed at both ends: the attribute fixes the checkout, `read_upload` fixes the
upload, and only the second survives a judge re-saving a downloaded note in an editor.

**Everything else.** `app.py` caught `MissingFactError` and nothing else, so any other failure
reached the page. P9-S1 made that far more likely rather than less: an open uploader is an
invitation to try your own note, and the public deploy has no key to answer one with. `guarded`
now stands between every engine call and the screen.

The tests below drive the real screen through `AppTest` rather than calling helpers, because the
property under test is what a person sees, not what a function returns.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.paths import data_dir
from conftest import needs_model

pytestmark = pytest.mark.p9_s2

APP = str(Path(__file__).resolve().parents[1] / "app.py")
CORPUS = data_dir() / "synthetic"

TIMEOUT = 90


@pytest.fixture
def new_app(tmp_path, monkeypatch):
    """A factory, because one test needs two screens that have never seen each other."""
    monkeypatch.setenv("ATTEST_STORE_DIR", str(tmp_path / "sessions"))
    monkeypatch.setenv("ATTEST_OUT_DIR", str(tmp_path / "out"))

    def make() -> AppTest:
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


def upload_bytes(at: AppTest, name: str, payload: bytes) -> AppTest:
    at.get_by_key("note_file").set_value((name, payload, "text/markdown"))
    return at.run()


def body_text(at: AppTest) -> str:
    return "\n".join(el.value for el in at.markdown) + "\n".join(el.value for el in at.caption)


def offered_samples() -> list[Path]:
    """Every file the landing screen hands a visitor, notes and the denial letter alike."""
    return sorted(CORPUS.glob("notes/*.md")) + sorted(CORPUS.glob("denials/*.md"))


# ------------------------------------------------------------------- line endings


@needs_model
def test_a_crlf_upload_decodes_to_the_same_text_as_the_committed_note(new_app):
    """The same note, uploaded twice with different line endings, is one note.

    Asserted three ways, weakest first. The captions match, so the same character count reached the
    screen. Intake reaches PacificSource, so that string hit the cassette rather than a live API —
    which is the failure this step exists to remove.

    The third is the strongest and needs no comparison at all. Scratch space is keyed by a hash of
    the note text (`note_key`), so uploading the CRLF copy into a session that already read the LF
    copy *continues that review* instead of offering **Run intake** again. Two strings that hash
    alike are the same string; the screen proves the property rather than being asked about it.
    """
    lf = (CORPUS / "notes" / "clean.md").read_bytes().replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    assert crlf != lf, "the fixture is not exercising anything"

    from_lf = click(upload_bytes(new_app(), "clean.md", lf), "Run intake")
    from_crlf = click(upload_bytes(new_app(), "clean.md", crlf), "Run intake")

    reading_lf = [c.value for c in from_lf.caption if "Reading" in c.value]
    reading_crlf = [c.value for c in from_crlf.caption if "Reading" in c.value]
    assert reading_crlf == reading_lf and len(reading_crlf) > 0
    assert "PacificSource" in body_text(from_crlf)

    continued = upload_bytes(from_lf, "clean.md", crlf)
    assert not any(b.label.startswith("Run intake") for b in continued.button), (
        "the CRLF copy started a second review, so it is not the same note text"
    )


def test_the_offered_sample_downloads_round_trip_through_the_uploader():
    """What the screen hands out must decode to what the pipeline recorded.

    A download hands over bytes and an upload hands them back, with no universal-newline
    translation anywhere in between — so for every sample the landing screen offers, the decoded
    bytes have to equal what `Path.read_text` gives. They do not on a checkout that smudges
    Markdown to CRLF, which is exactly the state this gate exists to refuse.

    Needs no model and no key: it is a property of the committed files and the checkout that
    produced them, which is why it is the test that fails first on a mis-configured clone.
    """
    samples = offered_samples()
    assert samples, f"no synthetic corpus under {CORPUS}"

    for path in samples:
        assert path.read_bytes().decode("utf-8") == path.read_text(encoding="utf-8"), (
            f"{path.name} carries CRLF in the working tree, so uploading it produces a different "
            "string than every other reader sees — a cassette miss and a live API call. Check "
            "that .gitattributes pins *.md to eol=lf and re-checkout."
        )


# ------------------------------------------------------------- nothing reaches the page


@needs_model
def test_a_note_the_cassettes_do_not_have_explains_itself_instead_of_raising(app, monkeypatch):
    """The uploader invites a note nobody recorded. That has to be a sentence, not a stack trace.

    `api_key` is patched to find nothing, which is both the deployed configuration and the only
    way to make this deterministic — on a machine that has a key, an unrecorded note would
    otherwise spend real quota proving the point.
    """
    monkeypatch.setattr("attest.llm.api_key", lambda: None)

    unrecorded = b"# Note\n\nPayer: Nobody. Nothing here was ever recorded.\n"
    at = click(upload_bytes(app, "mine.md", unrecorded), "Run intake")

    assert not at.exception, "an unrecorded note reached the page as a traceback"
    assert any("not one of the recorded ones" in w.value for w in at.warning), [
        w.value for w in at.warning
    ]
    # Saying what went wrong without offering something that works is half an answer.
    assert any("Download" in e.label for e in at.expander)


@needs_model
def test_a_storage_failure_does_not_reach_the_page(app, monkeypatch):
    """Storage is the other way a traceback got in, and it is not hypothetical.

    A deployed console writes to an ephemeral filesystem, and this exact failure was reproduced by
    pointing `ATTEST_STORE_DIR` at a path Windows would not accept. The run stops — the case is not
    silently treated as filed — but it stops in words.
    """

    def refuse(*args, **kwargs):
        raise OSError("disk is not writable")

    monkeypatch.setattr("attest.store.save_case", refuse)

    note = (CORPUS / "notes" / "clean.md").read_bytes().replace(b"\r\n", b"\n")
    at = click(upload_bytes(app, "clean.md", note), "Run intake")

    assert not at.exception, "a storage failure reached the page as a traceback"
    assert any("Filing the case" in e.value for e in at.error), [e.value for e in at.error]
    assert any("disk is not writable" in e.value for e in at.error)
