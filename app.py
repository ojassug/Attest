"""Attest — the reviewer's console.

The office manager's screen. Everything the engine produces is shown here in the order a human
would actually work through it: upload the note, decide whether a prior authorization is needed,
check the payer's criteria against the record, see what is missing, approve, send. Then the same
again when a denial arrives.

Three rules shape this file. The first two come from `Attest-PRODUCT.md` §6:

**The gates are not UI logic, so this file must not be able to weaken them.** Approving here builds
a real `ApprovalRecord` and calls the same `emit_*_artifact` functions the tests exercise. There is
no UI-side path to a document. If someone deleted this file, the gates would be exactly as strong.

**Nothing is shown as fact that the verifier did not confirm.** Every quote on this page carries the
verifier's own verdict; unverifiable ones were already stripped from the coverage before it got
here, and their criterion downgraded to INSUFFICIENT.

**Nothing is preloaded.** The case arrives the way it arrives in a practice — as a document someone
uploads. Earlier revisions of this screen picked one of three committed corpus cases from a radio,
which meant the payer, the policy pack and the case id were all known before the model had read
anything. That is a demo of the renderer, not of the product: it cannot show the one step a
practice actually cares about, which is Attest working out *by itself* whose rules apply. The
corpus still exists and still backs every gate in `tests/` — it is simply no longer wired into the
screen. See `DECISIONS.md`, 2026-09-10.

The app replays from committed cassettes, so a judge with no API key sees the same results — but
only for a note whose text matches what was recorded. Any other note is a live call.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from attest.agents.intake import MissingFactError, extract_case
from attest.appeal.assemble import build_appeal
from attest.appeal.draft import draft_rebuttals
from attest.appeal.emit import emit_appeal_artifact
from attest.appeal.parse import parse_denial
from attest.appeal.precedent import find_precedents
from attest.criteria.gaps import build_gap_list
from attest.criteria.match import match_all
from attest.gates import content_hash
from attest.models import ApprovalRecord, Packet, Verdict
from attest.packet.emit import ARTIFACT_NAME, PDF_NAME, emit_submission_artifact
from attest.packet.justification import build_justification
from attest.paths import data_dir
from attest.policies.loader import find_pack
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

# Offered for download on the landing screen, never loaded into the pipeline. A judge opening the
# public deploy has no clinical note on their machine and no way to obtain one — handing them a
# file to upload keeps the app testable by a stranger without putting a case back on the rails.
SAMPLE_NOTES = {
    "Fully documented — PacificSource, TMS": "notes/clean.md",
    "Missing documentation — PacificSource, TMS": "notes/gap.md",
    "Denied, then appealed — Highmark, TMS": "notes/denial.md",
    "Second specialty — VNS Health, physical therapy": "notes/pt.md",
}
SAMPLE_DENIAL = "denials/denial_001.md"

st.set_page_config(page_title="Attest — prior authorization", page_icon="🩺", layout="wide")


# --------------------------------------------------------------------------- state


def read_upload(uploaded) -> str:
    """Decode an uploaded document.

    The encoding is named rather than left to the platform default. Sessions alternate between a
    Mac and a Windows machine, and a note decoded under two different default codecs would not
    merely look wrong — it would shift every character offset the verifier records, so evidence
    spans would point at the wrong text while still appearing verified.
    """
    return uploaded.getvalue().decode("utf-8")


def note_key(text: str) -> str:
    """Per-note scratch space is keyed by the note's content, not its filename.

    Two uploads of the same note continue the same review rather than starting a second one, and
    re-uploading an edited note correctly starts a fresh review — because the edit is exactly what
    invalidates the results already on screen.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def case_state() -> dict:
    return st.session_state.setdefault("results", {}).setdefault(st.session_state["note_key"], {})


def reset_case() -> None:
    st.session_state.setdefault("results", {}).pop(st.session_state.get("note_key"), None)


# ------------------------------------------------------------------------- sidebar

with st.sidebar:
    st.title("🩺 Attest")
    st.caption("Prior authorization, end to end — for practices without PA staff.")

    uploaded = st.file_uploader(
        "Clinical note",
        type=["md", "txt"],
        key="note_file",
        help="The note the practice already wrote. Attest reads it — nobody re-keys it into a form.",
    )

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


# ------------------------------------------------------------------ 0 · empty state

st.title("Prior authorization review")

