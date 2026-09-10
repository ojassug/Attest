# UI/UX review — the reviewer's console, 2026-09-10

> **What this is.** A walkthrough of `app.py` as it stands after P9-S1, judged against the five
> criteria in `Attest-PRODUCT.md` §1.5 and against the one question that decides them: *what does a
> judge understand, in the first thirty seconds, from a link and a five-minute video?*
>
> **What this is not.** A list of preferences. Every finding below was reproduced by running the
> app, and each one is tied to a scoring criterion or to a fail condition already written down in
> `docs/ui-checklist.md`. The reasoning that survives becomes `DECISIONS.md`; the work becomes
> P9-S2 onward in `PLAN.md`.

**Method.** Fresh venv, `streamlit run app.py`, no API key. Walked `clean.md` end to end, then
`denial.md` + `denial_001.md` end to end, then the same landing screen at 375 px. Also opened the
public deploy at <https://attest.streamlit.app>, which — contrary to the 09-10 handoff note in
`STATUS.md` — **is already serving the upload-driven P9-S1 screen**, not the old picker.

---

## 0 · Two findings that are not about design

These are not UX. They are the two ways the demo breaks in front of a judge, and they outrank
everything else in this document.

### 0.1 On Windows, uploading the committed corpus file misses every cassette

Reproduced on the first attempt. `.gitattributes` pins only `*.sh` to LF, so Markdown checks out
CRLF on a Windows clone. Then the two paths into the same file disagree:

| how the note is read | line endings | length |
|---|---|---|
| `Path.read_text()` — what recorded the cassettes, and what every test uses | `\n` | 2371 chars |
| `read_upload()` — `uploaded.getvalue().decode("utf-8")`, no newline translation | `\r\n` | 2424 chars |

Two different strings, therefore two different `cache._key` values, therefore a cassette miss,
therefore a live Gemini call, therefore — with no key configured —
`RuntimeError: No Gemini API key found` rendered as a full traceback inside the page.

The hosted app is not affected: Streamlit Community Cloud clones on Linux, so the bytes it serves
and the bytes it receives back are both LF. **Every local demo on a Windows machine is affected**,
and `docs/ui-checklist.md` explicitly instructs the operator to "upload the committed files
themselves" — which is precisely the action that fails.

This is the encoding landmine `DECISIONS.md` (2026-09-08, 2026-09-10) already records, arriving
through the door P9-S1 opened. `read_upload` names its encoding for exactly the right reason and
then leaves newlines to the filesystem, which is the half that still shifts every character offset
the verifier reports.

### 0.2 There is no error boundary anywhere in the console

`app.py` catches `MissingFactError` and nothing else. Every other failure — an auth error, a
network error, a `StorageError`, a schema mismatch — reaches Streamlit and renders as a red Python
traceback. A second one was reproduced trivially by pointing `ATTEST_STORE_DIR` at a long path:
`strands.types.exceptions.StorageError: Failed to write 'session/case-SYNTH-001/...'`.

P9-S1 made this materially more likely rather than less. Replacing a three-option radio with an
open upload box is an *invitation* to try your own note, and any note not in `cassettes/` is a live
call that cannot succeed on a keyless deploy. The screen now asks judges to do the one thing it
cannot survive.

"Any Python traceback rendered in the page" is the first entry under **Fail conditions** in
`docs/ui-checklist.md`. The console has two reliable ways to produce one.

> **Both fixed — P9-S2, gate passed at `f906041`.** `.gitattributes` pins `*.md` to `eol=lf`,
> `read_upload` normalises newlines after decoding, and every engine call runs inside `guarded`.
> `verify.sh ALL --offline` is now **361 passed, 5 deselected**, on Windows as well as Linux. A
> judge who uploads their own note gets an explanation and the sample downloads, not a stack trace
> — walked in a browser, and covered by `docs/ui-checklist.md` §6. The fix is deliberately at both
> ends: the attribute fixes the checkout, `read_upload` fixes the upload, and only the second
> survives someone re-saving a downloaded note in an editor. See `DECISIONS.md`, 2026-09-10.

