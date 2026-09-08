"""The intake agent: note in, structured case plus an authorization determination out.

Division of labour is deliberate. Extraction is a structured-output call because it has one
correct answer and no choices to make. The authorization determination is an *agent* call with a
tool, because it involves a judgment the model should make explicitly and visibly: a note may
request several CPT codes, and the agent decides which one governs the request before looking it
up. The lookup itself stays deterministic — the tool reads the policy index, it does not reason.

That split is the pattern the rest of the pipeline follows: models decide, code determines.
"""

from __future__ import annotations

from strands import Agent, tool

from attest.agents.intake import extract_case
from attest.cache import cached_structured
from attest.llm import build_model, model_id, with_retry
from attest.models import Base, Case, PADetermination
from attest.tools.pa_lookup import check_pa_required

SYSTEM_PROMPT = """\
You determine whether a requested healthcare service needs prior authorization.

You have one tool, check_prior_authorization. You must call it — never answer from your own
knowledge of payer rules, which is not a reliable source for a specific plan.

If the request names several CPT codes, call the tool with the primary procedure code (the one
that identifies the service being authorized, not a follow-up or add-on code).

Report exactly what the tool returns. If it reports UNKNOWN, say so plainly. Do not soften an
UNKNOWN into "probably not required" — a practice acting on that would deliver an unreimbursed
service.
"""


@tool
def check_prior_authorization(cpt_code: str, payer: str, plan: str) -> dict:
    """Look up whether a payer requires prior authorization for a CPT code.

    Args:
        cpt_code: The primary CPT/HCPCS procedure code, e.g. "90867".
        payer: Insurance payer name, e.g. "PacificSource".
        plan: Plan name, e.g. "Commercial" or "Medicaid".

    Returns:
        A determination with requirement (required / not_required / unknown), the policy id,
        a citation, and a rationale.
    """
    return check_pa_required(cpt_code, payer, plan).model_dump(mode="json")


class IntakeResult(Base):
    case: Case
    determination: PADetermination


def build_intake_agent() -> Agent:
    return Agent(
        model=build_model("fast"),
        system_prompt=SYSTEM_PROMPT,
        tools=[check_prior_authorization],
    )


def determine_authorization(case: Case) -> PADetermination:
    """Ask the agent to identify the governing code and look it up."""
    prompt = (
        f"Payer: {case.insurance.payer}\n"
        f"Plan: {case.insurance.plan}\n"
        f"Service: {case.service.service}\n"
        f"CPT codes requested: {', '.join(case.service.cpt_codes)}\n\n"
        "Determine whether this service requires prior authorization."
    )

    def produce() -> PADetermination:
        agent = build_intake_agent()
        return with_retry(
            lambda: agent(prompt, structured_output_model=PADetermination)
        ).structured_output

    return cached_structured(
        "pa_determination", "fast", SYSTEM_PROMPT + prompt, PADetermination, produce
    )


def run_intake(note_text: str, *, note_id: str = "note") -> IntakeResult:
    """Full intake: note to structured case to authorization determination."""
    case = extract_case(note_text, note_id=note_id)
    return IntakeResult(case=case, determination=determine_authorization(case))
