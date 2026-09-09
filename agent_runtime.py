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

Payload accepts `{"case": "<clean|gap|denial|pt>"}` for the synthetic demo cases, or a raw note as
`{"note": "..."}` / `{"prompt": "..."}`. With cassettes present it needs no credentials at all,
which is what makes it testable and demonstrable offline.

**Two execution modes, and the default is the boring one.** `{"mode": "direct"}` (the default) runs
the deterministic pipeline. `{"mode": "orchestrated"}` routes the same work through the P7-S1
orchestrator and its four specialist subagents. They are required to produce identical verdicts —
`test_end_to_end_parity` is that assertion — so the choice is about what the caller wants to
observe, never about what comes out. Direct is the default because a deployed service should not
spend a routing model's quota, and a 503 in a routing loop is a failed request rather than a
slower one.
"""

from __future__ import annotations

import logging

from bedrock_agentcore import BedrockAgentCoreApp

from attest.agents.intake import extract_case
from attest.agents.orchestrator import Run, do_criteria, do_intake, do_packet
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

# The three TMS cases plus the physical-therapy extensibility case. `CASE_NAMES` deliberately
# holds only the TMS three so the PT case cannot leak into tests that assume TMS verdicts; a
# caller of the service has no such constraint and should be able to ask for either specialty.
DEMO_CASES = (*CASE_NAMES, "pt")

MODES = ("direct", "orchestrated")


def _resolve(payload: dict) -> tuple[str, str, str] | dict:
    """Work out which note to run on. Returns (note_text, case_id, note_id) or an error dict."""
    if not isinstance(payload, dict) or not payload:
        return {"error": "empty payload: send {'case': '<name>'} or {'note': '<clinical note>'}"}

    name = payload.get("case")
    if name is not None:
        # The PT case lives outside CASE_NAMES on purpose - it is a different specialty and must
        # not leak into tests that assume TMS - but a caller should still be able to ask for it.
        if name not in DEMO_CASES:
            return {"error": f"unknown case {name!r}; available cases: {sorted(DEMO_CASES)}"}
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

    mode = payload.get("mode", "direct")
    if mode not in MODES:
        return {"error": f"unknown mode {mode!r}; expected one of {list(MODES)}"}

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

        if mode == "orchestrated":
            # Same work, routed through the four specialist subagents. Required to agree with the
            # direct path - test_end_to_end_parity holds that - so this changes what a caller can
            # watch, never what comes back.
            run = Run(case_id=case.case_id, note=note_text, pack=pack)
            do_intake(run)
            do_criteria(run)
            do_packet(run)
            packet, verified_report = run.packet, run.verification
        else:
            matched = match_all(pack, note_text, case_id=case.case_id, note_id=note_id)
            verified = enforce_verification(matched, note_text)
            verified_report = verified.report

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
        "mode": mode,
        "pack_id": packet.coverage.pack_id,
        "packet": packet.model_dump(mode="json"),
        "content_hash": content_hash(packet),
        "approval_required": True,
        "next_step": (
            "Gate 1: a clinician must review this packet and approve the content_hash above "
            "before any submission artifact is emitted."
        ),
        "rejected_spans": [r.model_dump(mode="json") for r in verified_report.rejected],
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(port=8080)
