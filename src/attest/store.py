"""Durable case storage, one Strands session per case.

A prior authorization is not a single request-response; it is a case that stays open for weeks —
submitted, denied, appealed, tracked against a filing deadline. That outlives any process, so the
case has to survive one.

**One case, one session id, never shared.** Strands' session managers are documented as not
thread-safe and take no distributed lock. Two cases sharing a session would race; the fix is not
locking but partitioning, so the session id is derived from the case id and nothing else.

**An unusable case id is refused, never repaired.** `session_id_for` rejects anything that is not
already a clean identifier rather than slugifying it. Sanitising looks friendlier and is far more
dangerous here: `SYNTH/001` and `SYNTH-001` would both flatten to one session, and the second case
saved would silently overwrite the first — one patient's record served for another's. A refusal is
recoverable, a collision is not, and the whole point of one-session-per-case is that two cases can
never land in the same place.

**The `Agent` in here is a persistence vehicle, not a reasoning agent.** `SnapshotSessionManager`
captures and restores agents, so a case is carried as agent state through that machinery. The agent
is never invoked, never sends a prompt, and needs no credentials — verified by
`test_store_needs_no_credentials`, which matters because this module has to work in a keyless clone.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from strands import Agent
from strands.session import SnapshotSessionManager
from strands.storage import LocalFileStorage

from attest.models import Appeal, Case

# `sessions/` is gitignored: stored cases are runtime state, never committed. Synthetic though the
# corpus is, a case store that lands in version control is the wrong habit to build into a product
# that will one day hold PHI.
STORE_DIR = Path("sessions")

# One agent per session, so its id is fixed. Pinned rather than left to Strands' default: the id is
# part of the storage key, and a changed default would orphan every stored case silently.
AGENT_ID = "attest-case"

# Namespaces our sessions inside the storage directory, and makes the mapping invertible so
# `list_cases` can read the case ids back off the keys.
SESSION_PREFIX = "case-"

# Where each record sits in the session's agent state. A case and its appeal share one session,
# because they are one case: partitioning is per case, and an appeal filed against a different
# session would be an appeal about a patient the session does not hold.
STATE_KEY = "case"
APPEAL_KEY = "appeal"


class CaseIdError(ValueError):
    """A case id that cannot be used as a session id. Raised rather than repaired."""


def session_id_for(case_id: str) -> str:
    """The one session id this case may ever use.

    Deterministic and one-to-one: the same case id always returns the same session id, and two
    different case ids can never return the same one.
    """
    if not case_id or not case_id.strip():
        raise CaseIdError("case_id may not be empty or whitespace-only")

    # These are the characters that would either break out of the session's storage prefix or
    # collapse two case ids into one. Refusing is the whole contract of this function; see the
    # module docstring for why repairing them would be worse.
    if case_id != case_id.strip() or any(c in case_id for c in "/\\") or case_id in (".", ".."):
        raise CaseIdError(
            f"case_id {case_id!r} is not usable as a session id. It must not contain a path "
            "separator, be a relative-path segment, or carry leading/trailing whitespace. "
            "Attest refuses to rewrite it: two case ids that differ only in those characters "
            "would collapse onto one session and silently overwrite each other's records."
        )

    return f"{SESSION_PREFIX}{case_id}"


def _storage(store_dir: Path | str) -> LocalFileStorage:
    return LocalFileStorage(base_dir=str(store_dir))


def _manager(case_id: str, store_dir: Path | str) -> SnapshotSessionManager:
    return SnapshotSessionManager(session_id_for(case_id), storage=_storage(store_dir))


def _read_state(case_id: str, store_dir: Path | str) -> dict | None:
    """The session's whole state dict, or `None` if the session has never been written."""
    manager = _manager(case_id, store_dir)

    # Deliberately constructed without `session_manager=`. Passing it restores implicitly and
    # returns nothing, so there would be no way to tell "never saved" from "saved and empty".
    agent = Agent(agent_id=AGENT_ID)

    if not asyncio.run(manager.restore_snapshot(agent)):
        return None
    return dict(agent.state.get())


def _write_state(case_id: str, store_dir: Path | str, state: dict) -> str:
    """Replace the session's state. Returns the session id written to."""
    manager = _manager(case_id, store_dir)
    agent = Agent(agent_id=AGENT_ID, state=state)
    asyncio.run(manager.save_snapshot(agent, is_latest=True))
    return manager.session_id