### 0.3 The keyless gate is red on `main`, and the README tells judges to run it

Found while confirming that the two findings above were not self-inflicted. They were not — but
this was.

```
gh run list --branch main
main  P9-S1 DONE: gate passed at ec06236   failure   2026-09-10T11:51Z
```

The last five `gate` runs all failed. The most recent one on `main` reports
**`2 failed, 355 passed, 5 deselected`**, and both failures are
`RuntimeError: No Gemini API key found` in `tests/test_p7_s1.py`:
`test_the_orchestrator_composes_exactly_the_four_specialists` and
`test_every_specialist_advertises_what_it_is_for`.

The cause is small. Both call `build_orchestrator`, which constructs Strands `Agent`s, and `Agent`
construction calls `build_model()`, which raises without a credential. Neither test carries the
`skipif` that `test_p0_s4.py` and `test_p2_s1.py` define for exactly this case, so these two are
the only tests in the repository that demand a key to check something purely structural — that four
specialists are composed, and that each has a description longer than forty characters.

Why it matters more than anything else in this document:

- `README.md` states `./scripts/verify.sh ALL --offline` "exits zero, **357 tests**, ~13s, no API
  key", and that "the same command runs in CI on every push, on Linux, with no credentials
  configured — the judge's scenario rather than ours." Both sentences are currently false.
- The hackathon rules require a project that "installs and runs consistently", and Stage One is
  pass/fail on baseline viability. A judge who follows the README's own instructions gets a red
  gate.
- `.github/workflows/gate.yml` was written precisely to make this a check rather than a claim. It
  is doing its job; nobody has read the result.

This is drafted as **P9-S8**, and it outranks the rest of P9.

> **Fixed, same day — gate passed at `84cb86e`.** `verify.sh ALL --offline` now exits zero keyless:
> **357 passed, 5 deselected**. The answer was already in the repository: `test_p2_s3.py` hit this
> at P2-S3 against `build_intake_agent` and solved it by injecting a placeholder credential,
> because constructing an `Agent` makes no request. P7-S1 never applied the pattern. A `needs_key`
> skip was rejected — it would have left `agent.as_tool()` composition unverified in the judge's
> exact environment. The 357 in the README turned out to be correct; only "exits zero" was false.
> See `DECISIONS.md`, 2026-09-10. **One DoD item remains open and needs a merge rather than a
> commit:** the workflow only runs on `main` and on pull requests, so it has not yet reported on
> this fix.

**Local numbers, for comparison.** On this Windows checkout the same command reported
**15 failed, 342 passed**. Normalising only the corpus line endings to LF — changing nothing else —
took it to **2 failed, 355 passed**, matching CI exactly. That is the experiment that confirms
§0.1: thirteen of the fifteen failures were CRLF, including the whole of `test_p9_s1.py` and most
of `test_p6_s3.py`. **The P6-S3 and P9-S1 gates do not pass on a Windows clone.**

---

## 1 · The diagnosis

**The console is a correct instrument panel. It is not a narrative.**

Every number on screen is honest, sourced and defensible — which is rare, and is the hard part.
But the screen shows *results* and never *the story*, and four of the five judging criteria are
scored from a five-minute video and a short click-through rather than from the repository.

Three consequences, each tied to a criterion:

**A judge never learns what problem this solves.** *(Potential Impact, Presentation.)* The landing
screen is about sixty words. The material in `README.md` — 39–43 PA requests per physician per
week, ~13 hours a week of physician and staff time, ~31% often or always denied, appeals effective
but under-used — appears nowhere on screen. The pitch lives in the video and the repo; the link the
judges click carries none of it.

**The agent is invisible.** *(Technical Implementation — the criterion that names the SDK.)* The
console names Strands zero times. There is no orchestrator, no subagent boundary, no tool call, no
model tier, no elapsed time anywhere on screen. A judge scoring "how thoroughly and skillfully the
project uses Strands Agents" from the live link has no evidence at all and must read `src/` to find
any. Some will. Most will not.

