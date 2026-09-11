"""Gate for P9-S12 — the sidebar's case list says something.

**This module is incomplete on purpose, and P9-S12 is NOT done.** Two of its DoD items are
screen-level and are being built elsewhere: each entry under **Open cases** carrying its payer, and
**Reset this case** not rendering before a note has been uploaded. Neither
`test_the_landing_screen_offers_nothing_to_reset` nor the sidebar half of
`test_a_case_the_store_cannot_read_does_not_take_the_sidebar_down` exists yet. Do not read a green
`verify.sh P9-S12` as a finished step — check the DoD in `PLAN.md`.

What is here is the store half, landed early because it removes a trap rather than adding a
feature. `test_p9_s1.py::test_the_app_cannot_reach_the_corpus_at_all` bans the bare substring
`load_case` in `app.py`, to stop a preloaded corpus case returning under an alias. But
`attest.store.load_case` is the obvious way to render a payer beside a stored case id — so the
obvious implementation of this step takes the **P9-S1** gate red, and the failure names a test
about the corpus. `list_case_summaries` is the way through, and it exists now so that whoever
builds the sidebar never meets the trap. See `DECISIONS.md`, 2026-09-11.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from attest.models import Case, InsuranceInfo, ServiceRequest
from attest.store import list_case_summaries, save_case

pytestmark = pytest.mark.p9_s12


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
    return tmp_path / "sessions"


def test_a_stored_case_is_listed_with_its_payer(store):
    """`SYNTH-001` alone is not a case list. The payer is the field that makes it one."""
    save_case(a_case("SYNTH-001", "PacificSource"))
    save_case(a_case("SYNTH-003", "Highmark Health Options"))

    summaries = list_case_summaries()

    assert [s.case_id for s in summaries] == ["SYNTH-001", "SYNTH-003"], "not sorted by case id"
    assert [s.payer for s in summaries] == ["PacificSource", "Highmark Health Options"]
    assert all(s.service for s in summaries), "a listing with no service names nothing useful"


def test_a_damaged_case_does_not_hide_the_healthy_ones(store):
    """This runs on every render, including the landing screen, so it may not fail loudly.

    `load_case` raises on a snapshot that no longer satisfies `Case` — correctly, because anyone
    asking about *that* case must not get a half-populated record. But a listing is a different
    question, and one corrupted record must not be able to empty a practice's case list. The
    damaged case is skipped; every other case still appears.
    """
    save_case(a_case("SYNTH-001", "PacificSource"))
    save_case(a_case("SYNTH-003", "Highmark Health Options"))

    damaged = [p for p in store.rglob("*.json") if "SYNTH-001" in str(p)]
    assert damaged, "the fixture did not write the snapshot this test damages"
    for path in damaged:
        path.write_text(
            json.dumps({"agent_id": "x", "state": {"attest_case": {"not": "a case"}}}),
            encoding="utf-8",
        )

    summaries = list_case_summaries()

    assert [s.case_id for s in summaries] == ["SYNTH-003"]
