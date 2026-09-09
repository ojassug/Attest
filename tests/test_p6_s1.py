"""Gate for P6-S1 — the case store.

A prior authorization stays open for weeks. The two tests the Definition of Done names both guard
that fact rather than the API surface:

**Surviving a process restart** is checked across two real subprocesses, not by clearing a cache in
this one. An in-memory store passes every single-process round-trip test ever written; only a
second interpreter can tell durability from a dictionary that happened to still be there.

**One case, one session id** is the partitioning that stands in for a lock. Strands' session
managers are not thread-safe and take no distributed lock, so nothing may share a session. The
sharp edge is not the happy path but the repair that looks helpful: a store that sanitises
`SYNTH/001` into `SYNTH-001` silently serves one patient's case for another's.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone

import pytest
from strands import Agent
from strands.session import SnapshotSessionManager
from strands.storage import LocalFileStorage

from attest.models import Case, InsuranceInfo, ServiceRequest
from attest.store import (
    AGENT_ID,
    CaseIdError,
    list_cases,
    load_case,
    save_case,
    session_id_for,
)

pytestmark = pytest.mark.p6_s1


def make_case(case_id: str = "SYNTH-001") -> Case:
    return Case(
        case_id=case_id,
        note_id="note-1",
        patient_ref="SYNTH-PATIENT-A",
        insurance=InsuranceInfo(payer="PacificSource", plan="Commercial", member_id="M-1"),
        service=ServiceRequest(service="TMS", cpt_codes=["90867", "90868"], duration_weeks=6),
        primary_diagnosis_code="F33.2",
        primary_diagnosis_text="Major depressive disorder, recurrent, severe",
        created_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )


# --------------------------------------------------------------- the two DoD tests


def test_case_survives_process_restart(tmp_path):
    """Write in one interpreter, read in another. Nothing is shared but the directory."""
    case = make_case()
    store = str(tmp_path)

    write = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json,sys;from attest.models import Case;from attest.store import save_case;"
            "save_case(Case.model_validate(json.loads(sys.argv[1])), sys.argv[2])",
            case.model_dump_json(),
            store,
        ],
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0, write.stderr

    read = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys;from attest.store import load_case;"
            "c = load_case(sys.argv[1], sys.argv[2]);"
            "sys.stdout.write(c.model_dump_json())",
            case.case_id,
            store,
        ],
        capture_output=True,
        text=True,
    )
    assert read.returncode == 0, read.stderr

    # Identical, not merely present: a store that drops a field is worse than one that loses the
    # case, because the loss is invisible until a document is built from the gap.
    assert Case.model_validate(json.loads(read.stdout)) == case


def test_one_session_id_per_case():
    """The mapping is deterministic, one-to-one, and refuses what it cannot represent."""
    assert session_id_for("SYNTH-001") == session_id_for("SYNTH-001")
    assert session_id_for("SYNTH-001") != session_id_for("SYNTH-002")

    ids = ["SYNTH-001", "SYNTH-002", "SYNTH-003"]
    assert len({session_id_for(i) for i in ids}) == len(ids)

    # The failure this guards is a collision, so the ids that would collide under sanitisation are
    # refused instead. `SYNTH/001` must never become `SYNTH-001` and overwrite it.
    for bad in ("SYNTH/001", "SYNTH\\001", "", "   ", ".", "..", " SYNTH-001", "SYNTH-001 "):
        with pytest.raises(CaseIdError):
            session_id_for(bad)


# ------------------------------------------------------------------- round-tripping


def test_unknown_case_reads_as_none(tmp_path):
    assert load_case("SYNTH-404", tmp_path) is None


def test_saving_twice_updates_the_same_case(tmp_path):
    """A case is edited over its life. The second save must replace, not accumulate."""
    save_case(make_case(), tmp_path)

    updated = make_case().model_copy(update={"primary_diagnosis_text": "Corrected diagnosis"})
    save_case(updated, tmp_path)

    assert load_case("SYNTH-001", tmp_path) == updated
    assert list_cases(tmp_path) == ["SYNTH-001"]


def test_cases_do_not_leak_into_each_other(tmp_path):
    """The partitioning claim, checked rather than assumed."""
    a, b = make_case("SYNTH-001"), make_case("SYNTH-002")
    save_case(a, tmp_path)
    save_case(b, tmp_path)

    assert load_case("SYNTH-001", tmp_path) == a
    assert load_case("SYNTH-002", tmp_path) == b


def test_saved_cases_are_listed(tmp_path):
    """Also pins the one place this module reads Strands' session key layout.

    If a Strands upgrade changes that layout, this fails — rather than `list_cases` quietly
    reporting that the practice has no open cases.
    """
    assert list_cases(tmp_path) == []

    save_case(make_case("SYNTH-002"), tmp_path)
    save_case(make_case("SYNTH-001"), tmp_path)

    assert list_cases(tmp_path) == ["SYNTH-001", "SYNTH-002"]


# ------------------------------------------------------------------------ integrity


def test_a_misfiled_case_is_refused_not_served(tmp_path):
    """A snapshot holding a different case than its session id claims must not be returned.

    Only reachable by writing to the store out of band, which is exactly when a store that
    answers anyway hands one patient's record over for another's.
    """
    manager = SnapshotSessionManager(
        session_id_for("SYNTH-001"), storage=LocalFileStorage(base_dir=str(tmp_path))
    )
    agent = Agent(agent_id=AGENT_ID, state={"case": make_case("SYNTH-999").model_dump(mode="json")})
    asyncio.run(manager.save_snapshot(agent, is_latest=True))

    with pytest.raises(ValueError, match="SYNTH-999"):
        load_case("SYNTH-001", tmp_path)


def test_a_foreign_session_is_refused_not_served(tmp_path):
    """A session written by something other than attest.store holds no case, and says so."""
    manager = SnapshotSessionManager(
        session_id_for("SYNTH-001"), storage=LocalFileStorage(base_dir=str(tmp_path))
    )
    asyncio.run(manager.save_snapshot(Agent(agent_id=AGENT_ID), is_latest=True))

    with pytest.raises(ValueError, match="state key"):
        load_case("SYNTH-001", tmp_path)


def test_the_store_directory_is_read_per_call(tmp_path, monkeypatch):
    """`$ATTEST_STORE_DIR` must be honoured even when set after this module was imported.

    Found in P6-S3: the directory was a module-level constant bound at import, so the UI tests set
    the variable too late and the app wrote cases into the repo instead of a scratch directory. It
    failed silently — the data went somewhere real, just not where it was asked to. A hosted deploy
    redirecting the store would have missed in the same way.
    """
    monkeypatch.setenv("ATTEST_STORE_DIR", str(tmp_path / "redirected"))

    case = make_case()
    save_case(case)  # no explicit directory — must follow the environment

    assert (tmp_path / "redirected").exists()
    assert load_case(case.case_id) == case
    assert list_cases() == [case.case_id]


def test_store_needs_no_credentials(tmp_path, monkeypatch):
    """The store must work in a keyless clone.

    It builds a Strands `Agent` purely as a persistence vehicle — never invoked, no prompt, no
    request — so no provider credential should ever be consulted. A judge cloning the repo with no
    `.env` has to be able to open a case.
    """
    for var in ("GOOGLE_API_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE"):
        monkeypatch.delenv(var, raising=False)

    case = make_case()
    save_case(case, tmp_path)
    assert load_case(case.case_id, tmp_path) == case
