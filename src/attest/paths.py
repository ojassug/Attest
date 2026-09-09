"""Where the repository's data lives, resolved rather than assumed.

Three directories this package reads are **repo assets, not package assets**: the synthetic corpus
(`data/synthetic`), the source policy texts (`data/policies/raw`), and the recorded model responses
(`cassettes/`). They sit outside `src/`, so they are not installed with the package.

Every module used to find them with `Path(__file__).resolve().parents[2]`, which is the repo root
only when the package is installed **editable** — the layout every developer and every test runs
under. Installed normally, `__file__` is inside `site-packages` and `parents[2]` is a directory in
the virtualenv that has never contained anything. That is not a crash at import; it is a wrong
path that fails later, at the first read, in whatever code happened to touch data first.

It reached production exactly that way: the P6-S4 Streamlit deploy installs from `requirements.txt`,
which is a plain (non-editable) install, so the hosted app raised `FileNotFoundError` on the corpus
while the local suite stayed green. Two further failures were queued behind it — the policy packs
and the cassettes were both missing from the built wheel too.

So the root is now *searched for* rather than computed, and the search is explicit about what it is
looking for: a directory that actually contains `data/synthetic`.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

ROOT_ENV_VAR = "ATTEST_REPO_ROOT"

# What identifies the repository root. Deliberately one of the directories we need rather than
# something incidental like `.git`, which is absent from a deployment checkout or a Docker image.
MARKER = Path("data") / "synthetic"


def _has_marker(candidate: Path) -> bool:
    return (candidate / MARKER).is_dir()


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """The directory holding `data/` and `cassettes/`.

    Resolution order, most explicit first:

    1. ``$ATTEST_REPO_ROOT`` — for an image or host that puts the assets somewhere unusual.
    2. Upward from this file — an editable install or a source checkout, which is how the tests
       and every developer run.
    3. Upward from the working directory — an ordinary install whose repo is still checked out
       around it. This is the hosted case: Streamlit Cloud installs the package into a virtualenv
       but runs `app.py` from the checkout at `/mount/src/<repo>`.

    Falls back to the old `parents[2]` guess so behaviour is unchanged where it already worked.
    """
    override = os.environ.get(ROOT_ENV_VAR)
    if override:
        return Path(override)

    here = Path(__file__).resolve()
    for candidate in here.parents:
        if _has_marker(candidate):
            return candidate

    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if _has_marker(candidate):
            return candidate

    # Nothing found. Return the historical guess rather than raising: the caller's own
    # FileNotFoundError names the file it wanted, which is more useful than an error from here.
    return here.parents[2]


def data_dir() -> Path:
    return repo_root() / "data"


def cassettes_dir() -> Path:
    return repo_root() / "cassettes"
