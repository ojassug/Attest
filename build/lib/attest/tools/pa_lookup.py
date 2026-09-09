"""Prior-authorization requirement lookup.

Deterministic. No model call — this is a policy-index lookup, and asking a model to guess whether
a payer requires authorization would be both slower and wrong.

The load-bearing design decision is the three-state answer. "We found no policy" is reported as
``UNKNOWN``, never as ``NOT_REQUIRED``. Telling a practice that no authorization is needed because
we failed to find a policy causes an unreimbursed service, which is the most expensive mistake
this tool could make.
"""

from __future__ import annotations

from attest.models import PADetermination, PARequirement
from attest.policies.loader import find_pack


def check_pa_required(cpt: str, payer: str, plan: str | None = None) -> PADetermination:
    """Whether prior authorization is required for a CPT code under a payer's plan.

    Always returns a citation when a policy was found, because the practice needs to be able to
    check the answer against the source rather than take it on trust.
    """
    pack = find_pack(cpt=cpt, payer=payer, plan=plan)

    if pack is None:
        where = f"{payer}" + (f" / {plan}" if plan else "")
        return PADetermination(
            requirement=PARequirement.UNKNOWN,
            rationale=(
                f"No policy on file covering CPT {cpt} for {where}. This is not evidence that "
                f"prior authorization is unnecessary - it means we cannot tell. Confirm directly "
                f"with the payer before delivering the service."
            ),
        )

    requirement = PARequirement.REQUIRED if pack.pa_required else PARequirement.NOT_REQUIRED
    verb = "requires" if pack.pa_required else "does not require"

    return PADetermination(
        requirement=requirement,
        policy_id=pack.pack_id,
        citation=f"{pack.source_title} — {pack.source_url}",
        rationale=(
            f"{pack.payer} ({pack.plan}) {verb} prior authorization for {pack.service}. "
            f"CPT {cpt} is listed in that policy."
        ),
    )
