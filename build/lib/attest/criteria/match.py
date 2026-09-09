"""Check a clinical note against a payer's criteria, one verdict per criterion.

This is the heart of the product. Three things it must get right, in order of how badly they fail:

1. **Quote verbatim.** Every verdict carries spans copied character-for-character from the note.
   `attest.verifier` rejects anything else, so a paraphrase becomes a rejected span and the
   criterion degrades. Paraphrase is the failure mode, not a stylistic preference.

2. **Distinguish UNMET from INSUFFICIENT.** UNMET means the note shows the requirement is *not*
   satisfied — four weeks where eight are required. INSUFFICIENT means the note does not say
   enough to tell. They lead to opposite actions: an unmet criterion is an argument to have with
   the payer, an insufficient one is a question to ask the practice.

3. **Respect polarity.** A contraindication is satisfied by *absence*. "No history of seizure
   disorder" MEETS the seizure criterion. Silence does not — that is INSUFFICIENT, because an
   undocumented contraindication is unknown, not ruled out.

All criteria for a case go in one call rather than one call each. That is not only a quota
concession: several policies phrase requirements as "ANY ONE of the following", which cannot be
judged correctly by a model that can only see one branch at a time.
"""

from __future__ import annotations

from pydantic import Field
from strands import Agent

from attest.cache import cached_structured
from attest.llm import build_model, with_retry
from attest.models import (
    Base,
    Criterion,
    CriteriaCoverage,
    CriterionVerdict,
    EvidenceSpan,
    Polarity,
    Verdict,
)
from attest.policies.schema import PolicyPack

SYSTEM_PROMPT = """\
You check a clinical note against a health insurer's published coverage criteria. For each
criterion you return a verdict, the evidence from the note, and your reasoning.

VERDICTS
- "met": the note establishes the criterion is satisfied.
- "unmet": the note establishes the criterion is NOT satisfied. Use this only when the note
  contains positive evidence of failure - for example a required 8-week trial documented as
  lasting 4 weeks.
- "insufficient": the note does not say enough to decide. Use this when the relevant fact is
  absent, vague, or stated without the detail the criterion requires.

The difference between "unmet" and "insufficient" matters enormously. "unmet" starts an argument
with the insurer. "insufficient" asks the practice a question. Never report "insufficient" as
"unmet", and never guess in order to avoid saying "insufficient".

POLARITY
Each criterion has a polarity.
- polarity "present": the note must show the thing IS true.
- polarity "absent": this is a contraindication or exclusion. The criterion is "met" when the
  note documents that the finding is ABSENT - for example "No history of seizure disorder" meets
  a seizure-disorder exclusion. If the note is simply silent about it, that is "insufficient",
  not "met": an undocumented contraindication is unknown, not ruled out.

EVIDENCE - THIS IS THE CRITICAL RULE
Every quote you return must be copied from the note CHARACTER FOR CHARACTER. Copy an exact,
contiguous run of text. Do not paraphrase, summarise, reword, correct, translate, join separate
sentences, or add ellipses. Quotes are checked programmatically against the note and any quote
that does not appear verbatim is discarded, which will degrade your verdict.

Prefer several short exact quotes over one long approximate one. If a criterion depends on facts
in a table, quote the table rows verbatim.

Return no quotes at all rather than an inexact one. A verdict of "insufficient" with no quotes is
correct and useful; a "met" propped up by an invented quote is harmful.

REASONING
State plainly what the note shows and how it maps to the criterion's requirement. Where the
criterion sets a numeric bar - a dose, a duration, a count - say what the note documents and
whether it clears the bar. Where the criterion offers alternatives ("ANY ONE of the following"),
name which branch is satisfied.
"""


class DraftVerdict(Base):
    """What the model returns. No span ids or note ids — those are ours to assign."""

    criterion_id: str = Field(description="The id of the criterion being judged.")
    verdict: Verdict
    quotes: list[str] = Field(
        default_factory=list,
        description="Exact verbatim excerpts from the note. Empty is valid and preferred to an inexact quote.",
    )
    reasoning: str = Field(description="How the note maps to this criterion's requirement.")


