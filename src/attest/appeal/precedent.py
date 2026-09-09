"""Reuse language from appeals a clinician already signed off on.

`Attest-PRODUCT.md` §4.9: the product "reuses language from prior successful appeals on similar
future denials". This is that — the practice stops rebuilding every appeal from scratch, which is
one of the reasons §2 gives for appeals being under-used.

**Approved is the bar, and the hash is what enforces it.** An appeal becomes precedent only if it
carries an `ApprovalRecord` whose hash still matches its content. Presence of a record alone would
mean an appeal could be approved, then edited, and the edited language offered to the next case as
though a clinician had signed it — laundering unapproved text into a future document through the
back door. The same reasoning that makes `content_hash` load-bearing at both gates makes it
load-bearing here.

**"Approved" is not "successful", and this module does not pretend otherwise.** We know a human
signed the appeal; we do not know the payer overturned the denial, because nothing tracks outcomes
yet. So precedent is offered as *language a clinician has already approved for this criterion* and
never as a winning template. Recording the payer's response is the field this would need, and it is
deliberately not invented here — see DECISIONS.md.

**There is no precedent index.** This reads the case store directly. An index would be a second
source of truth that can disagree with the approved appeals it indexes, and the disagreement would
surface as an appeal citing language nobody approved.
"""

from __future__ import annotations

from pathlib import Path

from attest.gates import content_hash
from attest.models import Appeal, Rebuttal
from attest.store import STORE_DIR, list_cases, load_appeal


def is_precedent(appeal: Appeal) -> bool:
    """True if a clinician approved this exact appeal, and it has not changed since.

    Split out from `find_precedents` because it is the whole safety rule of this module, and a
    caller displaying a stored appeal needs to be able to ask the same question.
    """
    approval = appeal.approval
    if approval is None:
        return False
    return approval.content_hash == content_hash(appeal)


def find_precedents(criterion_id: str, store_dir: Path | str = STORE_DIR) -> list[Appeal]:
    """Approved appeals that argued this criterion, most recently approved first.

    Ordering is by approval time descending: payer policies churn, so the language a clinician
    approved most recently is the language most likely to still fit. `appeal_id` breaks ties so the
    result is stable rather than dependent on how the store happened to enumerate.
    """
    found = []

    for case_id in list_cases(store_dir):
        appeal = load_appeal(case_id, store_dir)
        if appeal is None or not is_precedent(appeal):
            continue
        if any(r.criterion_id == criterion_id for r in appeal.rebuttals):
            found.append(appeal)

    # `approval` is non-None on everything here — is_precedent already required it.
    return sorted(found, key=lambda a: (a.approval.approved_at, a.appeal_id), reverse=True)


def precedent_rebuttals(criterion_id: str, store_dir: Path | str = STORE_DIR) -> list[Rebuttal]:
    """The approved arguments themselves, for the criterion asked about.

    `find_precedents` returns whole appeals because that is what the Definition of Done specifies
    and because provenance matters — a reader should be able to see which case an argument came
    from. But the thing actually reused is the rebuttal, and making every caller re-filter
    `appeal.rebuttals` invites one of them to forget and offer an argument for a different
    criterion.
    """
    return [
        rebuttal
        for appeal in find_precedents(criterion_id, store_dir)
        for rebuttal in appeal.rebuttals
        if rebuttal.criterion_id == criterion_id
    ]