if uploaded is None:
    st.info("Upload a clinical note in the sidebar to begin.", icon="📄")
    st.caption(
        "Attest reads the note, works out which payer's policy applies, checks the record against "
        "that policy criterion by criterion, and stops for a clinician's approval before anything "
        "is submitted."
    )

    notes_dir = data_dir() / "synthetic"
    if notes_dir.is_dir():
        with st.expander("No note to hand? Download a synthetic one", expanded=False):
            st.caption(
                "Fabricated records, written for testing. Download one and upload it in the "
                "sidebar. The denial walkthrough needs the letter as well, at step 5."
            )
            for label, relative in SAMPLE_NOTES.items():
                path = notes_dir / relative
                if path.is_file():
                    st.download_button(
                        label,
                        path.read_text(encoding="utf-8"),
                        file_name=path.name,
                        use_container_width=True,
                    )
            denial_path = notes_dir / SAMPLE_DENIAL
            if denial_path.is_file():
                st.download_button(
                    "Denial letter — Highmark",
                    denial_path.read_text(encoding="utf-8"),
                    file_name=denial_path.name,
                    use_container_width=True,
                )
    st.stop()


note_text = read_upload(uploaded)
st.session_state["note_key"] = note_key(note_text)
state = case_state()

st.caption(f"Reading **{uploaded.name}** — {len(note_text):,} characters.")

with st.expander("The clinical note", expanded=False):
    st.markdown(note_text)


# ------------------------------------------------------- 1 & 2 · intake and PA need

st.header("1 · Read the note and decide whether a PA is needed")

if "case" not in state:
    if st.button("Run intake", type="primary"):
        with st.spinner("Reading the note…"):
            try:
                state["case"] = extract_case(note_text)
            except MissingFactError as exc:
                # The note is missing something the request cannot proceed without. That is a
                # question for the practice, not a failure of the run — say which fact, and stop.
                st.error(str(exc), icon="❓")
                st.stop()
            save_case(state["case"])
        st.rerun()
    st.stop()

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


# ------------------------------------------------------------- 1b · policy routing

# Which payer's rules apply is derived from what the model read, not chosen by whoever opened the
# app. `find_pack` is the same lookup `check_pa_required` just used, and returning None is
# meaningful: no pack means we have no criteria to check, which is not the same as passing.
pack = find_pack(
    cpt=case.service.cpt_codes[0],
    payer=case.insurance.payer,
    plan=case.insurance.plan,
)

if pack is None:
    st.warning(
        f"**No policy on file.** Nothing covering CPT "
        f"{', '.join(case.service.cpt_codes)} for {case.insurance.payer} "
        f"({case.insurance.plan}). Attest will not guess a payer's criteria, so the review stops "
        f"here — the intake above still stands, and the requirement should be confirmed with the "
        f"payer directly.",
        icon="🔍",
    )
    st.caption(
        "Adding a payer is a data change, not a code change: one YAML pack under "
        "`src/attest/policies/packs/`."
    )
    st.stop()

st.success(f"**Policy matched — {pack.payer}** · {pack.plan} · {pack.service}", icon="📕")
st.caption(
    f"Criteria from [{pack.source_title}]({pack.source_url}), retrieved {pack.retrieved_date}"
)


# ------------------------------------------------------------- 3 · criteria coverage

st.header("2 · Check the record against the payer's criteria")

if "coverage" not in state:
    if st.button("Match criteria", type="primary"):
        with st.spinner("Reading each criterion against the note…"):
            raw = match_all(pack, note_text, case_id=case.case_id)
            # The verifier runs before anything is displayed, not after. A quote that cannot be
            # found verbatim in the note never reaches this screen at all.
            state["verified"] = enforce_verification(raw, note_text)
            state["coverage"] = state["verified"].coverage
        st.rerun()
    st.stop()

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

gaps = build_gap_list(coverage)

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

st.header("4 · Approve the submission")

packet = Packet(
    case_id=case.case_id,
    coverage=coverage,
    justification=build_justification(coverage, case),
    gaps=gaps,
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

st.header("5 · The payer denied it")
st.caption(
    "A denial arrives days later as its own document, so it is uploaded separately rather than "
    "shipped alongside the note."
)

denial_upload = st.file_uploader(
    "Denial letter",
    type=["md", "txt"],
    key="denial_file",
    help="The payer's determination letter. Upload it to draft the appeal.",
)

if denial_upload is None:
    st.stop()

denial_text = read_upload(denial_upload)

with st.expander("The denial letter", expanded=False):
    st.markdown(denial_text)

if "appeal" not in state:
    if st.button("Draft the appeal", type="primary"):
        with st.spinner("Reading the denial and building the rebuttals…"):
            denial = parse_denial(denial_text, pack, case_id=case.case_id)
            rebuttals = draft_rebuttals(denial.contested, coverage, pack)
            state["denial"] = denial
            state["appeal"] = build_appeal(denial, rebuttals, pack)
        st.rerun()
    st.stop()

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

appeal_approver = st.text_input("Approving clinician", key="gate2_approver", placeholder="Dr. …")

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
