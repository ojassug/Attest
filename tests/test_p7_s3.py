"""Gate for P7-S3 — the AgentCore Runtime entrypoint.

`agent_runtime.py` is how Attest runs as a deployed service rather than a library. The whole
pipeline runs behind one HTTP handler: note in, assembled packet out.

**The runtime never emits an artifact.** It returns the packet and the hash a clinician must
approve, and stops. That is Gate 1 holding in the place it matters most — a headless deployment,
where there is no UI to remember to ask. `Attest-PRODUCT.md` §6 calls this non-negotiable, and a
deployment that quietly skipped it would make the gate a UI convention rather than a product rule.

The handler is tested directly rather than over HTTP: it is a plain function, the server is
Starlette's, and booting a socket to prove a dict is returned tests the wrong thing. The DoD's
`curl` check covers the transport.
"""

import json

import pytest

from agent_runtime import app, invoke
from attest.gates import content_hash
from attest.models import Packet
from conftest import needs_model

pytestmark = pytest.mark.p7_s3


# --------------------------------------------------------------------------- wiring


def test_entrypoint_is_registered():
    """A handler the runtime never calls is dead code with a decorator on it."""
    assert callable(invoke)
    assert app is not None


def test_requirements_txt_installs_the_runtime_from_one_declaration():
    """AgentCore builds the image from this file — and so does the live Streamlit deploy.

    **Deliberate deviation from PLAN's wording**, which says this file "pins the runtime
    dependencies". It did, in the first P7-S3 attempt: a hand-maintained list of `==` pins beside
    `pyproject.toml`. Two things killed that.

    It is a second source of truth. The pins duplicated `pyproject.toml`'s dependency list with
    nothing keeping them in step, and the revert commit that removed them said so at the time.

    And this file now has two consumers. P6-S4 deploys the Streamlit console from the same
    `requirements.txt`, and that deploy is live and judge-facing. Replacing `.` with a pinned list
    that omits `streamlit` — as the original correctly did, since the UI is not part of the runtime
    image — would break the public demo to satisfy a word in the plan.

    So the file is one line, and it is `-e .`. It installs this package from `pyproject.toml` and
    brings its declared dependencies with it. If reproducible image builds are ever needed, the
    mechanism is a generated lockfile, not a second hand-edited list.

    **Editable, and that is load-bearing rather than stylistic.** A plain `.` installs into
    site-packages and leaves the synthetic corpus and the cassettes behind — they are repo assets
    outside `src/` — which is precisely how the live P6-S4 deploy came to raise `FileNotFoundError`
    while every local test stayed green. `tests/test_p6_s4.py` owns that regression.
    """
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8")
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert lines == ["-e ."], f"requirements.txt should install the package editable, got {lines}"

    # The single declaration must actually carry what the runtime imports.
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    for required in ("strands-agents", "bedrock-agentcore", "pydantic", "fpdf2", "streamlit"):
        assert required in pyproject, f"{required} missing from pyproject.toml"


# --------------------------------------------------------------------------- the happy path


@needs_model
def test_invoke_returns_a_packet_for_a_synthetic_case():
    result = invoke({"case": "gap"})

    assert result["case_id"] == "SYNTH-002"
    packet = Packet.model_validate(result["packet"])
    assert packet.justification.claims
    assert packet.gaps


@needs_model
def test_response_is_json_serializable():
    """It goes over HTTP. A Pydantic object in the response dict fails only in production."""
    assert json.dumps(invoke({"case": "clean"}))


@needs_model
def test_prompt_key_is_accepted_as_a_raw_note():
    """The DoD's curl example posts {"prompt": ...}, so that shape has to work."""
    from attest.corpus import load_case

    result = invoke({"prompt": load_case("clean").note_text})

    assert Packet.model_validate(result["packet"]).justification.claims


# --------------------------------------------------------------------------- Gate 1, headless


@needs_model
def test_runtime_does_not_emit_an_artifact():
    """No approval has happened yet, so nothing may be written."""
    result = invoke({"case": "clean"})

    assert result["approval_required"] is True
    assert Packet.model_validate(result["packet"]).approval is None


@needs_model
def test_response_carries_the_hash_to_be_approved():
    """The clinician approves a specific hash; without it the approval means nothing."""
    result = invoke({"case": "clean"})
    packet = Packet.model_validate(result["packet"])

    assert result["content_hash"] == content_hash(packet)


@needs_model
def test_every_cited_span_is_verified():
    """The safety property has to survive the trip through the runtime."""
    result = invoke({"case": "clean"})
    packet = Packet.model_validate(result["packet"])

    spans = {s.span_id: s for v in packet.coverage.verdicts for s in v.spans}
    cited = {i for c in packet.justification.claims for i in c.supporting_span_ids}

    assert cited
    assert all(spans[i].verified for i in cited)


# --------------------------------------------------------------------------- failure modes


def test_unknown_case_returns_an_error_not_a_crash():
    """A 500 from a deployed runtime tells the caller nothing."""
    result = invoke({"case": "not-a-real-case"})

    assert "error" in result
    assert "not-a-real-case" in result["error"]


def test_empty_payload_returns_an_error():
    result = invoke({})

    assert "error" in result


def test_blank_note_returns_an_error():
    result = invoke({"prompt": "   "})

    assert "error" in result


# ------------------------------------------------------- added in P7-S3, second attempt


def test_direct_is_the_default_mode():
    """A deployed service should not spend a routing model's quota unless asked.

    Both modes must agree on the answer, so defaulting to the cheap, deterministic one costs
    nothing. A 503 inside a routing loop is a failed request rather than a slower one.
    """
    from agent_runtime import MODES

    assert MODES[0] == "direct"


def test_an_unknown_mode_is_refused_rather_than_guessed():
    result = invoke({"case": "gap", "mode": "bogus"})

    assert "error" in result and "bogus" in result["error"]
    assert "packet" not in result


@needs_model
def test_the_response_names_the_mode_it_used():
    """A caller comparing two runs has to be able to tell which path produced which."""
    assert invoke({"case": "gap"})["mode"] == "direct"


@needs_model
def test_a_second_specialty_runs_through_the_deployed_surface():
    """P7-S2's claim, checked at the far end of the system.

    The physical-therapy case reaches the runtime through the same handler, the same pack
    resolution and the same verifier as TMS. If extensibility stopped short of the deployment
    surface it would not be extensibility.
    """
    result = invoke({"case": "pt"})

    assert "error" not in result, result.get("error")
    assert result["pack_id"] == "vnshealth-medicare-pt"

    packet = Packet.model_validate(result["packet"])
    assert packet.case_id == "SYNTH-004"
    assert len(packet.coverage.verdicts) == 11
    assert packet.justification.claims

    # The safety property is not specialty-specific either.
    cited = {s for c in packet.justification.claims for s in c.supporting_span_ids}
    verified = {s.span_id for v in packet.coverage.verdicts for s in v.spans if s.verified}
    assert cited <= verified
