"""Gate for P9-S3 — a criterion says what it means.

`Attest-PRODUCT.md` §9 calls criteria matching "the product's core", which "must be the strongest
part of the demo". It was the hardest screen in the app to read, in two separate ways.

**The label was the whole policy text.** Up to 524 characters of payer legalese (`hho-03`), wrapping
to four lines, ten of them stacked in one column, every one collapsed — so the screen showed no
evidence at rest and cost ten clicks to reveal any. The id and the category, which are what a
reviewer scans for, were hidden *inside*.

**And a tick meant opposite things without saying so.** Four of Highmark's ten criteria carry
`polarity: absent`. Rendered from the verdict alone, the screen said

    ✅ hho-05 — Seizure disorder or any history of seizure with increased risk of future seizure

which to anyone who is not a clinician reads as *the patient has a seizure disorder*. It means the
record documents that they do not. The polarity was already loaded, already in the pack, and never
reached the label.

The tests below are deliberately written against every criterion in every pack rather than against
the two TMS packs the demo uses, because the fault was a rendering rule that happened to be wrong
for one polarity — the kind that hides until a pack nobody was looking at ships.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from attest.models import Polarity
from attest.paths import data_dir
from attest.policies.loader import find_pack
from conftest import needs_model

pytestmark = pytest.mark.p9_s3

APP = str(Path(__file__).resolve().parents[1] / "app.py")
CORPUS = data_dir() / "synthetic"

TIMEOUT = 90

# A label has to fit on one line at a glance. The worst case the new format can produce is around
# seventy characters; the format it replaced ran past five hundred.
SCANNABLE = 100


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


def body_text(at: AppTest) -> str:
    return "\n".join(el.value for el in at.markdown) + "\n".join(el.value for el in at.caption)


def matched(at: AppTest, note: str) -> AppTest:
    return click(click(upload_note(at, note), "Run intake"), "Match criteria")


def criterion_labels(at: AppTest, pack) -> dict[str, str]:
    """The expander label rendered for each criterion in `pack`, keyed by criterion id.

    Matched by id rather than by position: the screen carries other expanders — the note, the
    denial letter, the rebuttals — and a positional assumption would quietly start reading one of
    those the first time the layout changed.
    """
    found = {}
    for element in at.expander:
        for criterion in pack.criteria:
            if criterion.id in element.label:
                found[criterion.id] = element.label
    return found


HIGHMARK = find_pack(cpt="90867", payer="Highmark Health Options", plan="Medicaid")


# ------------------------------------------------------------------------- polarity


def test_the_packs_still_contain_the_case_this_gate_exists_for():
    """If no pack has an absent criterion, the polarity tests below assert nothing.

    A guard on the fixture rather than on the product: `needs_model` tests are easy to leave
    passing vacuously when the data underneath them changes.
    """
    assert HIGHMARK is not None, "the Highmark pack is not reachable"
    absent = [c for c in HIGHMARK.criteria if c.polarity is Polarity.ABSENT]
    assert len(absent) >= 4, f"expected contraindications in the Highmark pack, found {absent}"


@needs_model
def test_a_contraindication_that_was_ruled_out_is_not_labelled_met(app):
    """"Met" on a contraindication says the finding is present. It is not, and it must not say so.

    The note documents the absence of every Highmark contraindication, so each lands MET — the
    verdict is right and always was. What is under test is the sentence built from it.
    """
    at = matched(app, "denial")
    assert not at.exception

    labels = criterion_labels(at, HIGHMARK)
    contraindications = [c for c in HIGHMARK.criteria if c.polarity is Polarity.ABSENT]

    for criterion in contraindications:
        label = labels.get(criterion.id)
        assert label, f"{criterion.id} is not on screen; saw {sorted(labels)}"
        assert "Ruled out" in label, (
            f"{criterion.id} is a contraindication the record rules out, and the screen says "
            f"{label!r}"
        )
        assert "— Met" not in label, f"{criterion.id} reads as though the finding were present"

    # And the screen says *why* a tick on a contraindication means what it means, rather than
    # leaving a reader to work it out from the verdict.
    assert "satisfied when the record documents the finding is" in body_text(at)


# ---------------------------------------------------------------------------- labels


@needs_model
def test_no_criterion_label_is_longer_than_a_scannable_line(app):
    """Ten criteria have to be readable as a list, which the policy text made impossible."""
    at = matched(app, "denial")
    assert not at.exception

    labels = criterion_labels(at, HIGHMARK)
    assert len(labels) == len(HIGHMARK.criteria), sorted(labels)

    for criterion_id, label in sorted(labels.items()):
        assert len(label) <= SCANNABLE, (
            f"{criterion_id}'s label is {len(label)} characters: {label!r}"
        )


@needs_model
def test_the_payers_own_wording_is_still_on_screen_for_every_criterion(app):
    """Shortening the label must not lose the policy text — it moves, it does not go.

    Quoting the payer verbatim is the product's argument, not decoration: the appeal cites this
    wording back at them. A label that summarised it would be a paraphrase on the one screen where
    paraphrase is the failure mode being defended against.
    """
    at = matched(app, "denial")
    assert not at.exception

    text = body_text(at)
    for criterion in HIGHMARK.criteria:
        wording = " ".join(criterion.text.split())
        assert wording in " ".join(text.split()), (
            f"{criterion.id}'s policy wording is no longer on screen: {wording[:60]}…"
        )


# ------------------------------------------------------- what must not have changed


@needs_model
def test_every_quote_on_screen_still_carries_the_verifiers_mark(app):
    """P6-S3's standing property, re-asserted against a rewritten criteria block.

    Nothing is shown as fact that the verifier did not confirm. This is the rule most likely to be
    lost to a layout change, because losing it looks like nothing at all.
    """
    at = matched(app, "denial")
    assert not at.exception

    # The note is on screen too, rendered whole, and its own first line is a blockquote — the
    # synthetic-data banner. Excluded by identity rather than by pattern, so this keeps counting
    # only evidence however either one is later reformatted. Compared stripped, because Streamlit
    # drops the file's trailing newline on the way to the element.
    note_text = (CORPUS / "notes" / "denial.md").read_text(encoding="utf-8").strip()
    quotes = [
        m.value
        for m in at.markdown
        if m.value.startswith("> ") and m.value.strip() != note_text
    ]
    assert quotes, "no evidence quotes rendered at all"

    marks = [c.value for c in at.caption if "verified verbatim" in c.value]
    assert len(marks) >= len(quotes), (
        f"{len(quotes)} quotes on screen but only {len(marks)} carry the verifier's mark"
    )
    assert not any("unverified" in c.value for c in at.caption)
