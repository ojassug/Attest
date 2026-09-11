"""Attest — the reviewer's console.

The office manager's screen. Everything the engine produces is shown here in the order a human
would actually work through it: upload the note, decide whether a prior authorization is needed,
check the payer's criteria against the record, see what is missing, approve, send. Then the same
again when a denial arrives.

Four rules shape this file. The first two come from `Attest-PRODUCT.md` §6:

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

**Nothing raises into the page.** An uploader is an invitation, and a judge will accept it with a
note of their own — which is a live model call this deploy has no key for. Every engine call on
this screen therefore sits inside `guarded`, which turns a failure into a sentence a person can act
on. A Python traceback rendered in the page is the first entry under *Fail conditions* in
`docs/ui-checklist.md`, and before P9-S2 this file had two reliable ways to produce one.

The app replays from committed cassettes, so a judge with no API key sees the same results — but
only for a note whose text matches what was recorded. Any other note is a live call.
"""

from __future__ import annotations

import hashlib
import os
from contextlib import contextmanager
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
from attest.llm import have_credentials
from attest.models import ApprovalRecord, Packet, Polarity, Verdict
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

# The icon follows the verdict, because "satisfied / not satisfied / cannot tell" means the same
# thing to a reviewer whichever way the criterion points.
VERDICT_ICON = {
    Verdict.MET: "✅",
    Verdict.UNMET: "❌",
    Verdict.INSUFFICIENT: "⚠️",
}

