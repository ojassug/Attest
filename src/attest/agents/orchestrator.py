"""The orchestrator: four specialist agents, composed as tools.

Judging criterion 1 scores how thoroughly a project uses Strands. This is that — `agent.as_tool()`
composition over the intake, criteria, packet and appeal specialists, on top of the structured
output, tool calling, hook interrupts and session persistence the rest of the codebase already
uses.

Two decisions here are load-bearing, and both are about keeping orchestration from eroding
guarantees the deterministic pipeline already provides.

**Specialists exchange identifiers, never clinical content.** Every tool reads and writes a shared
`Run` and returns a short factual summary — counts, criterion ids, verdicts. It never returns a
quote. If evidence travelled between agents as prose, each hop would be a chance for a model to
paraphrase it, and the paraphrase would arrive at the packet builder looking exactly like a quote.
The verifier cannot catch that, because by then the note it would check against is two agents away.
So the note is read once and the spans live in `Run`, where only code touches them.

**Verification is inside the criteria tool, not a step the orchestrator can choose.** A router that
*could* skip `enforce_verification` would eventually skip it. `assess_criteria` matches and enforces
in one indivisible call, and there is no tool that returns unverified coverage — so no routing
decision, however confused, can produce a packet built on unverified evidence.

The result is that the orchestrator decides *what to do next*, and code decides *what is true*.
`test_end_to_end_parity` pins that: the orchestrated run must produce byte-identical verdicts to
the direct pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from strands import Agent, tool

from attest.agents.intake import extract_case
from attest.agents.intake_agent import determine_authorization
from attest.appeal.assemble import build_appeal
from attest.appeal.draft import draft_rebuttals
from attest.appeal.parse import parse_denial
from attest.criteria.gaps import build_gap_list
from attest.criteria.match import match_all
from attest.llm import build_model, with_retry
from attest.models import (
    Appeal,
    Case,
    CriteriaCoverage,
    Denial,
    GapItem,
    PADetermination,
    Packet,
)
from attest.packet.justification import build_justification
from attest.policies.schema import PolicyPack
from attest.verifier import VerificationReport, enforce_verification

INTAKE = "intake_specialist"
CRITERIA = "criteria_specialist"
PACKET = "packet_specialist"
APPEAL = "appeal_specialist"


@dataclass
class Run:
    """One case's working state, shared by every specialist.

    This exists so that agents can pass each other *references* to clinical facts rather than the
    facts themselves. See the module docstring: prose hand-offs are where paraphrase gets in.
    """

    case_id: str
    note: str
    pack: PolicyPack
    denial_text: str | None = None

    case: Case | None = None
    determination: PADetermination | None = None
    coverage: CriteriaCoverage | None = None
    verification: VerificationReport | None = None
    gaps: list[GapItem] = field(default_factory=list)
    packet: Packet | None = None
    denial: Denial | None = None
    appeal: Appeal | None = None

    # Which specialists actually ran. The orchestrator's routing is the thing under test in
    # `test_orchestrator_routes_to_each_specialist`, and an agent's prose is no evidence of it.
    calls: list[str] = field(default_factory=list)

    def record(self, specialist: str) -> None:
        self.calls.append(specialist)


# ------------------------------------------------------------------------------- steps
#
# The work each specialist does, as plain functions. The @tool closures below are thin wrappers.
#
# Separated so the pipeline can be exercised without a routing model in the loop: these replay
# from cassettes and cost no quota, which is what lets `test_orchestrated_steps_match_the_direct_pipeline`
# run offline. It also states the design claim in code - orchestration contributes routing and
# nothing else, so the steps must be complete on their own.


def do_intake(run: Run) -> str:
    run.record(INTAKE)
    run.case = extract_case(run.note, note_id=run.case_id, case_id=run.case_id)
    run.determination = determine_authorization(run.case)
    return (
        f"case {run.case.case_id}: {run.case.service.service}; "
        f"CPT {', '.join(run.case.service.cpt_codes)}; "
        f"diagnosis {run.case.primary_diagnosis_code}; "
        f"payer {run.case.insurance.payer} / {run.case.insurance.plan}; "
        f"prior authorization {run.determination.requirement.value}"
    )


def do_criteria(run: Run) -> str:
    run.record(CRITERIA)
    # Matching and verification are one call on purpose. Splitting them would let a router
    # emit a packet from unverified coverage; see the module docstring.
    matched = match_all(run.pack, run.note, case_id=run.case_id, note_id=run.case_id)
    verified = enforce_verification(matched, run.note)
    run.coverage, run.verification = verified.coverage, verified.report
    run.gaps = build_gap_list(run.coverage)

    verdicts = ", ".join(f"{v.criterion_id}={v.verdict.value}" for v in run.coverage.verdicts)
    gaps = ", ".join(g.criterion_id for g in run.gaps) or "none"
    return f"verdicts: {verdicts}. gaps: {gaps}."


def do_packet(run: Run) -> str:
    run.record(PACKET)
    if run.coverage is None or run.case is None:
        return "cannot assemble a packet before intake and criteria matching have run."

    justification = build_justification(run.coverage, run.case)
    run.packet = Packet(
        case_id=run.case.case_id,
        coverage=run.coverage,
        justification=justification,
        gaps=run.gaps,
    )
    spans = {s for c in justification.claims for s in c.supporting_span_ids}
    return (
        f"packet for {run.packet.case_id}: {len(justification.claims)} claims citing "
        f"{len(spans)} verified spans; {len(run.gaps)} gap(s). Awaiting clinician approval - "
        "no document is written until Gate 1 passes."
    )


def do_appeal(run: Run) -> str:
    run.record(APPEAL)
    if run.denial_text is None:
        return "there is no denial letter for this case, so there is nothing to appeal."
    if run.coverage is None:
        return "cannot draft an appeal before criteria matching has run."

    run.denial = parse_denial(run.denial_text, run.pack, case_id=run.case_id)
    rebuttals = draft_rebuttals(run.denial.contested, run.coverage, run.pack)
    run.appeal = build_appeal(run.denial, rebuttals, run.pack)

    contested = ", ".join(c.criterion_id for c in run.denial.contested)
    unmapped = len(run.denial.unmapped_reasons)
    return (
        f"contested: {contested}. rebuttals: {len(run.appeal.rebuttals)}. "
        f"deadline {run.appeal.deadline.isoformat()} ({run.appeal.deadline_source}). "
        f"{unmapped} payer objection(s) map to no criterion and need a separate response. "
        "Awaiting clinician approval - no appeal is sent until Gate 2 passes."
    )


# --------------------------------------------------------------------------- specialists


def _intake_agent(run: Run) -> Agent:
    @tool
    def read_the_note() -> str:
        """Extract the structured case from the clinical note and determine whether prior
        authorization is required.

        Returns:
            A summary of the service, diagnosis, payer and the authorization determination.
        """
        return do_intake(run)

    return Agent(
        model=build_model("fast"),
        name=INTAKE,
        description=(
            "Reads a clinical note into a structured case and determines whether the payer "
            "requires prior authorization. Run this first."
        ),
        system_prompt=(
            "You handle intake. Call read_the_note exactly once, then report what it returned. "
            "Never restate a prior-authorization requirement as anything other than what the tool "
            "said - in particular never soften UNKNOWN into 'probably not required'."
        ),
        tools=[read_the_note],
    )


def _criteria_agent(run: Run) -> Agent:
    @tool
    def assess_criteria() -> str:
        """Check the note against every criterion in the payer's policy, verify the evidence, and
        list what the practice still needs to supply.

        Returns:
            Each criterion id with its verdict, plus the gap list.
        """
        return do_criteria(run)

    return Agent(
        model=build_model("fast"),
        name=CRITERIA,
        description=(
            "Checks the clinical note against the payer's published criteria, verifies every "
            "quoted piece of evidence appears verbatim in the note, and produces the gap list. "
            "Run this after intake."
        ),
        system_prompt=(
            "You handle criteria matching. Call assess_criteria exactly once and report the "
            "verdicts and gaps it returns. Do not quote the clinical note yourself and do not "
            "reinterpret a verdict - the evidence has already been verified by code, and anything "
            "you add has not been."
        ),
        tools=[assess_criteria],
    )


def _packet_agent(run: Run) -> Agent:
    @tool
    def assemble_packet() -> str:
        """Build the submission packet: the medical-necessity justification, the criteria coverage
        and the gap list, ready for a clinician to approve.

        Returns:
            The number of claims and the spans they cite.
        """
        return do_packet(run)

    return Agent(
        model=build_model("fast"),
        name=PACKET,
        description=(
            "Assembles the submission packet from verified evidence and holds it for clinician "
            "approval. Run this after criteria matching."
        ),
        system_prompt=(
            "You assemble submission packets. Call assemble_packet exactly once and report what it "
            "returned. You never approve a packet and you never emit a document - a named "
            "clinician does that at Gate 1."
        ),
        tools=[assemble_packet],
    )


def _appeal_agent(run: Run) -> Agent:
    @tool
    def build_the_appeal() -> str:
        """Read the payer's denial letter, identify which criteria it contests, draft a rebuttal
        for each from verified evidence, and compute the filing deadline.

        Returns:
            The contested criterion ids, the rebuttals drafted, and the appeal deadline.
        """
        return do_appeal(run)

    return Agent(
        model=build_model("fast"),
        name=APPEAL,
        description=(
            "Turns a payer denial into a criteria-cited appeal with a filing deadline, and holds "
            "it for clinician approval. Run this only when the case has a denial letter."
        ),
        system_prompt=(
            "You handle appeals. Call build_the_appeal exactly once and report what it returned. "
            "Report the deadline together with its stated source - an appeal deadline presented "
            "without provenance is worse than none, because it looks authoritative. You never "
            "approve or send an appeal; a named clinician does that at Gate 2."
        ),
        tools=[build_the_appeal],
    )


# ------------------------------------------------------------------------- orchestrator

SYSTEM_PROMPT = """\
You coordinate a prior-authorization case for a small specialty practice. You do no clinical
reasoning yourself: you decide which specialist to call, and you report what they return.

