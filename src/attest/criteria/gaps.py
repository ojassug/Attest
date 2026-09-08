"""Turn the criteria that could not be evaluated into questions for the practice.

The distinction this module turns on is INSUFFICIENT versus UNMET, and it decides who gets asked:

* **INSUFFICIENT** — the note does not say enough to tell. That is a question for the practice,
  and it is what becomes a gap.
* **UNMET** — the note shows the requirement is genuinely not satisfied. That is an argument to
  have with the payer, and it is deliberately *not* a gap. Asking a practice to document
  something the record shows is absent sends them chasing a document that cannot exist.

Nothing here calls a model. The matcher already worked out precisely what each note failed to
establish, and its reasoning is carried straight through as ``missing`` — more specific than any
template could manage, and free, which matters against a 20-request-per-day ceiling.

A gap never guesses at the answer. It states the payer's requirement verbatim, says what the note
failed to establish, and asks.
"""

from __future__ import annotations

from attest.models import CriteriaCoverage, GapItem, Verdict
from attest.policies.loader import PACKS_DIR, load_pack
from attest.policies.schema import Criterion, PolicyPack


def _question(pack: PolicyPack, criterion: Criterion) -> str:
    """A question addressed to the practice, quoting the bar it is measured against.

    The requirement is quoted verbatim rather than summarised: the practice is being asked to
    satisfy the payer's words, and a paraphrase of a payer requirement is how the wrong document
    gets pulled.
    """
    return (
        f"{pack.payer} requires, at {criterion.source_section}: "
        f'"{criterion.text}". '
        f"The note does not establish this. Can you supply the supporting documentation from the "
        f"chart, or confirm that it is not recorded?"
    )


def build_gap_list(coverage: CriteriaCoverage) -> list[GapItem]:
    """One question per criterion the note could not answer, in the policy's own order.

    Ordered by the pack rather than by the coverage because the practice reads this as a
    checklist against the policy. Raises if the pack or a criterion cannot be resolved — a gap
    list built against the wrong pack would quote one payer's requirements at another.
    """
    pack = load_pack(PACKS_DIR / f"{coverage.pack_id}.yaml")
    by_id = {c.id: c for c in pack.criteria}

    insufficient = {
        v.criterion_id: v for v in coverage.verdicts if v.verdict == Verdict.INSUFFICIENT
    }

    unknown = set(insufficient) - set(by_id)
    if unknown:
        raise KeyError(
            f"criteria {sorted(unknown)} are not in pack {pack.pack_id!r}; "
            "the coverage and the pack disagree"
        )

    return [
        GapItem(
            criterion_id=criterion.id,
            missing=insufficient[criterion.id].reasoning,
            question=_question(pack, criterion),
        )
        for criterion in pack.criteria
        if criterion.id in insufficient
    ]