class DraftCoverage(Base):
    verdicts: list[DraftVerdict] = Field(description="Exactly one verdict per criterion supplied.")


def _render_criteria(criteria: list[Criterion]) -> str:
    lines = []
    for c in criteria:
        sense = (
            "must be ABSENT (contraindication)"
            if c.polarity is Polarity.ABSENT
            else "must be PRESENT"
        )
        lines.append(f"- id: {c.id}\n  polarity: {sense}\n  criterion: {c.text}")
    return "\n".join(lines)


def _to_verdict(draft: DraftVerdict, note_id: str) -> CriterionVerdict:
    spans = [
        EvidenceSpan(span_id=f"{draft.criterion_id}-{i}", note_id=note_id, quote=q)
        for i, q in enumerate(draft.quotes)
        if q and q.strip()
    ]
    return CriterionVerdict(
        criterion_id=draft.criterion_id,
        verdict=draft.verdict,
        spans=spans,
        reasoning=draft.reasoning,
    )


def match_all(pack: PolicyPack, note: str, *, case_id: str, note_id: str = "note") -> CriteriaCoverage:
    """Judge every criterion in a pack against a note, in a single call."""
    prompt = (
        f"PAYER: {pack.payer} ({pack.plan})\n"
        f"SERVICE: {pack.service}\n\n"
        f"CRITERIA TO CHECK:\n{_render_criteria(pack.criteria)}\n\n"
        f"CLINICAL NOTE:\n{note}\n\n"
        "Return exactly one verdict for every criterion id listed above."
    )

    def produce() -> DraftCoverage:
        agent = Agent(model=build_model("reasoning"), system_prompt=SYSTEM_PROMPT)
        return with_retry(
            lambda: agent(prompt, structured_output_model=DraftCoverage)
        ).structured_output

    draft = cached_structured("match", "reasoning", SYSTEM_PROMPT + prompt, DraftCoverage, produce)

    by_id = {d.criterion_id: d for d in draft.verdicts}
    verdicts: list[CriterionVerdict] = []

    for criterion in pack.criteria:
        drafted = by_id.get(criterion.id)
        if drafted is None:
            # A skipped criterion must never read as satisfied. Absence of a judgment is
            # exactly the "we do not know" case.
            verdicts.append(
                CriterionVerdict(
                    criterion_id=criterion.id,
                    verdict=Verdict.INSUFFICIENT,
                    spans=[],
                    reasoning=(
                        "No verdict was produced for this criterion, so it has not been "
                        "assessed. Treated as insufficient rather than met."
                    ),
                )
            )
            continue
        verdicts.append(_to_verdict(drafted, note_id))

    return CriteriaCoverage(case_id=case_id, pack_id=pack.pack_id, verdicts=verdicts)


def match_criterion(criterion: Criterion, note: str, *, note_id: str = "note") -> CriterionVerdict:
    """Judge a single criterion. Used for re-checking one criterion after a practice replies."""
    prompt = (
        f"CRITERIA TO CHECK:\n{_render_criteria([criterion])}\n\n"
        f"CLINICAL NOTE:\n{note}\n\n"
        "Return exactly one verdict."
    )

    def produce() -> DraftCoverage:
        agent = Agent(model=build_model("reasoning"), system_prompt=SYSTEM_PROMPT)
        return with_retry(
            lambda: agent(prompt, structured_output_model=DraftCoverage)
        ).structured_output

    draft = cached_structured("match", "reasoning", SYSTEM_PROMPT + prompt, DraftCoverage, produce)
    for d in draft.verdicts:
        if d.criterion_id == criterion.id:
            return _to_verdict(d, note_id)
    return _to_verdict(
        DraftVerdict(
            criterion_id=criterion.id,
            verdict=Verdict.INSUFFICIENT,
            quotes=[],
            reasoning="No verdict was produced for this criterion.",
        ),
        note_id,
    )