# The wording does not, and collapsing the two senses is the specific misreading this table exists
# to prevent. Four of Highmark's ten criteria are contraindications, and the screen used to render
# them as "✅ hho-05 — Seizure disorder or any history of seizure", which to anyone who is not a
# clinician says the patient *has* a seizure disorder. It says the opposite: the record documents
# that they do not.
#
# INSUFFICIENT is the pair worth reading twice. On an absent criterion it does not mean the finding
# might be there — it means nobody wrote it down, and `match.py` is explicit that "an undocumented
# contraindication is unknown, not ruled out". "Not ruled out" is that sentence in two words.
VERDICT_WORDING = {
    Polarity.PRESENT: {
        Verdict.MET: "Met",
        Verdict.UNMET: "Not met",
        Verdict.INSUFFICIENT: "Insufficiently documented",
    },
    Polarity.ABSENT: {
        Verdict.MET: "Ruled out",
        Verdict.UNMET: "Present — contraindicated",
        Verdict.INSUFFICIENT: "Not ruled out",
    },
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
    """Decode an uploaded document, and settle its line endings.

    The encoding is named rather than left to the platform default. Sessions alternate between a
    Mac and a Windows machine, and a note decoded under two different default codecs would not
    merely look wrong — it would shift every character offset the verifier records, so evidence
    spans would point at the wrong text while still appearing verified.

    Newlines are the same hazard through a different door, and P9-S2 found it the hard way. Every
    other reader in this codebase goes through `Path.read_text`, whose universal-newline handling
    collapses `\\r\\n` to `\\n` before anything sees it — so that is the text the cassettes were
    recorded against and the text the ground truth describes. An upload arrives as raw bytes with
    no such translation, so a note checked out on Windows reached this function as a *different
    string*: 2424 characters where the recorded one is 2371. Different string, different
    `cache._key`, cassette miss, live call, and on a keyless deploy a traceback in the page.

    `.gitattributes` now pins `*.md` to LF, which fixes the checkout. This fixes the upload, which
    is the half that still matters: a judge who opens a downloaded note in Notepad and saves it
    has re-introduced CRLF on a file no `.gitattributes` will ever touch.
    """
    text = uploaded.getvalue().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def humanise(category: str) -> str:
    """`treatment_resistance` → `Treatment resistance`.

    Categories are pack data written for code to group by, and they reach the screen unchanged
    everywhere else in this file. In a criterion label they are doing a different job — telling a
    reviewer what kind of requirement they are looking at — so they get read as English.
    """
    return category.replace("_", " ").capitalize()


def offer_samples(*, expanded: bool = False) -> None:
    """Hand over the synthetic corpus as downloads, never as a loaded case.

    Two screens need this: the landing screen, where a judge has no clinical note of their own, and
    the dead end `guarded` reaches when someone uploads a note the cassettes cannot answer. Telling
    them what went wrong without handing them something that works is half an answer.

    Nothing here enters the pipeline. The app writes a file out and forgets it; the case still only
    arrives by upload. See `DECISIONS.md`, 2026-09-10 — "downloading a sample is not preloading
    one".
    """
    notes_dir = data_dir() / "synthetic"
    if not notes_dir.is_dir():
        return

    with st.expander("No note to hand? Download a synthetic one", expanded=expanded):
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


@contextmanager
def guarded(stage: str, *, model_backed: bool = False):
    """Turn any failure in `stage` into a sentence, and stop the run.

    Streamlit renders an uncaught exception as a traceback inside the page, which is the first
    entry under *Fail conditions* in `docs/ui-checklist.md`. Before P9-S1 that was mostly
    theoretical — the screen offered three known cases. An uploader changes that: it invites a note
    nobody recorded, and the public deploy has no key to answer one with.

    `model_backed` distinguishes the two failures a person can actually do something about. With no
    credential configured, a model call can only have been reached by missing a cassette — the note
    is simply not one of the recorded ones — and saying so is more useful than the `RuntimeError`
    about a missing key, which sounds like the deploy is broken when it is working as designed.
    Everything else is named as what it is; the screen never pretends a real failure was expected.
    """
    try:
        yield
    except MissingFactError as exc:
        # Not a failure of the run: the note omits something the request cannot proceed without.
        # That is a question for the practice, so it keeps its own wording and its own icon.
        st.error(str(exc), icon="❓")
        st.stop()
    except Exception as exc:  # noqa: BLE001 - the whole point is that nothing escapes to the page
        if model_backed and not have_credentials():
            st.warning(
                f"**This note is not one of the recorded ones.** {stage} needs a model, and this "
                "demo answers from responses recorded ahead of time so that it costs nothing and "
                "works with no API key. A note that was not part of that recording has nothing to "
                "replay.\n\n"
                "Download one of the synthetic notes below and upload that, or run Attest locally "
                "with your own key to use this note — see `docs/setup.md`.",
                icon="🎞️",
            )
            offer_samples(expanded=True)
        else:
            st.error(
                f"**{stage} could not be completed.** {type(exc).__name__}: {exc}",
                icon="🛑",
            )
        st.stop()


def note_key(text: str) -> str:
    """Per-note scratch space is keyed by the note's content, not its filename.

    Two uploads of the same note continue the same review rather than starting a second one, and
    re-uploading an edited note correctly starts a fresh review — because the edit is exactly what
    invalidates the results already on screen.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


class SampleUpload:
    """Simulate an uploaded file for a sample case from the synthetic corpus."""

    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def case_state() -> dict:
    return st.session_state.setdefault("results", {}).setdefault(st.session_state["note_key"], {})


def reset_case() -> None:
    st.session_state.setdefault("results", {}).pop(st.session_state.get("note_key"), None)
    st.session_state.pop("sample_upload", None)


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

if uploaded is not None:
    st.session_state.pop("sample_upload", None)
elif "sample_upload" in st.session_state:
    uploaded = st.session_state["sample_upload"]

st.title("Prior authorization review")

if uploaded is None:
    st.info("Upload a clinical note in the sidebar to begin.", icon="📄")

    st.markdown(
        "**The problem.** Prior authorization (PA) is the largest administrative burden in "
        "outpatient specialty care, consuming immense staff time and delaying patient treatment. "
        "Solo and small practices absorb this directly because they have no dedicated PA departments."
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Weekly requests", "~39–43", help="PA requests completed per physician per week (AMA surveys)")
    m2.metric("Staff time spent", "~13 hrs/wk", help="Physician and staff hours consumed by PA weekly (AMA)")
    m3.metric("Denial rate", "~31%", help="Physicians reporting requests often or always denied")

    st.subheader("Target audience")
    st.write(
        "Built for office managers, solo clinicians, and administrative staff at 1–10 provider "
        "specialty practices (behavioral health, physical therapy, pain, neurology) who personally handle PAs."
    )

    st.subheader("End-to-end pipeline")
    st.markdown(
        "1. **Intake & PA lookup** — Ingests clinical note, extracts case details, and checks if PA is required under payer policy.\n"
        "2. **Criteria matching & verifier** — Evaluates each policy criterion, strictly verifying verbatim source evidence quotes.\n"
        "3. **Gap identification** — Surfaces missing documentation as targeted clinician questions.\n"
        "4. **Clinician approval (Gate 1) & Submission** — Secure human sign-off with cryptographic content hash before emitting PDF/Markdown.\n"
        "5. **Denial parsing & appeal (Gate 2)** — Parses denial letter, drafts policy-cited rebuttals, enforces Gate 2 approval, and saves precedent."
    )

    st.warning(
        "**Synthetic data only.** Every note and denial letter in this demo is fabricated. "
        "No real patient information is used anywhere in Attest.",
        icon="⚠️",
    )

    st.subheader("Try a sample note or download one below")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Load sample: PacificSource TMS (clean)", use_container_width=True):
            sample_path = data_dir() / "synthetic" / "notes" / "clean.md"
            if sample_path.exists():
                st.session_state["sample_upload"] = SampleUpload(sample_path.name, sample_path.read_bytes())
                st.rerun()
    with col2:
        if st.button("Load sample: Highmark TMS (denial)", use_container_width=True):
            sample_path = data_dir() / "synthetic" / "notes" / "denial.md"
            if sample_path.exists():
                st.session_state["sample_upload"] = SampleUpload(sample_path.name, sample_path.read_bytes())
                st.rerun()

    offer_samples()
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
            with guarded("Reading the note", model_backed=True):
                state["case"] = extract_case(note_text)
            with guarded("Filing the case"):
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
            with guarded("Matching the criteria", model_backed=True):
                raw = match_all(pack, note_text, case_id=case.case_id)
                # The verifier runs before anything is displayed, not after. A quote that cannot be
                # found verbatim in the note never reaches this screen at all. It stays inside the
                # guard with the match it checks: a verification failure is not a result either.
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
    icon = VERDICT_ICON[verdict.verdict]
    label = VERDICT_WORDING[criterion.polarity][verdict.verdict]

    # The label answers "which criterion, what kind, and how did it land" — the three things a
    # reviewer scans a list of ten for. The payer's wording used to be *in* this label: up to 524
    # characters of policy legalese wrapping to four lines, ten of them stacked, which made the
    # product's core screen the one nobody could read. It moves inside, where it is still on
    # screen and still verbatim, and where reading it is a choice rather than a toll.
    with st.expander(
        f"{icon} **{criterion.id}** · {humanise(criterion.category)} — {label}", expanded=False
    ):
        st.markdown(f"**The payer's own words.** {criterion.text}")
        # "Source:" rather than "Policy", because a section name is already a section name —
        # Highmark's is literally "POLICY POSITION", and the old prefix rendered it twice.
        st.caption(f"Source: {criterion.source_section}")

        if criterion.polarity is Polarity.ABSENT:
            st.caption(
                "This is a contraindication: it is satisfied when the record documents the "
                "finding is **absent**. Silence is not the same as ruled out."
            )

        st.markdown(f"**Attest's reading.** {verdict.reasoning}")

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
    # `emit_submission_artifact` refuses a packet whose hash has moved since sign-off. That refusal
    # is the gate doing its job, so it is rendered rather than raised — and it still stops here.
    with guarded("Generating the submission"):
        emit_submission_artifact(approved, out)
    state["submission"] = out
    state["submission_approval"] = approved.approval
    st.rerun()

if "submission" in state:
    out = state["submission"]
    st.success("Submission packet approved and generated.", icon="✅")
    if "submission_approval" in state:
        appr = state["submission_approval"]
        st.caption(
            f"Approved by **{appr.approver}** on {appr.approved_at.strftime('%Y-%m-%d %H:%M:%S UTC')} · "
            f"Content hash `{appr.content_hash[:12]}`"
        )
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
else:
    st.stop()


# ------------------------------------------------------------ 6 · denial and Gate 2

if st.session_state.get("denial_file") is None:
    st.header("5 · If a denial arrives")
else:
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
            with guarded("Reading the denial", model_backed=True):
                denial = parse_denial(denial_text, pack, case_id=case.case_id)
            with guarded("Drafting the rebuttals", model_backed=True):
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
    with guarded("Generating the appeal"):
        artifact = emit_appeal_artifact(approved_appeal, out)
        # Stored so it becomes precedent for the next case that hits the same criterion.
        save_appeal(approved_appeal)
    state["appeal_artifact"] = artifact
    state["appeal_approval"] = approved_appeal.approval
    st.rerun()

if "appeal_artifact" in state:
    st.success("Appeal approved, generated, and filed as precedent.", icon="✅")
    if "appeal_approval" in state:
        appr = state["appeal_approval"]
        st.caption(
            f"Approved by **{appr.approver}** on {appr.approved_at.strftime('%Y-%m-%d %H:%M:%S UTC')} · "
            f"Content hash `{appr.content_hash[:12]}`"
        )
    st.download_button(
        "Download appeal (Markdown)",
        state["appeal_artifact"].read_text(encoding="utf-8"),
        file_name=f"{appeal.case_id}-appeal.md",
    )
