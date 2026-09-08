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


def test_requirements_txt_pins_the_runtime_dependencies():
    """AgentCore builds the image from this file, not from pyproject."""
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(encoding="utf-8")
    pinned = [
        line for line in text.splitlines() if line.strip() and not line.strip().startswith("#")
    ]

    assert pinned, "requirements.txt is empty"
    for line in pinned:
        assert "==" in line, f"unpinned runtime dependency: {line!r}"
    joined = " ".join(pinned)
    for required in ("strands-agents", "bedrock-agentcore", "pydantic", "fpdf2"):
        assert required in joined, f"{required} missing from requirements.txt"


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