Call them in this order, one at a time:

1. intake_specialist - always first. Structures the note and determines whether a PA is required.
2. criteria_specialist - always second. Matches the note against the payer's criteria and verifies
   the evidence.
3. packet_specialist - assembles the submission packet for clinician approval.
4. appeal_specialist - only when the case has a denial letter to answer.

Rules you may not break:

- Never skip the criteria specialist. Every downstream document is built from verified evidence,
  and only that specialist produces it.
- Never state a clinical fact, quote the note, or adjust a verdict a specialist reported. Their
  output has been verified by code; anything you add has not been.
- Never claim a document was submitted or an appeal sent. Both wait on a named clinician.

Finish with a short factual summary of what each specialist reported.
"""


def build_orchestrator(run: Run) -> Agent:
    """The orchestrator, with the four specialists composed in via `agent.as_tool()`.

    `preserve_context` is left at its default of False, so each specialist starts from the same
    baseline on every invocation. Their continuity lives in `run`, which is code-owned, rather than
    in a conversation history a later turn could reinterpret.
    """
    specialists = [
        _intake_agent(run),
        _criteria_agent(run),
        _packet_agent(run),
        _appeal_agent(run),
    ]

    return Agent(
        # The router runs on the reasoning tier while the specialists run on the fast one. Routing
        # is the step with an ordering rule to keep and a skip to refuse, and it is the one call
        # nothing downstream can check - a specialist that misbehaves still lands in `Run`, where
        # code sees it, but a router that silently omits the criteria specialist just produces a
        # thinner case. It also splits the work across two daily quotas, which is what makes the
        # live tests runnable at all on a 20-request-per-model free tier.
        model=build_model("reasoning"),
        name="attest_orchestrator",
        system_prompt=SYSTEM_PROMPT,
        tools=[a.as_tool(name=a.name, description=a.description) for a in specialists],
    )


def run_case(
    note: str,
    pack: PolicyPack,
    *,
    case_id: str,
    denial_text: str | None = None,
) -> Run:
    """Drive one case through the orchestrator and return everything it produced.

    The `Run` is the result, not the agent's prose. A caller needs the typed `Packet` and `Appeal`,
    and reading them out of a model's summary would be exactly the paraphrase hop this design
    exists to avoid.
    """
    run = Run(case_id=case_id, note=note, pack=pack, denial_text=denial_text)
    agent = build_orchestrator(run)

    request = (
        f"Case {case_id}. Payer {pack.payer} ({pack.plan}), service {pack.service}. "
        "Run intake, then criteria matching, then assemble the submission packet."
    )
    if denial_text is not None:
        request += " The payer has since denied this case, so draft the appeal as well."

    # Retried like every other model call in the project. An orchestrated run is many calls deep,
    # so it is *more* exposed to the free tier's unpredictable 503s than a single structured-output
    # call is, not less - one blip anywhere in the routing loop would otherwise abandon the case
    # halfway and read as a real regression. Found exactly that way: the parity run completed the
    # first case, then died mid-intake on the second with a provider ServerError.
    with_retry(lambda: agent(request))
    return run
