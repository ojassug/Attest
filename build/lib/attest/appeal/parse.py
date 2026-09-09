"""Turn a payer's denial letter into contested criteria the appeal can answer.

A denial letter is prose. Each paragraph either objects to a criterion the policy actually
contains — in which case the appeal can answer it with evidence — or it raises something the
clinical criteria do not cover, which the practice needs to hear about separately.

Two rules hold this together, and both are code rather than prompt:

**A criterion id the model proposes is not a criterion id until the pack agrees.** The model reads
the letter and suggests a mapping; `resolve_contested` checks every suggestion against the pack and
demotes anything it cannot find to an unmapped reason. This is the same discipline
`attest.verifier` applies to quotes: the model may point, but only our data confirms.

**No reason is ever dropped.** A payer reason that maps to no criterion is the one most likely to
sink a resubmission — a practice that never hears about it will fix the clinical criteria and be
denied again for the same third thing. Every reason ends up in exactly one of `contested` or
`unmapped_reasons`.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field
from strands import Agent

from attest.cache import cached_structured
from attest.llm import build_model, with_retry
from attest.models import Base, ContestedCriterion, Denial
from attest.policies.schema import PolicyPack

SYSTEM_PROMPT = """You read prior-authorization denial letters from health insurers.

Your job is to split the letter's stated reasons into individual objections, and for each one say
which of the payer's own policy criteria it disputes.

Rules:
- One entry per distinct reason the letter gives. Do not merge two reasons or invent a third.
- `reason` must be the payer's own wording, not a summary of it. It is quoted back to them.
- `criterion_id` must be one of the ids supplied to you, or an empty string. If a reason does not
  clearly dispute one of the listed criteria, return an empty string. An empty string is a correct
  and expected answer - it is far better than a wrong mapping, because a wrong mapping sends the
  appeal arguing something the payer never raised.
- Administrative or benefit-design objections (site of service, member eligibility, plan
  exclusions) usually map to no clinical criterion. Return an empty string for those.
- `denial_date` is the date the determination was issued, in YYYY-MM-DD form.
"""


class DraftReason(Base):
    reason: str = Field(description="The payer's own wording for this objection.")
    criterion_id: str = Field(
        default="",
        description="The disputed criterion id, or an empty string if it maps to none.",
    )


class DraftDenial(Base):
    denial_date: str = Field(description="Determination date, YYYY-MM-DD.")
    reasons: list[DraftReason] = Field(default_factory=list)


def resolve_contested(
    reasons: list[tuple[str, str]], pack: PolicyPack
) -> tuple[list[ContestedCriterion], list[str]]:
    """Check proposed criterion ids against the pack. Returns (contested, unmapped_reasons).

    Anything the pack does not contain is demoted to an unmapped reason rather than trusted, and
    nothing is discarded: `len(contested) + len(unmapped) == len(reasons)` always holds, except
    where two reasons dispute the same criterion, which is one contested criterion carrying both
    paragraphs.

    Contested criteria come back in the pack's order, because the appeal is read against the
    payer's own policy.
    """
    known = {c.id for c in pack.criteria}
    grouped: dict[str, list[str]] = {}
    unmapped: list[str] = []

    for criterion_id, reason in reasons:
        if criterion_id and criterion_id in known:
            grouped.setdefault(criterion_id, []).append(reason)
        else:
            unmapped.append(reason)

    contested = [
        ContestedCriterion(criterion_id=c.id, payer_reason="\n\n".join(grouped[c.id]))
        for c in pack.criteria
        if c.id in grouped
    ]
    return contested, unmapped


def parse_denial(
    text: str,
    pack: PolicyPack,
    *,
    case_id: str = "UNKNOWN",
    denial_id: str | None = None,
) -> Denial:
    """Parse a denial letter against the pack it was issued under.

    One model call for the whole letter: the reasons have to be split consistently, and a model
    shown one paragraph at a time cannot tell a second objection from a restatement of the first.
    """
    criteria = "\n".join(f"- {c.id}: {c.text}" for c in pack.criteria)
    prompt = (
        f"PAYER: {pack.payer} ({pack.plan})\n"
        f"POLICY: {pack.pack_id}\n\n"
        f"THE PAYER'S CRITERIA:\n{criteria}\n\n"
        f"DENIAL LETTER:\n{text}\n\n"
        "List every reason the letter gives for the denial."
    )

    def produce() -> DraftDenial:
        agent = Agent(model=build_model("reasoning"), system_prompt=SYSTEM_PROMPT)
        return with_retry(
            lambda: agent(prompt, structured_output_model=DraftDenial)
        ).structured_output

    draft = cached_structured("denial", "reasoning", SYSTEM_PROMPT + prompt, DraftDenial, produce)

    try:
        denial_date = date.fromisoformat(draft.denial_date.strip())
    except ValueError as exc:
        raise ValueError(
            f"could not read a determination date from the letter (got "
            f"{draft.denial_date!r}). The appeal deadline is computed from it, so a wrong or "
            "missing date is a missed appeal - it must not be guessed at."
        ) from exc

    contested, unmapped = resolve_contested(
        [(r.criterion_id.strip(), r.reason.strip()) for r in draft.reasons], pack
    )

    return Denial(
        denial_id=denial_id or f"{case_id}-denial-{denial_date.isoformat()}",
        case_id=case_id,
        denial_date=denial_date,
        contested=contested,
        unmapped_reasons=unmapped,
    )
