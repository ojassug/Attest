"""Gate for P6-S4 — the public deploy stays installable.

P6-S4's Definition of Done is a URL that answers, and it did: the hosted console returned HTTP 200
and the step was marked done. Then the page itself raised `FileNotFoundError` on the corpus.

**HTTP 200 was the wrong thing to check.** It proves Streamlit's shell booted, not that the app
runs — the traceback is rendered *inside* a page the server is perfectly happy to serve. The
checklist step that would have caught it (`docs/ui-checklist.md`, walked against the deployed app)
had not been done.

**The defect underneath was a packaging one, and it was invisible to every test.** The suite runs
against an editable install, where `Path(__file__).parents[2]` happens to be the repo root.
`requirements.txt` did a plain install, so on the host `__file__` was inside `site-packages` and
`parents[2]` was a directory in the virtualenv. Worse, the built wheel contained only `.py` files:
the policy packs, the synthetic corpus and the cassettes were all absent, so two more failures were
queued behind the one that surfaced.

These tests hold the two halves of the fix: assets that belong to the package are packaged, and
assets that belong to the repository are *found* rather than computed from a parent count.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

from attest.paths import ROOT_ENV_VAR, repo_root

pytestmark = pytest.mark.p6_s4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "attest"


# ---------------------------------------------------------------- repo assets are found


def test_repo_root_finds_the_data_it_is_looking_for():
    root = repo_root()

    assert (root / "data" / "synthetic").is_dir()
    assert (root / "cassettes").is_dir()


def test_repo_root_honours_an_explicit_override(tmp_path, monkeypatch):
    """An image that puts the assets somewhere unusual needs a way to say so."""
    (tmp_path / "data" / "synthetic").mkdir(parents=True)
    monkeypatch.setenv(ROOT_ENV_VAR, str(tmp_path))
    repo_root.cache_clear()

    try:
        assert repo_root() == tmp_path
    finally:
        repo_root.cache_clear()


def test_repo_root_is_found_from_the_working_directory(tmp_path, monkeypatch):
    """The deployed case: package in site-packages, repo checked out around the process.

    Streamlit Cloud installs into a virtualenv and runs `app.py` from `/mount/src/<repo>`, so the
    search upward from `__file__` finds nothing and the working directory is what saves it. This
    is the exact path that was broken in production.
    """
    checkout = tmp_path / "mount" / "src" / "attest"
    (checkout / "data" / "synthetic").mkdir(parents=True)
    (checkout / "cassettes").mkdir()

    import attest.paths as paths

    monkeypatch.setattr(paths, "__file__", str(tmp_path / "venv" / "attest" / "paths.py"))
    monkeypatch.chdir(checkout)
    monkeypatch.delenv(ROOT_ENV_VAR, raising=False)
    paths.repo_root.cache_clear()

    try:
        assert paths.repo_root() == checkout.resolve()
    finally:
        paths.repo_root.cache_clear()


def test_no_module_computes_the_repo_root_by_counting_parents():
    """The tripwire for the actual bug.

    `Path(__file__).resolve().parents[2]` is correct only under an editable install. It is silent
    under every other install: not an import error, just a path that has never existed, failing
    later at whatever read happens to come first. Four modules did this; `attest.paths` replaces
    them all.
    """
    offenders = []
    for path in SRC.rglob("*.py"):
        if path.name == "paths.py":
            continue  # the one place allowed to reason about the layout
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "parents"
            ):
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")

    assert not offenders, (
        "these modules locate files by counting parent directories, which only works under an "
        f"editable install - use attest.paths instead: {offenders}"
    )


# ------------------------------------------------------------- package assets are packaged


def test_the_policy_packs_are_declared_as_package_data():
    """The packs live inside the package, so they must ship with it.

    Without this declaration the wheel carries only `.py` files and `load_pack` fails on any
    non-editable install — verified by building one and looking.
    """
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = config["tool"]["setuptools"]["package-data"]

    patterns = package_data["attest"]
    assert any("packs" in p and p.endswith(".yaml") for p in patterns), patterns

    # And the declaration has to match reality.
    packs = list((SRC / "policies" / "packs").glob("*.yaml"))
    assert len(packs) >= 3, f"expected the shipped packs, found {packs}"


def test_requirements_installs_editable_so_repo_assets_resolve():
    """`.` would install to site-packages and leave the corpus and cassettes behind.

    Both deployment surfaces read this file — the Streamlit console and the AgentCore image — and
    both need the repository layout the tests run against, not a copy of the `.py` files.
    """
    lines = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert lines == ["-e ."], f"requirements.txt must install this package editable, got {lines}"
