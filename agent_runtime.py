"""Attest as a deployed service — the Amazon Bedrock AgentCore Runtime entrypoint.

One HTTP handler runs the whole pipeline: a clinical note goes in, an assembled prior-authorization
packet comes out — intake, PA determination, criteria matching, span verification, the gap list,
and the medical-necessity justification.

**It stops before Gate 1, on purpose.** The response carries the packet and the content hash a
clinician must approve; it never writes a submission artifact. `Attest-PRODUCT.md` §6 makes human
approval non-negotiable, and a headless deployment is exactly where that rule would otherwise
quietly become a UI convention. Emitting is a separate, approved step — see `attest.gates`.

Run locally:

    python agent_runtime.py
    curl -X POST localhost:8080/invocations \\
         -H 'Content-Type: application/json' \\
         -d '{"case": "gap"}'

Payload accepts `{"case": "<clean|gap|denial>"}` for the synthetic demo cases, or a raw note as
`{"note": "..."}` / `{"prompt": "..."}`. With cassettes present it needs no credentials at all,
which is what makes it testable and demonstrable offline.
"""

from __future__ import annotations

import logging

from bedrock_agentcore import BedrockAgentCoreApp

from attest.agents.intake import extract_case
from attest.corpus import CASE_NAMES, load_case
from attest.criteria.gaps import build_gap_list
from attest.criteria.match import match_all
from attest.gates import content_hash
from attest.models import Packet
from attest.packet.justification import build_justification
from attest.policies.loader import find_pack
from attest.verifier import enforce_verification

log = logging.getLogger("attest.runtime")

app = BedrockAgentCoreApp()


def _resolve(payload: dict) -> tuple[str, str, str] | dict:
    """Work out which note to run on. Returns (note_text, case_id, note_id) or an error dict."""
    if not isinstance(payload, dict) or not payload:
        return {"error": "empty payload: send {'case': '<name>'} or {'note': '<clinical note>'}"}

    name = payload.get("case")
    if name is not None:
        if name not in CASE_NAMES:
            return {"error": f"unknown case {name!r}; available cases: {sorted(CASE_NAMES)}"}
        case = load_case(name)
        return case.note_text, case.case_id, name

    note = payload.get("note") or payload.get("prompt")
    if not isinstance(note, str) or not note.strip():
        return {"error": "no note supplied: send {'case': '<name>'} or {'note': '<clinical note>'}"}

    return note, payload.get("case_id") or "RUNTIME-001", payload.get("note_id") or "note"


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Assemble a packet for one case and return it for human approval.

    Never raises to the caller: a deployed runtime that answers a bad payload with a 500 tells the
    caller nothing it can act on, so failures come back as `{"error": ...}` with the reason.
    """
    resolved = _resolve(payload)
    if isinstance(resolved, dict):
        return resolved

    note_text, case_id, note_id = resolved

    try:
        case = extract_case(note_text, case_id=case_id, note_id=note_id)

        pack = find_pack(case.service.cpt_codes[0], case.insurance.payer, case.insurance.plan)
        if pack is None:
            return {
                "error": (
                    f"no policy pack covers CPT {case.service.cpt_codes[0]} for "
                    f"{case.insurance.payer} {case.insurance.plan}. Absence of a policy is not "
                    "evidence that no prior authorization is needed - escalate to a human."
                )
            }

        matched = match_all(pack, note_text, case_id=case.case_id, note_id=note_id)
        verified = enforce_verification(matched, note_text)

        packet = Packet(
            case_id=case.case_id,
            coverage=verified.coverage,
            justification=build_justification(verified.coverage, case),
            gaps=build_gap_list(verified.coverage),
        )
    except Exception as exc:  # noqa: BLE001 - the boundary of a deployed service
        log.exception("packet assembly failed for case_id=%s", case_id)
        return {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "case_id": packet.case_id,
        "pack_id": packet.coverage.pack_id,
        "packet": packet.model_dump(mode="json"),
        "content_hash": content_hash(packet),
        "approval_required": True,
        "next_step": (
            "Gate 1: a clinician must review this packet and approve the content_hash above "
            "before any submission artifact is emitted."
        ),
        "rejected_spans": [r.model_dump(mode="json") for r in verified.report.rejected],
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(port=8080)
