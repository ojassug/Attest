"""Attest — the reviewer's console.

The office manager's screen. Everything the engine produces is shown here in the order a human
would actually work through it: read the note, decide whether a prior authorization is needed,
check the payer's criteria against the record, see what is missing, approve, send. Then the same
again for a denial.

Two rules shape this file, and both come from `Attest-PRODUCT.md` §6:

**The gates are not UI logic, so this file must not be able to weaken them.** Approving here builds
a real `ApprovalRecord` and calls the same `emit_*_artifact` functions the tests exercise. There is
no UI-side path to a document. If someone deleted this file, the gates would be exactly as strong.

**Nothing is shown as fact that the verifier did not confirm.** Every quote on this page carries the
verifier's own verdict; unverifiable ones were already stripped from the coverage before it got
here, and their criterion downgraded to INSUFFICIENT.

The app runs offline from committed cassettes, so a judge with no API key sees the same results.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from attest.appeal.assemble import build_appeal
from attest.appeal.draft import draft_rebuttals
from attest.appeal.parse import parse_denial
from attest.appeal.precedent import find_precedents
from attest.agents.intake import extract_case
from attest.appeal.emit import emit_appeal_artifact
from attest.corpus import CASE_NAMES, load_case
from attest.criteria.gaps import build_gap_list
from attest.criteria.match import match_all
from attest.gates import content_hash
from attest.models import ApprovalRecord, Packet, Verdict
from attest.packet.emit import ARTIFACT_NAME, PDF_NAME, emit_submission_artifact
from attest.packet.justification import build_justification
from attest.store import list_cases, save_appeal, save_case
from attest.tools.pa_lookup import check_pa_required
from attest.verifier import enforce_verification

# Same reason as `attest.store.STORE_DIR`: the UI tests must not write into the repo, and a hosted
# deploy has an ephemeral filesystem.
OUT_ROOT = Path(os.environ.get("ATTEST_OUT_DIR", "out"))

VERDICT_STYLE = {
    Verdict.MET: ("✅", "Met"),
    Verdict.UNMET: ("❌", "Not met"),
    Verdict.INSUFFICIENT: ("⚠️", "Insufficiently documented"),
}

st.set_page_config(page_title="Attest — prior authorization", page_icon="🩺", layout="wide")


# --------------------------------------------------------------------------- state

# Seeded explicitly rather than left to the radio's `key`. A widget only populates session state
# once it has rendered, so every read before that point would fail — including the import that
# `test_app_imports_without_error` performs.
st.session_state.setdefault("case_name", CASE_NAMES[0])


def case_state() -> dict:
    """Per-case scratch space. Switching cases must never show another case's results."""
    name = st.session_state.case_name
    return st.session_state.setdefault("results", {}).setdefault(name, {})


def reset_case() -> None:
    st.session_state.setdefault("results", {}).pop(st.session_state.case_name, None)


# ------------------------------------------------------------------------- sidebar

with st.sidebar:
    st.title("🩺 Attest")
    st.caption("Prior authorization, end to end — for practices without PA staff.")

    st.radio(
        "Demo case",
        CASE_NAMES,
        key="case_name",
        format_func=lambda n: {
            "clean": "Fully documented",
            "gap": "Missing documentation",
            "denial": "Denied → appeal",
        }[n],
    )

    expected = load_case(st.session_state.case_name)
    st.caption(expected.raw["description"])

    st.divider()
    st.subheader("Open cases")
    stored = list_cases()
    if stored:
        for case_id in stored:
            st.write(f"`{case_id}`")
    else:
        st.caption("None yet. Running a case files it here.")

    st.divider()
    st.warning(
        "**Synthetic data only.** Every note and denial letter in this demo is fabricated. "
        "No real patient information is used anywhere in Attest.",
        icon="⚠️",
    )
    if st.button("Reset this case", use_container_width=True):
        reset_case()
        st.rerun()


# ---------------------------------------------------------------------------- head

state = case_state()
pack = expected.pack

st.title("Prior authorization review")
st.caption(
    f"**{pack.payer}** · {pack.plan} · {pack.service} — criteria from "
    f"[{pack.source_title}]({pack.source_url}), retrieved {pack.retrieved_date}"
)

with st.expander("The clinical note", expanded=False):
    st.markdown(expected.note_text)


# ------------------------------------------------------- 1 & 2 · intake and PA need

st.header("1 · Read the note and decide whether a PA is needed")

if "case" not in state:
    if st.button("Run intake", type="primary"):
        with st.spinner("Reading the note…"):
            state["case"] = extract_case(expected.note_text, case_id=expected.case_id)
            save_case(state["case"])
        st.rerun()

