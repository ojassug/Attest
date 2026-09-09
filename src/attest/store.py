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

from attest.models import Case

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

# Where the case sits in agent state.
STATE_KEY = "case"


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


def save_case(case: Case, store_dir: Path | str = STORE_DIR) -> str:
    """Persist a case, overwriting any earlier version of that same case.

    Returns the session id it was written under, so a caller can log or display where a case
    actually lives rather than reconstructing the mapping itself.
    """
    manager = _manager(case.case_id, store_dir)

    # Deliberately constructed without `session_manager=`. Passing it would restore the *stored*
    # snapshot over the state we just set, so saving a case would write back the previous one.
    agent = Agent(agent_id=AGENT_ID, state={STATE_KEY: case.model_dump(mode="json")})

    asyncio.run(manager.save_snapshot(agent, is_latest=True))
    return manager.session_id


def load_case(case_id: str, store_dir: Path | str = STORE_DIR) -> Case | None:
    """Return the stored case, or `None` if this case has never been saved.

    `None` means "no such case", which is an ordinary answer for a lookup — a UI listing cases or
    resuming one has to be able to ask. It is distinguishable from a *damaged* case, which raises:
    a snapshot whose contents no longer satisfy `Case`, or that holds a different case id than the
    one it was filed under, is a corrupted record and must not be handed back half-populated.
    """
    manager = _manager(case_id, store_dir)
    agent = Agent(agent_id=AGENT_ID)

    if not asyncio.run(manager.restore_snapshot(agent)):
        return None

    stored = agent.state.get(STATE_KEY)
    if stored is None:
        raise ValueError(
            f"case {case_id!r}: a snapshot exists at session {manager.session_id!r} but holds no "
            f"case under state key {STATE_KEY!r}. The session was written by something other than "
            "attest.store."
        )

    # Validating through the model rather than returning the dict is what keeps a schema change or
    # a hand-edited snapshot from becoming a half-populated Case somewhere downstream.
    case = Case.model_validate(stored)

    # The one-session-per-case invariant, checked on the way out. If these disagree the store has
    # been written to out of band, and serving the record would mean answering about one patient
    # with another's case.
    if case.case_id != case_id:
        raise ValueError(
            f"case {case_id!r}: the snapshot at session {manager.session_id!r} holds case "
            f"{case.case_id!r}. One case, one session id — this store has been written to out of band."
        )

    return case


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
