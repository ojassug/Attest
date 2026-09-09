"""Draft the rebuttal that answers a payer's denial.

This is the document that argues back, and the last surface where a fabricated clinical claim
could reach the payer. So the model's job is deliberately narrow: **it writes the prose and
nothing else.**

Everything checkable is supplied by code:

* ``policy_citation`` comes from the criterion in the pack, so "every citation resolves to a real
  ``source_section``" is true by construction rather than by instruction.
* ``supporting_span_ids`` come from the verified coverage. ``Rebuttal`` carries ``min_length=1``
  on that field, and handing that constraint to a model reproduces the failure already recorded in
  DECISIONS.md, where a ``min_length`` on ``cpt_codes`` taught it to invent procedure codes. Here
  it would invent a span id — the worst thing an appeal could contain, because a payer who checks
  one citation and finds nothing dismisses the whole letter.

The argument is the model's, and even there the prompt forbids quoting anything not put in front
of it. A misquoted record hands the payer a reason to discard the appeal unread.

**A criterion with no verified evidence gets no rebuttal.** You cannot argue a point you cannot
evidence, so this raises rather than producing a confident-sounding paragraph with nothing behind
it. If the payer contests something our own matcher found INSUFFICIENT, that is a conversation
with the practice, not an argument with the payer.
"""

from __future__ import annotations

from pydantic import Field
from strands import Agent

from attest.cache import cached_structured
from attest.llm import build_model, with_retry
from attest.models import Base, ContestedCriterion, CriteriaCoverage, EvidenceSpan, Rebuttal
from attest.policies.schema import Criterion, PolicyPack

SYSTEM_PROMPT = """You write appeal letters contesting health-insurer denials of prior
authorization.

For each criterion the payer disputed, write one paragraph arguing that the clinical record does
satisfy it.

Rules, in order of importance:
- Argue only from the evidence supplied to you. You are given the exact quotes from the note that
  a verifier has already confirmed. Nothing else from the record is available to you, and you must
  not imply facts beyond them.
- If you put a passage in quotation marks, it must be copied character-for-character from the
  evidence quotes or from the payer's own criterion text supplied to you. Never quote anything
  else. A misquoted record lets the payer dismiss the entire appeal.
- Address the payer's stated reason directly. They said the documentation does not establish
  something; show where it does.
- Be specific and factual. Cite dates, doses, durations and scores where the evidence gives them.
  Do not editorialise, do not appeal to sympathy, and do not speculate about the payer's motives.
- Write in the practice's voice, addressed to the payer's reviewer. No salutation or sign-off -
  the surrounding letter supplies those.
"""


class NoEvidenceError(RuntimeError):
    """A contested criterion carries no verified evidence, so no rebuttal can be made for it."""


class DraftArgument(Base):
    criterion_id: str
    argument: str = Field(description="One paragraph arguing the record satisfies this criterion.")


class DraftArguments(Base):
    arguments: list[DraftArgument] = Field(default_factory=list)


def _verified_spans(coverage: CriteriaCoverage, criterion_id: str) -> list[EvidenceSpan]:
    return [
        s
        for v in coverage.verdicts
        if v.criterion_id == criterion_id
        for s in v.spans
        if s.verified
    ]


def _criterion(pack: PolicyPack, criterion_id: str) -> Criterion:
    for c in pack.criteria:
        if c.id == criterion_id:
            return c
    raise KeyError(
        f"criterion {criterion_id!r} is not in pack {pack.pack_id!r}; a rebuttal citing it would "
        "quote a policy section that does not exist"
    )


def _render(contested: ContestedCriterion, criterion: Criterion, spans: list[EvidenceSpan]) -> str:
    quotes = "\n".join(f'  - "{s.quote}"' for s in spans)
    return (
        f"CRITERION {criterion.id} ({criterion.source_section}):\n"
        f"{criterion.text}\n\n"
        f"THE PAYER'S STATED REASON:\n{contested.payer_reason}\n\n"
        f"VERIFIED EVIDENCE FROM THE NOTE (the only evidence you may use):\n{quotes}\n"
    )


def _assemble(
    contested: ContestedCriterion,
    coverage: CriteriaCoverage,
    pack: PolicyPack,
    argument: str,
) -> Rebuttal:
    criterion = _criterion(pack, contested.criterion_id)
    spans = _verified_spans(coverage, contested.criterion_id)
    return Rebuttal(
        criterion_id=criterion.id,
        argument=argument.strip(),
        policy_citation=criterion.source_section,
        supporting_span_ids=[s.span_id for s in spans],
    )


def _prepare(
    contested: list[ContestedCriterion], coverage: CriteriaCoverage, pack: PolicyPack
) -> list[tuple[ContestedCriterion, Criterion, list[EvidenceSpan]]]:
    prepared = []
    for item in contested:
        criterion = _criterion(pack, item.criterion_id)
        spans = _verified_spans(coverage, item.criterion_id)
        if not spans:
            raise NoEvidenceError(
                f"criterion {item.criterion_id!r} was contested by the payer but carries no "
                "verified evidence, so there is nothing to argue from. This is a question for the "
                "practice, not an argument with the payer."
            )
        prepared.append((item, criterion, spans))
    return prepared


def draft_rebuttals(
    contested: list[ContestedCriterion], coverage: CriteriaCoverage, pack: PolicyPack
) -> list[Rebuttal]:
    """One rebuttal per contested criterion, in a single model call.

    Batched for the same reason matching is: the paragraphs are read together, and a model shown
    one objection at a time repeats itself across them.
    """
    prepared = _prepare(contested, coverage, pack)
    blocks = "\n\n".join(_render(i, c, s) for i, c, s in prepared)

    prompt = (
        f"PAYER: {pack.payer} ({pack.plan})\n"
        f"POLICY: {pack.pack_id}\n\n"
        f"{blocks}\n"
        "Write one argument for every criterion id above."
    )

    def produce() -> DraftArguments:
        agent = Agent(model=build_model("reasoning"), system_prompt=SYSTEM_PROMPT)
        return with_retry(
            lambda: agent(prompt, structured_output_model=DraftArguments)
        ).structured_output

    draft = cached_structured(
        "rebuttal", "reasoning", SYSTEM_PROMPT + prompt, DraftArguments, produce
    )
    by_id = {a.criterion_id: a.argument for a in draft.arguments}

    rebuttals: list[Rebuttal] = []
    for item, criterion, _ in prepared:
        argument = by_id.get(criterion.id, "").strip()
        if not argument:
            raise NoEvidenceError(
                f"no argument was drafted for contested criterion {criterion.id!r}. A contested "
                "criterion left unrebutted is the one the payer denies on again."
            )
        rebuttals.append(_assemble(item, coverage, pack, argument))

    return rebuttals


def draft_rebuttal(
    contested: ContestedCriterion, coverage: CriteriaCoverage, pack: PolicyPack
) -> Rebuttal:
    """Draft one rebuttal. Kept for re-drafting a single criterion after new documentation."""
    return draft_rebuttals([contested], coverage, pack)[0]