def save_case(case: Case, store_dir: Path | str = STORE_DIR) -> str:
    """Persist a case, overwriting any earlier version of that same case.

    Read-modify-write, so re-saving an edited case does not discard the appeal stored beside it.
    Returns the session id it was written under, so a caller can log or display where a case
    actually lives rather than reconstructing the mapping itself.
    """
    state = _read_state(case.case_id, store_dir) or {}
    state[STATE_KEY] = case.model_dump(mode="json")
    return _write_state(case.case_id, store_dir, state)


def save_appeal(appeal: Appeal, store_dir: Path | str = STORE_DIR) -> str:
    """Persist an appeal alongside the case it argues.

    Raises if that case is not in the store. An appeal filed against a case that does not exist is
    an orphan: `find_precedents` would offer its language as precedent with no case behind it, and
    nothing downstream could answer "which patient was this?".
    """
    state = _read_state(appeal.case_id, store_dir)
    if state is None or STATE_KEY not in state:
        raise ValueError(
            f"appeal {appeal.appeal_id!r}: case {appeal.case_id!r} is not in the store. Save the "
            "case before the appeal that argues it."
        )

    state[APPEAL_KEY] = appeal.model_dump(mode="json")
    return _write_state(appeal.case_id, store_dir, state)


def load_case(case_id: str, store_dir: Path | str = STORE_DIR) -> Case | None:
    """Return the stored case, or `None` if this case has never been saved.

    `None` means "no such case", which is an ordinary answer for a lookup — a UI listing cases or
    resuming one has to be able to ask. It is distinguishable from a *damaged* case, which raises:
    a snapshot whose contents no longer satisfy `Case`, or that holds a different case id than the
    one it was filed under, is a corrupted record and must not be handed back half-populated.
    """
    state = _read_state(case_id, store_dir)
    if state is None:
        return None

    stored = state.get(STATE_KEY)
    if stored is None:
        raise ValueError(
            f"case {case_id!r}: a snapshot exists at session {session_id_for(case_id)!r} but holds "
            f"no case under state key {STATE_KEY!r}. The session was written by something other "
            "than attest.store."
        )

    # Validating through the model rather than returning the dict is what keeps a schema change or
    # a hand-edited snapshot from becoming a half-populated Case somewhere downstream.
    case = Case.model_validate(stored)

    # The one-session-per-case invariant, checked on the way out. If these disagree the store has
    # been written to out of band, and serving the record would mean answering about one patient
    # with another's case.
    if case.case_id != case_id:
        raise ValueError(
            f"case {case_id!r}: the snapshot at session {session_id_for(case_id)!r} holds case "
            f"{case.case_id!r}. One case, one session id — this store has been written to out of band."
        )

    return case


def load_appeal(case_id: str, store_dir: Path | str = STORE_DIR) -> Appeal | None:
    """Return the appeal stored for this case, or `None` if there is none.

    Same split as `load_case`: absence is an ordinary answer, damage raises.
    """
    state = _read_state(case_id, store_dir)
    if state is None or APPEAL_KEY not in state:
        return None

    appeal = Appeal.model_validate(state[APPEAL_KEY])

    if appeal.case_id != case_id:
        raise ValueError(
            f"case {case_id!r}: the snapshot at session {session_id_for(case_id)!r} holds an "
            f"appeal for case {appeal.case_id!r}. This store has been written to out of band."
        )

    return appeal


def list_cases(store_dir: Path | str = STORE_DIR) -> list[str]:
    """Every stored case id, sorted.

    Not in P6-S1's written Definition of Done, but a case store that cannot be enumerated is not a
    case store — P6-S3's UI has to render a case list, and the alternative is that it reaches into
    the storage layout itself.

    This does read Strands' session key layout, which is the one place in the module coupled to it.
    `test_a_saved_case_is_listed` pins that, so a Strands upgrade that changes the layout fails a
    test rather than quietly reporting that the practice has no open cases.
    """
    keys = asyncio.run(_storage(store_dir).list(""))

    ids = set()
    for key in keys:
        for part in key.split("/"):
            if part.startswith(SESSION_PREFIX):
                ids.add(part[len(SESSION_PREFIX) :])
                break

    return sorted(ids)
