"""Assemble the appeal: the deadline, and the check that every objection is answered.

**The deadline is read from the pack, never assumed.** The two shipped packs disagree — Highmark
allows 60 days and PacificSource 180 — so a constant would be wrong half the time and silently so.
A miscomputed appeal window is an appeal that never happens.

**Neither payer's policy actually states a window.** Both packs say so in `appeal_window_source`,
and `PolicyPack` gives the reason plainly: an invented deadline on an appeal is worse than no
deadline. This module computes the date; `emit.py` is responsible for printing the source next to
it, so a practice can tell a policy-stated deadline from our placeholder without opening the pack.

**Every contested criterion must be answered.** An appeal that rebuts two of three objections is
denied on the third, and the practice will not know why until the second denial arrives.
"""

from __future__ import annotations

from datetime import date, timedelta

from attest.models import Appeal, Denial, Rebuttal
from attest.policies.schema import PolicyPack


def appeal_deadline(denial_date: date, pack: PolicyPack) -> date:
    """The last day an appeal can be filed: the determination date plus the pack's window.

    Read from `pack.appeal_window_days` rather than hardcoded, because payers differ and being
    wrong in the generous direction is just as bad — it produces an appeal filed after the window
    closed, which is indistinguishable from not appealing at all.
    """
    return denial_date + timedelta(days=pack.appeal_window_days)


def build_appeal(
    denial: Denial,
    rebuttals: list[Rebuttal],
    pack: PolicyPack,
    *,
    appeal_id: str | None = None,
) -> Appeal:
    """Assemble an appeal from a parsed denial and its drafted rebuttals.

    Raises if any contested criterion has no rebuttal. Silently filing a partial appeal is the
    failure mode worth guarding: it looks complete, it is sent, and it is denied again on the
    objection nobody answered.

    `unmapped_reasons` are carried through from the denial so they reach the document. They are
    not rebutted — nothing in the clinical record speaks to them — but the practice has to be told
    the payer raised them, or it will fix the clinical objections and be denied for the same
    administrative one.
    """
    answered = {r.criterion_id for r in rebuttals}
    unanswered = [c.criterion_id for c in denial.contested if c.criterion_id not in answered]
    if unanswered:
        raise ValueError(
            f"contested criteria {unanswered} have no rebuttal. An appeal that answers only some "
            "objections is denied on the rest, and the practice does not find out until the "
            "second denial."
        )

    deadline = appeal_deadline(denial.denial_date, pack)

    return Appeal(
        appeal_id=appeal_id or f"{denial.case_id}-appeal-{deadline.isoformat()}",
        case_id=denial.case_id,
        denial_id=denial.denial_id,
        rebuttals=list(rebuttals),
        deadline=deadline,
        deadline_source=pack.appeal_window_source,
        unmapped_reasons=list(denial.unmapped_reasons),
    )