**The moment the demo exists for is un-narrated.** *(Creativity & Originality.)* Uploading a
PacificSource note and a Highmark note into the same unchanged screen reaches two different policy
packs with materially different bars — 2 antidepressant trials plus augmentation versus 4 trials
plus a psychotherapy failure. `docs/ui-checklist.md` calls this "the moment the demo exists to
show; give it a beat in the recording." On screen it is one green `st.success` bar, visually
identical to every other success message in the app. Nothing says *nobody told it this — it worked
it out from the document.*

---

## 2 · Findings, screen by screen

### 2.1 Landing

One info box, one sentence of caption, one collapsed expander. Roughly 85% of the viewport is
empty. The only path forward is: expand the expander → download a `.md` → find it in Downloads →
upload it. Four steps and a filesystem round trip before the product does anything at all.

This is the single highest bounce risk on the judge-facing URL, and it is a direct cost of P9-S1.
The step was right; the landing screen it left behind was never designed.

### 2.2 Mobile — the sidebar instruction points at nothing

At 375 px the sidebar collapses behind a small `»` chevron and the only instruction on screen reads
**"Upload a clinical note in the sidebar to begin"** — naming a surface the viewer cannot see.

Worse, the synthetic-data banner lives in that sidebar, so **on a phone it never renders at all**.
`Attest-PRODUCT.md` §7 requires the synthetic-data stance to be stated openly, and
`docs/ui-checklist.md` requires it visible "in the video's first frames". On mobile it is absent.

### 2.3 Intake — red means two different things

`Required` renders through `st.error`, i.e. red. A prior authorization being required is not an
error; it is the normal path and the entire reason the product exists. The comment above that
dispatch table defends `UNKNOWN` not being green, which is right, but it does not follow that
`REQUIRED` should be styled as a failure.

Compounding it: Streamlit's default primary colour is the same red, so on that one screen red means
both "something is wrong" and "click this". There is no `.streamlit/config.toml`, so the palette is
whatever Streamlit ships and whatever the judge's operating system reports for dark mode.

### 2.4 Criteria — the core of the product, and the weakest screen

`Attest-PRODUCT.md` §9 says this section "is the product's core and must be the strongest part of
the demo." It is currently the hardest to read.

**The expander label is the entire policy text.** Measured across the three packs: `hho-03` is 524
characters, `ps-01` 399, `ps-04a` 366, `ps-04b` 351, `hho-08` 329. Rendered as expander headers
these wrap to three and four lines of unbroken payer legalese, ten in a column. The category
(`contraindication`, `treatment_resistance`) that would make the list scannable is hidden *inside*
the expander.

**Nothing is expanded, so the screen shows zero evidence at rest.** The verified quotes — the whole
anti-hallucination argument — take ten clicks to reveal. In a five-minute video that is a section
the presenter must apologise for rather than dwell on.

