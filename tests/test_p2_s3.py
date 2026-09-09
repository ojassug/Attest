"""Gate for P2-S3 — the intake agent.

Two things need proving: that the tool is wired up at all (cheap, no API call), and that the
agent actually *calls* it rather than answering from its own recollection of payer rules. The
second needs a live run, because a replayed cassette records the answer, not the tool call.
"""

import pytest

from attest.agents.intake_agent import (
    IntakeResult,
    build_intake_agent,
    check_prior_authorization,
    determine_authorization,
    run_intake,
)
from attest.corpus import all_cases
from attest.llm import have_credentials
from attest.models import PARequirement
from conftest import needs_model

pytestmark = pytest.mark.p2_s3

CASES = all_cases()


def test_pa_tool_is_registered(monkeypatch):
    """No API call. Catches the tool silently falling off the agent.

    A placeholder credential is injected because `build_model` refuses to construct without one -
    deliberately, so that a missing key surfaces as a setup problem rather than as an auth error
    deep inside an agent run. Constructing the agent makes no request, so any string will do.

    Without this the test needed a real key to be *present* despite calling nothing, which made a
    keyless clone fail 1 of 268 and left the "judges can clone and run it" claim untrue.
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "placeholder-no-request-is-made")

    assert "check_prior_authorization" in build_intake_agent().tool_names


def test_tool_is_callable_and_returns_json():
    """Strands serialises tool results, so the tool must return plain JSON, not a Pydantic object.

    `@tool` wraps the function in a DecoratedFunctionTool, which is not directly callable, so the
    underlying behaviour is exercised through the function the tool delegates to.
    """
    from attest.tools.pa_lookup import check_pa_required

    out = check_pa_required("90867", "PacificSource", "Commercial").model_dump(mode="json")
    assert isinstance(out, dict)
    assert out["requirement"] == "required"
    assert out["policy_id"] == "pacificsource-commercial-tms"


def test_tool_spec_documents_its_arguments():
    """The agent picks arguments from this spec, so the descriptions are load-bearing."""
    spec = check_prior_authorization.tool_spec
    schema = spec["inputSchema"]["json"]
    assert set(schema["required"]) == {"cpt_code", "payer", "plan"}
    assert "90867" in schema["properties"]["cpt_code"]["description"]


@pytest.mark.live
@pytest.mark.skipif(
    not have_credentials(), reason="tool invocation cannot be replayed from a cassette"
)
def test_agent_invokes_pa_lookup_tool(monkeypatch):
    """The agent must call the tool, not answer from its own memory of payer rules.

    Cache is bypassed deliberately: a cassette replays the final answer, which would hide the
    absence of a tool call entirely.
    """
    monkeypatch.setenv("ATTEST_CACHE", "off")

    import attest.tools.pa_lookup as lookup_mod
    import attest.agents.intake_agent as agent_mod

    calls: list[tuple] = []
    real = lookup_mod.check_pa_required

    def spy(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(agent_mod, "check_pa_required", spy)

    determine_authorization(_case_for(CASES[0]))
    assert calls, "the agent never invoked check_prior_authorization"


def _case_for(expected):
    """Build a Case from ground truth without spending a model call on extraction."""
    from datetime import datetime, timezone

    from attest.models import Case, InsuranceInfo, ServiceRequest

    i = expected.intake
    return Case(
        case_id=expected.case_id,
        note_id=expected.name,
        patient_ref=expected.case_id,
        insurance=InsuranceInfo(payer=i["payer"], plan=i["plan"], member_id="TEST"),
        service=ServiceRequest(service=i["service"], cpt_codes=i["cpt_codes"]),
        primary_diagnosis_code=i["primary_diagnosis_code"],
        primary_diagnosis_text="Major depressive disorder",
        created_at=datetime.now(timezone.utc),
    )


@needs_model
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_determination_matches_ground_truth(case):
    got = determine_authorization(_case_for(case))
    assert got.requirement.value == case.raw["pa_required"]


@needs_model
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_run_intake_end_to_end(case):
    result = run_intake(case.note_text, note_id=case.name)
    assert isinstance(result, IntakeResult)
    assert result.case.insurance.payer == case.intake["payer"]
    assert result.determination.requirement is PARequirement.REQUIRED
    assert set(result.case.service.cpt_codes) == set(case.intake["cpt_codes"])
