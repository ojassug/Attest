"""Gate for P7-S2 — the physical-therapy extensibility pack.

The README claims the engine is specialty-agnostic and that adding a specialty costs a pack, not a
rewrite. That is the kind of claim that is true right up until someone checks, so this module
checks it: a different specialty, a different payer, a different plan type, running through the
same code as TMS with nothing added for it.

**Why physical therapy is the honest test rather than a convenient one.** DECISIONS.md picked TMS
precisely because its criteria are near-binary, and named PT's central requirement — "meaningful
functional progress" — as fuzzier and easier to fake convincingly. `pt-06` is that requirement.
Nothing in the note says "the member demonstrated meaningful functional progress" as a bare
assertion the matcher could keyword-match and wave through; the evidence is a table of objective
measures across four re-assessments, and a correct MET verdict means the matcher read improvement
out of numbers.

**Three criteria are exclusions** (`polarity: absent`) — maintenance-only care, duplicative
therapists, no measurable improvement after 4–6 visits. A well-documented member has to read as
*satisfying* them. Without polarity every thorough note would fail every exclusion, which is the
bug `Criterion.polarity` was added in P1-S3 to prevent, now exercised on a second specialty.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from attest.corpus import CASE_NAMES, load_case
from attest.criteria.gaps import build_gap_list
from attest.criteria.match import match_all
from attest.models import Polarity, Verdict
from attest.packet.justification import build_justification
from attest.policies.loader import PACKS_DIR, load_pack
from attest.verifier import enforce_verification
from conftest import needs_model

pytestmark = pytest.mark.p7_s2

CASE = load_case("pt")
PACK = CASE.pack

SRC = Path(__file__).resolve().parents[1] / "src" / "attest"


# ------------------------------------------------------------------ the pack is data


def test_pt_case_runs_with_zero_code_changes():
    """No module under src/attest names a specialty. A specialty is a pack plus a note.

    This is the assertion the extensibility claim actually rests on. If any of these words had to
    appear in engine code for the PT case to work, adding a specialty would cost a rewrite and the
    README would be wrong.
    """
    specialty_words = (
        "tms",
        "transcranial",
        "physical therapy",
        "physical_therapy",
        "depression",
        "antidepressant",
        "arthroplasty",
        "psychiatr",
    )

    offenders = []
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))

        # Docstrings are prose and may name a specialty as an example - several do, deliberately.
        # Comments never reach the AST at all. What is left is executable code: identifiers and
        # the string literals the program actually operates on.
        docstrings = {
            ast.get_docstring(node, clean=False)
            for node in ast.walk(tree)
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            )
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in docstrings:
                    continue
                haystack = node.value.lower()
            elif isinstance(node, ast.Name):
                haystack = node.id.lower()
            elif isinstance(node, ast.Attribute):
                haystack = node.attr.lower()
            else:
                continue

            for word in specialty_words:
                if word in haystack:
                    offenders.append(f"{path.relative_to(SRC)}:{node.lineno} {word!r}")

    assert not offenders, (
        "engine code names a specialty, so adding one would cost a code change: "
        f"{sorted(set(offenders))}"
    )


def test_the_pt_pack_is_a_third_specialty_not_a_third_tms_pack():
    """A second TMS pack would prove nothing about generality."""
    assert PACK.pack_id == "vnshealth-medicare-pt"
    assert not {"90867", "90868", "90869"} & set(PACK.cpt_codes)
    assert PACK.payer not in {"PacificSource", "Highmark Health Options"}
    assert PACK.plan == "Medicare Advantage"


def test_the_pt_pack_meets_every_universal_pack_rule():
    """The new pack is held to P1-S2's and P1-S3's standards, not exempted from them."""
    pack = load_pack(PACKS_DIR / "vnshealth-medicare-pt.yaml")

    assert len(pack.criteria) >= 8
    assert pack.source_url.scheme == "https"
    assert pack.appeal_window_source.strip(), "an invented appeal deadline is worse than none"
    for c in pack.criteria:
        assert c.text.strip() and c.category.strip() and c.source_section.strip()
    assert len({c.id for c in pack.criteria}) == len(pack.criteria)


def test_the_exclusions_are_marked_absent():
    """A well-documented member must satisfy an exclusion, not fail it."""
    exclusions = [c for c in PACK.criteria if c.category == "exclusion"]
    assert len(exclusions) == 3
    assert all(c.polarity is Polarity.ABSENT for c in exclusions)


def test_the_pt_case_is_not_in_the_tms_corpus():
    """`all_cases()` stays the three TMS cases, so the PT case cannot leak into tests that
    assume TMS verdicts."""
    assert "pt" not in CASE_NAMES


def test_the_pt_note_carries_the_synthetic_banner():
    assert CASE.note_text.lstrip().startswith("> **SYNTHETIC")


def test_every_expected_criterion_id_exists_in_the_pack():
    """Ground truth that names a criterion the pack does not have is unfalsifiable."""
    assert set(CASE.verdicts) == {c.id for c in PACK.criteria}


# ------------------------------------------------------------------ it actually works


@needs_model
def test_pt_verdicts_match_ground_truth():
    """The engine, unchanged, produces the committed verdicts for a specialty it has never seen."""
    coverage = enforce_verification(
        match_all(PACK, CASE.note_text, case_id=CASE.case_id, note_id=CASE.case_id),
        CASE.note_text,
    ).coverage

    actual = {v.criterion_id: v.verdict for v in coverage.verdicts}
    assert actual == CASE.verdicts

    assert [g.criterion_id for g in build_gap_list(coverage)] == CASE.expected_gaps


@needs_model
def test_pt_evidence_verifies_verbatim():
    """The anti-hallucination guarantee is not specialty-specific either.

    A PT note is dense with numbers - degrees, MMT grades, Berg scores - and a paraphrase that
    shifts one of them is the failure mode that matters most here.
    """
    verified = enforce_verification(
        match_all(PACK, CASE.note_text, case_id=CASE.case_id, note_id=CASE.case_id),
        CASE.note_text,
    )

    spans = [s for v in verified.coverage.verdicts for s in v.spans]
    assert spans, "no evidence was quoted at all"
    assert all(s.verified for s in spans)
    assert not verified.report.rejected


@needs_model
def test_the_functional_progress_criterion_is_judged_from_the_measurements():
    """`pt-06` is the criterion PT was chosen to test: a judgement, not a threshold.

    The note never asserts progress without evidence - it tabulates four re-assessments. A MET
    verdict here means the matcher read improvement out of the numbers, and the evidence it cites
    has to come from that record rather than from the summary sentence alone.
    """
    coverage = enforce_verification(
        match_all(PACK, CASE.note_text, case_id=CASE.case_id, note_id=CASE.case_id),
        CASE.note_text,
    ).coverage

    verdict = next(v for v in coverage.verdicts if v.criterion_id == "pt-06")
    assert verdict.verdict is Verdict.MET
    assert verdict.spans, "pt-06 was decided with no evidence at all"
    assert all(s.verified for s in verdict.spans)


@needs_model
def test_the_progress_criterion_fails_when_the_measurements_are_removed():
    """The discriminating test, and the reason the one above is not enough.

    Every criterion in the PT ground truth is MET, so a matcher that simply agreed with everything
    would pass it. Here the objective-measures table and the improvement summary are stripped out,
    leaving a note that still *claims* the member is progressing but no longer evidences it. A
    correct engine must stop saying MET.

    This is precisely the risk DECISIONS.md named when it chose TMS over PT: "documented functional
    progress" is fuzzy and easy to fake convincingly. If the matcher rubber-stamps the claim, the
    extensibility demo is hollow.
    """
    # Built by truncation rather than surgery. The real note quotes current measurements in three
    # places - the progress table, the summary, and the continuation justification - so editing
    # one out leaves the others behind and the test stops meaning what it says. Keeping everything
    # up to the progress section and substituting a bare claim is unambiguous: the note now
    # asserts progress and evidences none.
    head, _, _ = CASE.note_text.partition("## Progress to date")
    note = head + (
        "## Progress to date - 12 visits completed\n\n"
        "The member is progressing well and continues to improve. Continued skilled therapy is\n"
        "requested beyond 12 visits, up to a total of 24 visits.\n"
    )

    for leaked in ("47 / 56", "111 degrees", "meaningful functional progress"):
        assert leaked not in note, f"the progress evidence survived truncation: {leaked!r}"
    assert "Berg Balance Scale | 34 / 56" in note, "the baseline should remain - only the change is gone"

    coverage = enforce_verification(
        match_all(PACK, note, case_id="SYNTH-004-STRIPPED", note_id="SYNTH-004-STRIPPED"), note
    ).coverage

    verdict = next(v for v in coverage.verdicts if v.criterion_id == "pt-06")
    assert verdict.verdict is not Verdict.MET, (
        "pt-06 was reported MET on a note that asserts progress but documents none - the matcher "
        "is accepting the claim instead of the evidence"
    )


@needs_model
def test_a_pt_justification_is_built_from_verified_evidence_only():
    """The packet builder is specialty-agnostic too, all the way to a submittable document."""
    from attest.agents.orchestrator import Run, do_criteria, do_intake, do_packet

    run = Run(case_id=CASE.case_id, note=CASE.note_text, pack=PACK)
    do_intake(run)
    do_criteria(run)
    do_packet(run)

    assert run.packet is not None
    justification = build_justification(run.coverage, run.case)
    assert justification.claims

    verified_ids = {s.span_id for v in run.coverage.verdicts for s in v.spans if s.verified}
    for claim in justification.claims:
        assert claim.supporting_span_ids
        assert set(claim.supporting_span_ids) <= verified_ids