**Inside, the evidence is the faintest element on the page.** The quote renders as a low-contrast
blockquote beneath the model's reasoning, and `✓ verified verbatim · characters 2208–2266 of the
note` is a small grey caption. The most precise, most credible detail in the entire product is
styled as a footnote.

> **Both fixed — P9-S3, gate passed at `2436618`.** The label is now
> `✅ hho-05 · Contraindication — Ruled out`; the payer's wording moved inside the expander, still
> verbatim; and an absent criterion carries a line saying it is satisfied when the record documents
> the finding is *absent*. All ten criteria fit on one screen. `INSUFFICIENT` on a contraindication
> reads **Not ruled out**, because `match.py` is explicit that an undocumented contraindication is
> unknown rather than ruled out. Not fixed here: the evidence quote is still the faintest element
> in the expander — that is P9-S6. See `DECISIONS.md`, 2026-09-10.

**And the checkmarks mean opposite things without saying so.** Four of the ten Highmark criteria
carry `polarity: absent`. The screen renders:

> ✅ **hho-05** — Seizure disorder or any history of seizure with increased risk of future seizure

To a non-clinician — which is most judges — that reads as *"✅ the patient has a seizure disorder"*,
the exact inverse of what it means. The reasoning text inside does disambiguate ("the note
explicitly confirms the absence of…"), but the collapsed label is what a viewer sees, and the
caption says `Met · contraindication`, where "Ruled out" is the true statement. The polarity is
already in the pack and already loaded; it simply never reaches the label.

### 2.5 Justification — impeccable, and unreadable

Ten claims, each an enormous run-on carrying up to 400 characters of quoted policy, and each
closing with the clause *"The record documents this for the requested repetitive transcranial
magnetic stimulation"* — repeated verbatim ten times down the page.

The construction is the point and must not change: it is assembled, not written, one claim per met
criterion, citing only verified spans. But presentation is not construction. As rendered it is
indistinguishable from legal boilerplate, and the span ids beneath each claim (`ps-04a-0, ps-04a-1,
ps-04a-2, ps-04a-3`) are unexplained grey italics.

### 2.6 The gates — the product's differentiator, styled as a form

`🔒 Gate 1 — clinician approval` is a subheader, a grey caption, a text input, and a disabled
button that is dark grey on a dark background and very hard to read as *disabled* in a recording.
The human-in-the-loop guarantee — non-negotiable per §6, enforced twice, hash-bound — carries less
visual weight on the page than the criteria expanders above it.

After approval the screen says only *"Submission packet approved and generated."* It does not say
who approved it, when, or against what content hash — **even though all three are computed and
written to `approval.json` on the same code path**. The audit trail exists and is not shown. That is
free credibility left on the floor.

### 2.7 Section 5 — asserts a denial that has not happened

The header reads **"5 · The payer denied it"** unconditionally, on every case, and it renders
*before* Gate 1 has been approved. Reading top to bottom on the clean case, a judge sees
"4 · Approve the submission" (not yet approved) immediately followed by "5 · The payer denied it"
(not true, and nothing was ever submitted).

Reading the code, the denial uploader and the **Draft the appeal** button depend on `coverage`, not
on `state["submission"]` — so the console will draft an appeal for a packet that was never
approved and never submitted. Gate 2 still holds independently and no document escapes without an
approval, so this is not a gate weakness. It is a sequencing hole in the story the screen tells,
and a sharp judge will find it.

### 2.8 Appeal — the best section in the app

Contested criteria are listed cleanly with the payer's stated reason. The unmapped-objection warning
is honest and well placed. The rebuttals are expanded by default, argue against the payer's own
policy section, and quote verified evidence. Keep the shape of this section; it is what the rest
should look like.

Two notes. The deadline banner mixes a hard fact with a longer disclaimer —
*"Appeal deadline: 2026-10-02 — 60 days from the determination. Window source: NOT STATED in policy
HHO-DE-MP-1147. Placeholder pending confirmation…"* — so the box reads as a caveat rather than as
"we are already tracking your clock." The honesty is right and must stay; the proportion is wrong.
And there is no days-remaining, which is the number a practice actually acts on.

### 2.9 Sidebar and chrome

**Open cases** lists bare identifiers — `SYNTH-001`, `SYNTH-003` — with no payer, no state, no
deadline. The case store is one of the more interesting things built and it surfaces as two opaque
strings. And **Reset this case** is offered on the landing screen, where there is no case to reset.

---

## 3 · What to do, in priority order

Mapped to the steps drafted in `PLAN.md`.

| Tier | Step | What it buys |
|---|---|---|
| **0 — viability** | ~~**P9-S8**~~ **done** | `verify.sh ALL --offline` exits zero again, keyless, so the README's instruction to judges stops being false. Gate passed at `84cb86e`. |
| **0 — blockers** | ~~**P9-S2**~~ **done** | The demo stops crashing. CRLF pinned and normalised; every engine call in the console has an error boundary. Gate passed at `f906041`. |
| **0 — correctness** | ~~**P9-S3**~~ **done** | The criteria screen stops saying the opposite of what it means, and becomes scannable. Gate passed at `2436618`. |
| **1 — first impression** | **P9-S4** | A judge understands the problem, the audience and the pipeline before clicking anything — on a phone too. |
| **2 — credibility** | **P9-S5** | The gates look like gates; the approval shows who, when and against what hash; section 5 stops asserting a denial that has not happened. |
| **3 — marquee** | **P9-S6** | The note renders with its verified spans highlighted in place. The strongest engineering claim, made visible without narration. |
| **3 — upside** | **P9-S7** | The agent becomes visible: which subagent, which tool, which model, how long — plus the before/after strip that P8-S3 owes. |

### The landing screen, concretely

Not a wall of prose. Four blocks above the fold:

1. **One sentence of what and who** — "Prior authorization, end to end, for practices with no PA
   staff" — with the three AMA numbers as three `st.metric`s. The problem is the pitch.
2. **The five-step pipeline as a visual**, with the two gates marked. This doubles as the
   architecture diagram P8-S2 already owes, and it is the "handles a task end to end, not just
   chat" requirement made legible.
3. **One primary action that works in one click.** Today's download-then-upload is four steps.
4. **The synthetic-data banner in the main column**, not only the sidebar, so it survives mobile.

### On pre-filling a sample case without reinstating a picker

`DECISIONS.md` (2026-09-10) already sanctions the fix and names its shape:

> If a demo ever needs to open on a populated case … the answer is a query parameter that
> *pre-fills the uploader* from the corpus, leaving the pipeline entry point unchanged. Reinstating
> a picker that sets the pack directly would put the bypass back.

That is exactly what P9-S4 should build. The distinction that matters is **what chooses the policy
pack**, not how many clicks reach the uploader. A button that loads a corpus file into the same
upload path, and then runs `find_pack` on what intake extracted, preserves every property P9-S1 was
built to protect: nothing is preloaded into the pipeline, the payer is still derived from a document
the model read, and an unlisted payer still stops the review.

The existing gates hold if this is built with buttons: `test_the_landing_screen_offers_no_case_to_pick`
asserts the absence of `app.radio` and `app.selectbox` specifically, and
`test_the_app_cannot_reach_the_corpus_at_all` forbids `attest.corpus`, `load_case` and `CASE_NAMES`
by name — so the sample must be read from `data_dir()`, as the download buttons already do.

### On highlighting evidence in the note

Every verified span already carries exact character offsets against the note text; the verifier
guarantees they are real. Rendering the note with those spans highlighted in place, colour-coded by
criterion, converts the product's central claim — *no clinical sentence exists that we cannot
underline in the source* — from a caption into a picture. It requires no new model call and no new
data. It is the one recommendation in this document worth building even if nothing else on the list
is done.

---

## 4 · Scope warning

**P8 outranks all of P9.** As of 2026-09-10 the submission deadline is four days away and
`P8-S1` (README), `P8-S2` (architecture diagram), `P8-S4` (demo video) and `P8-S5` (Devpost, which
needs an AWS Builder ID nobody has yet) are all mandatory and all `TODO`. Stage One judging is
pass/fail on baseline viability and required deliverables; a missing architecture diagram risks not
being scored at all, and no amount of console polish compensates for that.

Read the tiers above accordingly:

- **P9-S8 came before everything, including P8, and is done.** It was the smallest item on this
  list and the only one touching Stage One pass/fail. Its last DoD item — CI reporting success —
  needs the fix merged to `main`.
- **P9-S2 and P9-S3 were worth doing before the video is recorded, and are done** — one prevents a
  traceback on camera, the other stopped the core screen from stating the inverse of the truth.
  With P9-S8 that clears the whole of Tier 0; **everything below this line still ranks under P8.**
- **P9-S4** materially changes what a judge sees on the live link, and its pipeline visual is
  reusable as the P8-S2 diagram, so it pays for itself twice.
- **P9-S5 through P9-S7 are upside.** Build them if P8 is genuinely finished, and not before.
