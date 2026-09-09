"""Build the medical-necessity justification from verified evidence, and nothing else.

This is the document that argues the case to the payer, and it is the last place a fabricated
clinical claim could still reach paper. The defence here is structural rather than instructed:
a claim is *assembled from* spans the verifier confirmed, so there is no code path that produces
one without evidence. `build_justification` cannot emit an unsupported claim any more than it can
emit a claim about a criterion nobody matched.

**Deterministic, and deliberately so.** Three reasons, in order of weight:

1. It makes "every referenced span is verified" true by construction rather than by prompt.
2. ``Claim.supporting_span_ids`` carries ``min_length=1``. Handing that constraint to a model
   would pressure it into inventing a span id to satisfy the schema — the exact failure recorded
   in DECISIONS.md, where a ``min_length`` on ``cpt_codes`` made the model fabricate procedure
   codes. A constraint the model cannot satisfy honestly is a constraint that teaches it to lie.
3. It costs no quota, and the free tier allows 20 requests per day per model.

Only ``MET`` criteria become claims. INSUFFICIENT is a question for the practice and belongs in
the gap list; UNMET is a criterion the note shows is not satisfied, and arguing it would hand the
payer its own denial rationale.
"""

from __future__ import annotations

from attest.models import Case, Claim, CriteriaCoverage, Justification, Verdict
from attest.policies.loader import PACKS_DIR, load_pack
from attest.policies.schema import Criterion, PolicyPack


def _claim_text(pack: PolicyPack, criterion: Criterion, case: Case) -> str:
    """One assertion, in the payer's own words.

    The requirement is quoted verbatim rather than summarised, because the reviewer signing this
    off at Gate 1 is confirming that the record meets *that* bar, not a paraphrase of it. The
    evidence itself is not inlined here — it hangs off ``supporting_span_ids``, so the emitter
    renders each quote exactly once and always from the verified span.

    The patient's diagnosis is deliberately *not* repeated per claim: it is one fact about the
    case, and restating it on all ten claims reads as machine output. It belongs in the packet
    header, which P4-S3 emits once.
    """
    return (
        f"{pack.payer} {pack.plan} requires, at {criterion.source_section}: "
        f'"{criterion.text}". '
        f"The record documents this for the requested {case.service.service}."
    )


def build_justification(coverage: CriteriaCoverage, case: Case) -> Justification:
    """One claim per met criterion, each citing only spans the verifier confirmed.

    Claims follow the policy's order rather than the coverage's, because a reviewer reads this
    against the payer's own criteria list.

    A criterion whose evidence has not been through ``enforce_verification`` contributes nothing:
    spans default to ``verified=False``, so skipping enforcement yields an empty justification
    rather than an unverified one. That is the intended failure direction — an empty document is
    recoverable, an unsupported one is not.
    """
    if coverage.case_id != case.case_id:
        raise ValueError(
            f"coverage is for case {coverage.case_id!r} but the case is {case.case_id!r}; "
            "a justification built from another case's coverage would argue the wrong patient"
        )

    pack = load_pack(PACKS_DIR / f"{coverage.pack_id}.yaml")
    met = {v.criterion_id: v for v in coverage.verdicts if v.verdict == Verdict.MET}

    claims: list[Claim] = []
    for criterion in pack.criteria:
        verdict = met.get(criterion.id)
        if verdict is None:
            continue

        span_ids = [span.span_id for span in verdict.spans if span.verified]
        if not span_ids:
            continue  # nothing the verifier blessed — say nothing rather than assert it

        claims.append(
            Claim(text=_claim_text(pack, criterion, case), supporting_span_ids=span_ids)
        )

    return Justification(claims=claims)