if "case" in state:
    case = state["case"]
    left, right = st.columns(2)

    with left:
        st.subheader("What the note says")
        st.write(f"**Patient:** {case.patient_ref}")
        st.write(f"**Service:** {case.service.service}")
        st.write(f"**CPT:** {', '.join(case.service.cpt_codes)}")
        st.write(f"**Diagnosis:** {case.primary_diagnosis_code} — {case.primary_diagnosis_text}")
        st.write(f"**Coverage:** {case.insurance.payer} · {case.insurance.plan}")

    with right:
        st.subheader("Prior authorization")
        determination = check_pa_required(
            case.service.cpt_codes[0], case.insurance.payer, case.insurance.plan
        )
        # UNKNOWN is deliberately not styled as a negative. "We could not find a policy" must never
        # read to a practice as "no authorization needed" - that is what causes an unpaid service.
        {"required": st.error, "not_required": st.success, "unknown": st.warning}[
            determination.requirement.value
        ](f"**{determination.requirement.value.replace('_', ' ').title()}** — {determination.rationale}")
        if determination.citation:
            st.caption(f"Policy {determination.policy_id} · {determination.citation}")


# ------------------------------------------------------------- 3 · criteria coverage

if "case" in state:
    st.header("2 · Check the record against the payer's criteria")

    if "coverage" not in state:
        if st.button("Match criteria", type="primary"):
            with st.spinner("Reading each criterion against the note…"):
                raw = match_all(pack, expected.note_text, case_id=expected.case_id)
                # The verifier runs before anything is displayed, not after. A quote that cannot be
                # found verbatim in the note never reaches this screen at all.
                state["verified"] = enforce_verification(raw, expected.note_text)
                state["coverage"] = state["verified"].coverage
            st.rerun()

    if "coverage" in state:
        coverage = state["coverage"]
        report = state["verified"].report
        by_id = {c.id: c for c in pack.criteria}

        met = sum(1 for v in coverage.verdicts if v.verdict is Verdict.MET)
        spans = [s for v in coverage.verdicts for s in v.spans]

        a, b, c = st.columns(3)
        a.metric("Criteria met", f"{met}/{len(coverage.verdicts)}")
        b.metric("Evidence quotes", len(spans))
        c.metric(
            "Verified verbatim",
            f"{sum(1 for s in spans if s.verified)}/{len(spans)}",
            help="Every quote is checked character by character against the note before it may "
            "enter any document. Paraphrase is rejected on purpose.",
        )

        if report.rejected:
            st.error(
                f"{len(report.rejected)} quote(s) could not be found in the note and were removed. "
                "Their criteria were downgraded to insufficiently documented.",
                icon="🚫",
            )

        for verdict in coverage.verdicts:
            criterion = by_id[verdict.criterion_id]
            icon, label = VERDICT_STYLE[verdict.verdict]

            with st.expander(f"{icon} **{criterion.id}** — {criterion.text}", expanded=False):
                st.caption(f"{label} · {criterion.category} · policy {criterion.source_section}")
                st.write(verdict.reasoning)

                if verdict.spans:
                    st.markdown("**Evidence from the note**")
                    for span in verdict.spans:
                        mark = "✓ verified verbatim" if span.verified else "unverified"
                        st.markdown(f"> {span.quote}")
                        st.caption(f"{mark} · characters {span.start}–{span.end} of the note")
                else:
                    st.caption("No supporting evidence found in the note.")


# ----------------------------------------------------------------------- 4 · the gaps

if "coverage" in state:
    gaps = build_gap_list(state["coverage"])

    st.header("3 · What the practice still needs to supply")
    if gaps:
        st.info(
            "These criteria are not *unmet* — the record does not say enough to tell. "
            "Each is a question for the practice, not an argument with the payer.",
            icon="📋",
        )
        for gap in gaps:
            st.markdown(f"**{gap.criterion_id}** — {gap.missing}")
            st.markdown(f"> {gap.question}")
    else:
        st.success("Nothing outstanding. Every criterion is documented.", icon="✅")


# --------------------------------------------------------------- 5 · packet + Gate 1

