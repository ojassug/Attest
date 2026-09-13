"""Gate for P0-S3 — repo skeleton, tooling, and the gate runner.

These tests also retroactively validate P0-S2's protocol documents: PLAN.md is the
contract, and STATUS.md and the pytest marker list must both track it exactly. If any
of the three drift, a session picking up on the other machine gets a false picture of
where the project stands, which is the one failure this protocol exists to prevent.
"""

import os
import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.p0_s3

REPO = Path(__file__).resolve().parents[1]

STEP_HEADING = re.compile(r"^## (P\d+-S\d+)", re.M)
STATUS_ROW = re.compile(r"^\|\s*(P\d+-S\d+)\s*\|", re.M)

# `bedrock-agentcore` was here until 2026-09-13, when Bedrock and AgentCore were dropped from
# the architecture entirely: Strands is the only AWS SDK this project uses, and the model is
# Gemini. A declared dependency on an AgentCore SDK we never import would be a claim the README
# contradicts, installed into every judge's clone. See DECISIONS.md, 2026-09-13.
REQUIRED_DEPS = (
    "strands-agents",
    "strands-agents-tools",
    "pydantic",
    "pytest",
    "streamlit",
    "pyyaml",
)


FORBIDDEN_DEPS = ("bedrock-agentcore",)


def plan_steps() -> list[str]:
    return STEP_HEADING.findall((REPO / "PLAN.md").read_text(encoding="utf-8"))


def status_steps() -> list[str]:
    return STATUS_ROW.findall((REPO / "STATUS.md").read_text(encoding="utf-8"))


def declared_markers() -> list[str]:
    cfg = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    raw = cfg["tool"]["pytest"]["ini_options"]["markers"]
    return [m.split(":", 1)[0].strip() for m in raw]


def test_status_covers_all_plan_steps():
    """Every step in the contract has exactly one row on the board, and vice versa."""
    plan = plan_steps()
    status = status_steps()

    assert plan, "PLAN.md declares no steps"

    missing = [s for s in plan if s not in status]
    assert not missing, f"steps in PLAN.md with no STATUS.md row: {missing}"

    orphans = [s for s in status if s not in plan]
    assert not orphans, f"STATUS.md rows with no matching PLAN.md step: {orphans}"

    duplicates = sorted({s for s in status if status.count(s) > 1})
    assert not duplicates, f"duplicate STATUS.md rows: {duplicates}"

    assert status == plan, (
        "STATUS.md rows are not in PLAN.md order — the board must read in execution "
        f"order.\n  plan:   {plan}\n  status: {status}"
    )


def test_every_step_has_a_marker():
    """Each step id maps to a registered pytest marker, so verify.sh can select it."""
    markers = declared_markers()
    expected = [s.lower().replace("-", "_") for s in plan_steps()]

    missing = [m for m in expected if m not in markers]
    assert not missing, f"steps with no registered pytest marker: {missing}"

    assert "live" in markers, "the 'live' marker must be registered"


def test_required_dependencies_declared():
    cfg = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    declared = " ".join(
        cfg["project"]["dependencies"]
        + [d for group in cfg["project"].get("optional-dependencies", {}).values() for d in group]
    )
    missing = [d for d in REQUIRED_DEPS if d not in declared]
    assert not missing, f"dependencies missing from pyproject.toml: {missing}"

    # The architecture claim is enforceable, so enforce it. README.md and DECISIONS.md both say
    # this project uses Strands and nothing else from AWS; a dependency is the one place that
    # claim can quietly become false without anyone reading a document.
    present = [d for d in FORBIDDEN_DEPS if d in declared]
    assert not present, (
        f"dependencies pyproject.toml must not declare: {present}. Bedrock and AgentCore were "
        "dropped on 2026-09-13 - see DECISIONS.md."
    )


def test_license_is_apache():
    """The rules accept MIT or Apache. PR #1 chose Apache 2.0."""
    head = (REPO / "LICENSE").read_text(encoding="utf-8")[:400]
    assert "Apache License" in head, "LICENSE is not Apache 2.0"


def test_package_is_importable():
    import attest

    assert attest.__version__


def test_verify_script_is_executable():
    script = REPO / "scripts" / "verify.sh"
    assert script.is_file(), "scripts/verify.sh is missing"
    assert os.access(script, os.X_OK), "scripts/verify.sh is not executable"


def test_synthetic_data_is_never_real_phi():
    """Guard rail for §7 of the product spec: the demo uses synthetic data only.

    Trivially true today because data/ does not exist yet. It becomes load-bearing in
    P1-S4, and failing early is better than discovering a real note in the repo later.
    """
    data = REPO / "data" / "synthetic"
    if not data.exists():
        pytest.skip("no synthetic corpus yet — created in P1-S4")
    for note in data.rglob("*.md"):
        head = note.read_text(encoding="utf-8")[:200]
        assert "SYNTHETIC" in head.upper(), f"{note} lacks a synthetic-data banner"
