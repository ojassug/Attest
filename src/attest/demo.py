"""Run one case end to end from a terminal, and stop where a clinician has to look.

    python -m attest.demo --case clean
    python -m attest.demo --note path/to/note.md
    python -m attest.demo --list

**Why this exists alongside the console.** `README.md` asks a judge to clone the repo and see it
work, and the rules require a project that "installs and runs consistently". A browser, an upload
dialog and a Streamlit session are a lot of moving parts to stand between a reader and that claim —
and since P9-S1 the console deliberately has no way to reach a committed case, so there was no
longer any path that ran one without a file picker. This is that path: no browser, no key, no
network, deterministic, about ten seconds.

**It stops before Gate 1, for the same reason `agent_runtime.py` does.** It prints the packet and
the content hash a clinician would approve, and writes nothing. `Attest-PRODUCT.md` §6 makes human
approval non-negotiable, and a command-line runner is exactly where that rule would otherwise
quietly become a UI convention. There is no `--approve` flag and there should not be one: approval
is a person reading the assertions, not an argument.

Every model call replays from `cassettes/`, so this needs no credentials. A note that was never
recorded needs a key, and says so rather than failing with an auth error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from attest.corpus import load_case
from attest.criteria.gaps import build_gap_list
from attest.criteria.match import match_all
from attest.gates import content_hash
from attest.llm import have_credentials
from attest.models import Packet, Polarity, Verdict
from attest.packet.justification import build_justification
from attest.policies.loader import find_pack
from attest.verifier import enforce_verification

# `CASE_NAMES` holds only the three TMS cases, so the physical-therapy case cannot leak into tests
# that assume TMS verdicts. A reader at a terminal has no such constraint, and `pt` is the case
# that shows the engine is not TMS-specific, so it is offered here.
CASES = ("clean", "gap", "denial", "pt")

MARK = {Verdict.MET: "[ok]", Verdict.UNMET: "[no]", Verdict.INSUFFICIENT: "[? ]"}

# The console says the same thing in `app.py`'s VERDICT_WORDING, and the two are not shared yet —
# see DECISIONS.md, 2026-09-10. A tick against a contraindication has to read as "ruled out" here
# too, because "met" beside "Seizure disorder" states the inverse of what was found.
WORDING = {
    Polarity.PRESENT: {
        Verdict.MET: "met",
        Verdict.UNMET: "not met",
        Verdict.INSUFFICIENT: "insufficiently documented",
    },
    Polarity.ABSENT: {
        Verdict.MET: "ruled out",
        Verdict.UNMET: "present — contraindicated",
        Verdict.INSUFFICIENT: "not ruled out",
    },
}


def use_utf8_output() -> None:
    """Make stdout able to carry the text this repository actually contains.

    DECISIONS.md already records that every file *read* must name its encoding. This is the same
    rule on the way out, and it is not hypothetical: a Windows console defaults to cp1252, the
    policy packs carry em dashes in `source_title`, and `print` of a character cp1252 cannot encode
    raises `UnicodeEncodeError` — so `python -m attest.demo --case clean > out.txt` died on a
    default Windows shell while working perfectly on macOS and in CI.

    `errors="replace"` rather than strict: a terminal that genuinely cannot render a dash should
    show a question mark, not lose the run. The chrome this module prints is deliberately ASCII, so
    the layout never depends on this working — only the payer's own words do.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def rule(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def run(note_text: str, *, case_id: str, note_id: str) -> int:
    """Assemble a packet and print it. Returns a process exit code."""
    from attest.agents.intake import extract_case

    rule("1 - Reading the note")
    case = extract_case(note_text, case_id=case_id, note_id=note_id)
    print(f"  Patient    {case.patient_ref}")
    print(f"  Service    {case.service.service}")
    print(f"  CPT        {', '.join(case.service.cpt_codes)}")
    print(f"  Diagnosis  {case.primary_diagnosis_code} - {case.primary_diagnosis_text}")
    print(f"  Coverage   {case.insurance.payer} | {case.insurance.plan}")

    pack = find_pack(case.service.cpt_codes[0], case.insurance.payer, case.insurance.plan)
    if pack is None:
        # Same rule as PARequirement.UNKNOWN, one layer up: no pack means we have no criteria to
        # check, which is not the same as passing.
        print(
            f"\n  No policy on file for CPT {case.service.cpt_codes[0]} under "
            f"{case.insurance.payer} ({case.insurance.plan}).\n"
            "  Attest will not guess a payer's criteria, so the review stops here. Confirm the "
            "requirement with the payer directly.",
            file=sys.stderr,
        )
        return 2

    print(f"\n  Policy matched - {pack.payer} | {pack.plan}")
    print(f"  {pack.source_title}")
    print(f"  {pack.source_url}  (retrieved {pack.retrieved_date})")

    rule("2 - Checking the record against the payer's criteria")
    verified = enforce_verification(
        match_all(pack, note_text, case_id=case.case_id, note_id=note_id), note_text
    )
    coverage = verified.coverage
    by_id = {c.id: c for c in pack.criteria}

    for verdict in coverage.verdicts:
        criterion = by_id[verdict.criterion_id]
        wording = WORDING[criterion.polarity][verdict.verdict]
        print(f"  {MARK[verdict.verdict]} {criterion.id:<8} {criterion.category:<26} {wording}")

    spans = [s for v in coverage.verdicts for s in v.spans]
    met = sum(1 for v in coverage.verdicts if v.verdict is Verdict.MET)
    print(f"\n  {met}/{len(coverage.verdicts)} criteria satisfied")
    print(f"  {sum(1 for s in spans if s.verified)}/{len(spans)} evidence quotes verified verbatim")
    if verified.report.rejected:
        print(
            f"  {len(verified.report.rejected)} quote(s) could not be found in the note and were "
            "removed; their criteria were downgraded."
        )

    rule("3 - What the practice still needs to supply")
    gaps = build_gap_list(coverage)
    if gaps:
        for gap in gaps:
            print(f"  {gap.criterion_id} - {gap.missing}")
            print(f"    {gap.question}")
    else:
        print("  Nothing outstanding. Every criterion is documented.")

    packet = Packet(
        case_id=case.case_id,
        coverage=coverage,
        justification=build_justification(coverage, case),
        gaps=gaps,
    )

    rule("4 - Medical-necessity justification")
    print(f"  {len(packet.justification.claims)} claims, each citing only verified spans.")
    for claim in packet.justification.claims:
        print(f"  - {' '.join(claim.text.split())[:110]}...")
        print(f"      {', '.join(claim.supporting_span_ids)}")

    rule("Gate 1 - stopping here")
    print(f"  content hash  {content_hash(packet)}")
    print(
        "  Nothing has been written. A named clinician must approve this exact content before any\n"
        "  submission artifact exists — run the console (`streamlit run app.py`) to do that, or\n"
        "  call attest.packet.emit.emit_submission_artifact with an ApprovalRecord."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()
    parser = argparse.ArgumentParser(
        prog="python -m attest.demo",
        description="Run one prior-authorization case end to end and stop at Gate 1.",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--case", choices=CASES, help="one of the committed synthetic cases")
    source.add_argument("--note", type=Path, help="a clinical note to read instead")
    parser.add_argument("--list", action="store_true", help="list the synthetic cases and exit")
    args = parser.parse_args(argv)

    if args.list or (args.case is None and args.note is None):
        print("Synthetic cases (all fabricated — no real patient data):")
        for name in CASES:
            print(f"  --case {name}")
        print("\nOr read your own note:  --note path/to/note.md")
        return 0

    if args.note is not None:
        if not args.note.is_file():
            print(f"no such file: {args.note}", file=sys.stderr)
            return 2
        # Newlines are normalised for the same reason `app.py` normalises an upload: every
        # cassette was keyed against text that came through universal-newline handling, and a
        # CRLF copy is a different string. See DECISIONS.md, 2026-09-10.
        note_text = args.note.read_text(encoding="utf-8")
        case_id, note_id = "DEMO-001", args.note.name
    else:
        case = load_case(args.case)
        note_text, case_id, note_id = case.note_text, case.case_id, args.case

    print("SYNTHETIC DATA ONLY - every note in this repository is fabricated.")

    try:
        return run(note_text, case_id=case_id, note_id=note_id)
    except Exception as exc:  # noqa: BLE001 - a CLI boundary, same reason as the console's
        if not have_credentials():
            print(
                f"\nThis note is not one of the recorded ones, so reading it needs a model.\n"
                f"Attest replays committed responses from cassettes/ so the demo costs nothing and\n"
                f"needs no key — but a note that was never recorded has nothing to replay.\n"
                f"Try `python -m attest.demo --case clean`, or set GOOGLE_API_KEY (see docs/setup.md).\n"
                f"\n  underlying error: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        else:
            print(f"\n{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
