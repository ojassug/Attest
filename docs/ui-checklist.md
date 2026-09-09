# UI walkthrough — run this before recording the demo video

`tests/test_p6_s3.py` drives this app through Streamlit's `AppTest` and asserts the things that
can be asserted: that the gates are inert until a clinician is named, that no document exists
before approval, that every quote on screen is verified. This checklist covers what a test cannot
see — whether the screen *reads* correctly to someone who has never seen it.

Run it end to end after any change to `app.py`, and once more immediately before recording.

```bash
./scripts/verify.sh P6-S3 --offline     # must be green first
streamlit run app.py
```

No API key is required. Every model call replays from `cassettes/`.

---

## Before you start

- [ ] `rm -rf out sessions` — start from an empty store, so the "Open cases" list begins empty and
      is visibly populated by the walkthrough. A stale store makes the persistence step invisible.
- [ ] Browser zoom at 100%, window wide enough for the two-column intake panel to sit side by side.

---

## 1 · Fully documented case (`clean`)

- [ ] The sidebar shows the three demo cases and an empty **Open cases** list.
- [ ] The synthetic-data warning is visible **without scrolling the sidebar**. It must be on screen
      in the video's first frames — §7 requires the stance stated openly.
- [ ] The header names PacificSource, the plan, and links the source policy. Click the link: it
      resolves to a real published payer policy.
- [ ] Expand **The clinical note**. It renders as formatted Markdown, not raw text.
- [ ] **Run intake** → the structured case appears: patient, service, CPT codes, diagnosis, coverage.
- [ ] The prior-authorization panel reads **Required**, with a policy id and citation beneath it.
- [ ] `SYNTH-001` now appears under **Open cases** in the sidebar.
- [ ] **Match criteria** → three metrics appear. Confirm **10/10 criteria met** and that
      *Verified verbatim* shows equal numerator and denominator.
- [ ] Open two or three criteria. Each shows the payer's own wording, the model's reasoning, and at
      least one quote marked *verified verbatim* with character offsets.
- [ ] Section 3 reads **Nothing outstanding**.
- [ ] The justification lists one claim per met criterion, each with span ids.
- [ ] **Gate 1:** the approve button is greyed out. Confirm it cannot be clicked.
- [ ] Type a clinician name. The button enables.
- [ ] Approve → both download buttons appear. Download the PDF and open it. Check that a quoted
      passage in the PDF matches the note character for character.

## 2 · Missing documentation (`gap`)

- [ ] Switch case in the sidebar. **The previous case's results must not carry over** — the screen
      returns to the intake button.
- [ ] Run intake, then match criteria.
- [ ] `ps-04b` is flagged, and section 3 asks the practice a question ending in `?`.
- [ ] Read the question aloud. It must name what is missing specifically — the agent, the dose, the
      duration — not "more documentation is needed".
- [ ] The criterion still shows the evidence that *was* found. This is the product's thesis on one
      screen: the practice documented something, it was not enough, and here is precisely what to
      send.

## 3 · Denial → appeal (`denial`)

- [ ] Switch to the denial case. Note the payer changes to **Highmark Health Options** and the
      criteria set changes with it — the same engine, different pack.
- [ ] Run intake and match criteria.
- [ ] Approve at Gate 1 and download the submission.
- [ ] Expand **The denial letter**.
- [ ] **Draft the appeal** → contested criteria are listed with the payer's stated reason.
- [ ] Any objection that maps to no criterion appears in its own warning block, explicitly *not*
      rebutted.
- [ ] Each rebuttal names the policy section it answers and cites verified span ids.
- [ ] The appeal deadline is shown **with its source**. Confirm the source line is present — an
      undisclosed placeholder deadline is the failure this text exists to prevent.
- [ ] **Gate 2:** the approve button is greyed out until a clinician is named.
- [ ] Approve → the appeal downloads, and the success message says it was filed as precedent.

## 4 · Precedent reuse

- [ ] With the appeal approved, reload the page and walk the denial case again.
- [ ] Under a rebuttal, **Previously approved language for this criterion** now appears, naming the
      appeal it came from and who approved it.
- [ ] Confirm the wording shown is the approved wording, not a paraphrase.

---

## Fail conditions — stop and fix, do not record

- Any Python traceback rendered in the page.
- An approve button enabled with an empty clinician field.
- A document downloadable before approval.
- A quote on screen without the *verified verbatim* mark.
- A deadline shown without its source.
- Results from one case visible after switching to another.
