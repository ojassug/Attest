"""Gate for P1-S4 — the synthetic corpus and its ground truth.

Two jobs. First, keep real patient data out of the repo: every note must carry a synthetic
banner. Second, make the ground truth *coherent* — it is the standard every later phase is
graded against, so a typo'd criterion id or a gap case with no gap would silently make P3's
gate meaningless rather than fail loudly here.
"""

import pytest

from attest.corpus import CASE_NAMES, DATA_DIR, all_cases, load_case
from attest.models import Verdict

pytestmark = pytest.mark.p1_s4

CASES = all_cases()


def test_all_expected_cases_exist():
    assert [c.name for c in CASES] == list(CASE_NAMES)


@pytest.mark.parametrize("path", sorted(DATA_DIR.rglob("*.md")), ids=lambda p: p.name)
def test_all_notes_carry_synthetic_banner(path):
    """§7 of the product spec: synthetic data only. Enforced, not just promised."""
    head = path.read_text(encoding="utf-8")[:200].upper()
    assert "SYNTHETIC" in head, f"{path.name} lacks a synthetic-data banner"
    assert "NOT REAL PATIENT DATA" in head, f"{path.name} banner is incomplete"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_expected_criterion_ids_exist_in_pack(case):
    """Ground truth may only reference criteria that actually exist in the named pack."""
    pack_ids = set(case.pack.criterion_ids)
    unknown = sorted(set(case.verdicts) - pack_ids)
    assert not unknown, f"{case.name}: verdicts reference unknown criteria {unknown}"

    missing = sorted(pack_ids - set(case.verdicts))
    assert not missing, f"{case.name}: no expected verdict for {missing}"


def test_gap_case_has_at_least_one_unmet():
    """The gap case must actually contain a gap, or P3-S5's gate proves nothing."""
    gap = load_case("gap")
    not_met = [cid for cid, v in gap.verdicts.items() if v is not Verdict.MET]
    assert not_met, "the gap case has no unmet or insufficient criterion"
    assert gap.expected_gaps, "the gap case declares no expected gaps"
    assert set(gap.expected_gaps) <= set(not_met)


def test_clean_case_is_fully_met():
    """The happy path must be unambiguous, or the packet demo has nothing to show."""
    clean = load_case("clean")
    assert all(v is Verdict.MET for v in clean.verdicts.values())
    assert clean.expected_gaps == []


def test_gaps_are_consistent_with_verdicts():
    for case in CASES:
        for cid in case.expected_gaps:
            assert case.verdicts[cid] is not Verdict.MET, (
                f"{case.name}: {cid} is listed as a gap but expected to be met"
            )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_notes_are_readable_and_nonempty(case):
    assert len(case.note_text.split()) > 100, f"{case.name} note is too thin to be realistic"


def test_denial_case_carries_a_denial_letter():
    denial = load_case("denial")
    assert denial.denial_text is not None
    spec = denial.raw["denial"]
    contested = spec["expected_contested"]
    assert contested, "denial case contests nothing"
    assert set(contested) <= set(denial.pack.criterion_ids)
    assert spec["expected_unmapped_reason_count"] >= 1, (
        "the denial must include a reason that maps to no criterion, so P5-S1 can prove such "
        "reasons are surfaced rather than dropped"
    )


def test_denial_case_is_fully_documented():
    """The appeal demo only lands if the note actually satisfies what the payer contests —
    otherwise the payer was right and the rebuttal is dishonest."""
    denial = load_case("denial")
    for cid in denial.raw["denial"]["expected_contested"]:
        assert denial.verdicts[cid] is Verdict.MET, (
            f"{cid} is contested by the payer but ground truth says it is not met"
        )


def test_cases_span_both_payers():
    """Two payers across the corpus, so the specialty-agnostic claim is exercised."""
    assert len({c.pack_id for c in CASES}) == 2


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_intake_matches_the_pack(case):
    """Ground-truth intake must agree with the pack it names, or P2-S1's gate is unfair."""
    assert case.intake["payer"] == case.pack.payer
    assert case.intake["plan"] == case.pack.plan
    assert set(case.intake["cpt_codes"]) <= set(case.pack.cpt_codes)
