# UI walkthrough — run this before recording the demo video

`tests/test_p6_s3.py` and `tests/test_p9_s1.py` drive this app through Streamlit's `AppTest` and
assert the things that can be asserted: that the gates are inert until a clinician is named, that
no document exists before approval, that every quote on screen is verified, that an uploaded note
reaches its own payer's policy. This checklist covers what a test cannot see — whether the screen
*reads* correctly to someone who has never seen it.

Run it end to end after any change to `app.py`, and once more immediately before recording.

```bash
./scripts/verify.sh P9-S1 --offline     # must be green first
streamlit run app.py
```

No API key is required. Every model call replays from `cassettes/`.

---

## Before you start

- [ ] `rm -rf out sessions` — start from an empty store, so the "Open cases" list begins empty and
      is visibly populated by the walkthrough. A stale store makes the persistence step invisible.
- [ ] Have the four corpus files to hand — `data/synthetic/notes/{clean,gap,denial}.md` and
      `data/synthetic/denials/denial_001.md`. **Upload the committed files themselves.** A re-typed
      or PDF-round-tripped note changes the cassette key and turns the demo into live API calls
      against a 20-request daily cap. Line endings are no longer part of that hazard — P9-S2 pins
      `*.md` to LF in `.gitattributes` and normalises them in `read_upload` — but the text itself
      still has to be the committed text, character for character.
- [ ] Browser zoom at 100%, window wide enough for the two-column intake panel to sit side by side.

---

## 0 · The landing screen

- [ ] Nothing is preloaded. There is no case picker — the only thing to do is upload a note.
- [ ] The synthetic-data warning is visible **without scrolling the sidebar**. It must be on screen
      in the video's first frames — §7 requires the stance stated openly.
- [ ] Expand **No note to hand? Download a synthetic one**. Four notes and the denial letter are
      offered. Download one and confirm it opens as the note you expected.
- [ ] No payer, plan or policy is named anywhere yet. The app has read nothing, so it must claim
      nothing.

## 1 · Fully documented case (`clean.md`)

- [ ] Upload `clean.md` in the sidebar. The note appears under **The clinical note** and renders as
      formatted Markdown, not raw text. The caption names the file and its length.
- [ ] **Run intake** → the structured case appears: patient, service, CPT codes, diagnosis, coverage.
- [ ] The prior-authorization panel reads **Required**, with a policy id and citation beneath it.
- [ ] **Policy matched — PacificSource** appears *after* intake, never before. Click the source
      link: it resolves to a real published payer policy.
- [ ] `SYNTH-001` now appears under **Open cases** in the sidebar. Nobody typed that id — it came
      out of the note.
- [ ] **Match criteria** → three metrics appear. Confirm **10/10 criteria met** and that
      *Verified verbatim* shows equal numerator and denominator.
- [ ] The ten criteria read as ten scannable lines — `✅ ps-01 · Provider qualification — Met` —
      not as ten paragraphs of policy text. All ten should fit on one screen.
- [ ] Open two or three criteria. Each shows the payer's own wording, the model's reasoning, and at
      least one quote marked *verified verbatim* with character offsets.
- [ ] Open a contraindication — `ps-05a`, `ps-05b` or `ps-05c`. The label says **Ruled out**, never
      *Met*, and inside it explains that a contraindication is satisfied when the record documents
      the finding is absent. Read the label aloud: it must not sound like the patient has the
      condition.
- [ ] Section 3 reads **Nothing outstanding**.
- [ ] The justification lists one claim per met criterion, each with span ids.
- [ ] **Gate 1:** the approve button is greyed out. Confirm it cannot be clicked.
- [ ] Type a clinician name. The button enables.
- [ ] Approve → both download buttons appear. Download the PDF and open it. Check that a quoted
      passage in the PDF matches the note character for character.

## 2 · Missing documentation (`gap.md`)

- [ ] Upload `gap.md` over the previous note. **The previous case's results must not carry over** —
      the screen returns to the intake button.
- [ ] Run intake, then match criteria.
- [ ] `ps-04b` is flagged, and section 3 asks the practice a question ending in `?`.
- [ ] Read the question aloud. It must name what is missing specifically — the agent, the dose, the
      duration — not "more documentation is needed".
- [ ] The criterion still shows the evidence that *was* found. This is the product's thesis on one
      screen: the practice documented something, it was not enough, and here is precisely what to
      send.

## 3 · Denial → appeal (`denial.md` + `denial_001.md`)

- [ ] Upload `denial.md`. Run intake.
- [ ] **The payer changes to Highmark Health Options and the criteria set changes with it** — same
      screen, same code, no setting touched. This is the moment the demo exists to show; give it a
      beat in the recording.
- [ ] Match criteria, approve at Gate 1, download the submission.
- [ ] Section 5 shows a **second uploader** for the denial letter, and no **Draft the appeal**
      button until one is supplied. A denial arrives days later as its own document.
- [ ] Upload `denial_001.md`. Expand **The denial letter**.
- [ ] **Draft the appeal** → contested criteria are listed with the payer's stated reason.
- [ ] Any objection that maps to no criterion appears in its own warning block, explicitly *not*
      rebutted.
- [ ] Each rebuttal names the policy section it answers and cites verified span ids.
- [ ] The appeal deadline is shown **with its source**. Confirm the source line is present — an
      undisclosed placeholder deadline is the failure this text exists to prevent.
- [ ] **Gate 2:** the approve button is greyed out until a clinician is named.
- [ ] Approve → the appeal downloads, and the success message says it was filed as precedent.

## 4 · Precedent reuse

- [ ] With the appeal approved, reload the page and walk the denial case again — upload both files
      as before.
- [ ] Under a rebuttal, **Previously approved language for this criterion** now appears, naming the
      appeal it came from and who approved it.
- [ ] Confirm the wording shown is the approved wording, not a paraphrase.

## 5 · The unlisted payer (optional, but it is the honest half of the story)

- [ ] Copy `clean.md`, change the payer line to a payer with no pack, and upload it. This is a live
      API call, so skip it if the daily quota is spent.
- [ ] Intake still succeeds and the structured case is still shown.
- [ ] Prior authorization reads **Unknown** — as a warning, never green — and the review **stops**
      with *No policy on file*. Confirm there is no criteria section and no path to a document.

---

## 6 · A note nobody recorded (do this once, it is what a judge will do first)

- [ ] Write two lines of nonsense into a `.md` file and upload it as the clinical note.
- [ ] **Run intake** → the screen says the note is not one of the recorded ones, explains that the
      demo replays responses recorded ahead of time so it costs nothing and needs no key, and
      expands the sample downloads underneath. **No traceback.**
- [ ] The same holds for any note of your own. An uploader is an invitation, and this is the
      answer to it — P9-S2 exists because the screen used to answer with a stack trace.

---

## Fail conditions — stop and fix, do not record

- Any Python traceback rendered in the page.
- A payer, plan or policy named before intake has run.
- An approve button enabled with an empty clinician field.
- A document downloadable before approval.
- A quote on screen without the *verified verbatim* mark.
- A contraindication labelled *Met*, which states the inverse of what was found.
- A deadline shown without its source.
- Results from one note still visible after uploading another.
- A **Draft the appeal** button offered with no denial letter uploaded.
- An unlisted payer producing an empty criteria table instead of stopping.