if "coverage" in state:
    st.header("4 · Approve the submission")

    packet = Packet(
        case_id=state["case"].case_id,
        coverage=state["coverage"],
        justification=build_justification(state["coverage"], state["case"]),
        gaps=build_gap_list(state["coverage"]),
    )

    st.subheader("Medical-necessity justification")
    st.caption(
        "Assembled, not written. One claim per met criterion, each citing only spans the verifier "
        "confirmed — so there is no code path that can produce an unsupported sentence."
    )
    for claim in packet.justification.claims:
        st.markdown(f"- {claim.text}  \n  *{', '.join(claim.supporting_span_ids)}*")

    st.divider()
    st.subheader("🔒 Gate 1 — clinician approval")
    st.caption(
        "Nothing is submitted until a named clinician approves this exact content. The approval "
        "stores a hash of it, so editing the packet afterwards invalidates the approval rather "
        "than riding on it."
    )

    approver = st.text_input("Approving clinician", key="gate1_approver", placeholder="Dr. …")

    if st.button("Approve and generate submission", type="primary", disabled=not approver.strip()):
        approved = packet.model_copy(
            update={
                "approval": ApprovalRecord(
                    approver=approver.strip(),
                    approved_at=datetime.now(timezone.utc),
                    content_hash=content_hash(packet),
                )
            }
        )
        out = OUT_ROOT / packet.case_id
        emit_submission_artifact(approved, out)
        state["submission"] = out
        st.rerun()

    if "submission" in state:
        out = state["submission"]
        st.success("Submission packet approved and generated.", icon="✅")
        d1, d2 = st.columns(2)
        d1.download_button(
            "Download submission (Markdown)",
            (out / ARTIFACT_NAME).read_text(encoding="utf-8"),
            file_name=f"{packet.case_id}-{ARTIFACT_NAME}",
            use_container_width=True,
        )
        d2.download_button(
            "Download submission (PDF)",
            (out / PDF_NAME).read_bytes(),
            file_name=f"{packet.case_id}-{PDF_NAME}",
            use_container_width=True,
        )


# ------------------------------------------------------------ 6 · denial and Gate 2

denial_text = expected.denial_text

if "coverage" in state and denial_text:
    st.header("5 · The payer denied it")

    with st.expander("The denial letter", expanded=False):
        st.markdown(denial_text)

    if "appeal" not in state:
        if st.button("Draft the appeal", type="primary"):
            with st.spinner("Reading the denial and building the rebuttals…"):
                denial = parse_denial(denial_text, pack, case_id=state["case"].case_id)
                rebuttals = draft_rebuttals(denial.contested, state["coverage"], pack)
                state["denial"] = denial
                state["appeal"] = build_appeal(denial, rebuttals, pack)
            st.rerun()

    if "appeal" in state:
        appeal = state["appeal"]
        denial = state["denial"]

        st.subheader("What the payer contests")
        for contested in denial.contested:
            st.markdown(f"**{contested.criterion_id}** — {contested.payer_reason}")

        if denial.unmapped_reasons:
            st.warning(
                "**Raised but outside the clinical criteria.** These map to no criterion in the "
                "policy, so they are not rebutted below and need a separate response:\n\n"
                + "\n".join(f"- {r}" for r in denial.unmapped_reasons),
                icon="📌",
            )

        st.subheader("The rebuttals")
        for rebuttal in appeal.rebuttals:
            with st.expander(f"**{rebuttal.criterion_id}** — {rebuttal.policy_citation}", expanded=True):
                st.write(rebuttal.argument)
                st.caption(f"Cites verified evidence: {', '.join(rebuttal.supporting_span_ids)}")

                # Precedent reuse: language a clinician already signed off on for this criterion.
                # Approved, not known-successful - nothing tracks payer outcomes yet.
                precedents = find_precedents(rebuttal.criterion_id)
                if precedents:
                    st.markdown("**Previously approved language for this criterion**")
                    for prior in precedents:
                        for prior_rebuttal in prior.rebuttals:
                            if prior_rebuttal.criterion_id == rebuttal.criterion_id:
                                st.caption(
                                    f"From appeal {prior.appeal_id} · approved by "
                                    f"{prior.approval.approver}"
                                )
                                st.markdown(f"> {prior_rebuttal.argument}")

        st.info(
            f"**Appeal deadline: {appeal.deadline.isoformat()}** — "
            f"{pack.appeal_window_days} days from the determination. "
            f"Window source: {appeal.deadline_source}",
            icon="📅",
        )

        st.divider()
        st.subheader("🔒 Gate 2 — clinician approval")
        st.caption(
            "The same gate again, on the appeal letter. An approval for one document can never "
            "authorise another: the hash covers the case id."
        )

        appeal_approver = st.text_input(
            "Approving clinician", key="gate2_approver", placeholder="Dr. …"
        )

        if st.button("Approve and send appeal", type="primary", disabled=not appeal_approver.strip()):
            approved_appeal = appeal.model_copy(
                update={
                    "approval": ApprovalRecord(
                        approver=appeal_approver.strip(),
                        approved_at=datetime.now(timezone.utc),
                        content_hash=content_hash(appeal),
                    )
                }
            )
            out = OUT_ROOT / appeal.case_id
            artifact = emit_appeal_artifact(approved_appeal, out)
            # Stored so it becomes precedent for the next case that hits the same criterion.
            save_appeal(approved_appeal)
            state["appeal_artifact"] = artifact
            st.rerun()

        if "appeal_artifact" in state:
            st.success("Appeal approved, generated, and filed as precedent.", icon="✅")
            st.download_button(
                "Download appeal (Markdown)",
                state["appeal_artifact"].read_text(encoding="utf-8"),
                file_name=f"{appeal.case_id}-appeal.md",
            )
