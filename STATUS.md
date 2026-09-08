# Attest — Status Board

> **Single source of truth for progress.** Update this on every step transition.
> The contract (phases, steps, Definitions of Done) is in `PLAN.md`. The reasoning is in `DECISIONS.md`.

**Read this first if you are starting cold**, then `DECISIONS.md`, then `PLAN.md`.
Then run `./scripts/verify.sh <last DONE step>` to confirm the baseline is real before starting anything new.

---

## Current position

| | |
|---|---|
| **Phase** | **P0–P4 complete.** **P5-S1 is next.** |
| **Next step** | `P5-S1` — denial parsing. First model-calling step since P3-S2; check quota. |
| **Blocking constraint** | Gemini free tier: **20 requests/day per model**. Four models spent on 09-08. |
| **Submission deadline** | **Sep 14, 2026, 5:00pm PT** |
| **Public demo URL** | not yet deployed |
| **Demo video URL** | not yet recorded |

---

## Status values

`TODO` · `IN_PROGRESS` · `BLOCKED` · `DONE`

A step becomes `DONE` only when `./scripts/verify.sh <STEP_ID>` exits zero. Record the commit SHA it passed at.

---

## Board

| Step  | Title                                      | Status | Owner | Gate SHA | Date  |
|-------|--------------------------------------------|--------|-------|----------|-------|
| P0-S1 | Model provider access (Gemini key)         | DONE   | Atharv| 65511ee  | 09-08 |
| P0-S2 | Protocol documents                         | DONE   | Atharv| pre-gate | 09-08 |
| P0-S3 | Repo skeleton, tooling, gate runner        | DONE   | Atharv| 93c3aa3  | 09-08 |
| P0-S4 | Model provider smoke test                  | DONE   | Atharv| 65511ee  | 09-08 |
| P1-S1 | Pydantic domain models                     | DONE   | Atharv| d666605  | 09-08 |
| P1-S2 | Policy pack format and loader              | DONE   | Atharv| 8e9bc2d  | 09-08 |
| P1-S3 | Two TMS policy packs                       | DONE   | Atharv| 0dba1ff  | 09-08 |
| P1-S4 | Synthetic corpus and ground truth          | DONE   | Atharv| 335ac1a  | 09-08 |
| P2-S1 | Note to structured Case                    | DONE   | Atharv| c84581b  | 09-08 |
| P2-S2 | PA-required determination                  | DONE   | Atharv| cb28e44  | 09-08 |
| P2-S3 | Intake agent wiring                        | DONE   | Atharv| 1b99b51  | 09-08 |
| P3-S1 | Policy ingestion to draft criteria         | DONE   | Atharv| e0f07e4  | 09-08 |
| P3-S2 | Per-criterion evidence matching            | DONE   | Atharv| a1358d9  | 09-08 |
| P3-S3 | Evidence-span verifier                     | DONE   | Atharv| 67c6b21  | 09-08 |
| P3-S4 | Verifier enforcement in the pipeline       | DONE   | Atharv| f80d422  | 09-08 |
| P3-S5 | Gap list                                   | DONE   | Atharv| 7385449  | 09-08 |
| P4-S1 | Justification from verified evidence only  | DONE   | Atharv| 86eb7d0  | 09-08 |
| P4-S2 | Gate 1 — approval before submission        | DONE   | Atharv| 6ae10bd  | 09-08 |
| P4-S3 | Submission artifact                        | DONE   | Atharv| 7a69618  | 09-08 |
| P5-S1 | Denial parsing                             | TODO   | —     | —        | —     |
| P5-S2 | Rebuttal drafting                          | TODO   | —     | —        | —     |
| P5-S3 | Gate 2 — approval before appeal            | TODO   | —     | —        | —     |
| P5-S4 | Appeal artifact and deadline               | TODO   | —     | —        | —     |
| P6-S1 | Case store                                 | TODO   | —     | —        | —     |
| P6-S2 | Precedent reuse                            | TODO   | —     | —        | —     |
| P6-S3 | Streamlit UI                               | TODO   | —     | —        | —     |
| P6-S4 | Public deploy for judges                   | TODO   | —     | —        | —     |
| P7-S1 | Orchestrator with specialist subagents     | TODO   | —     | —        | —     |
| P7-S2 | Physical-therapy extensibility pack        | TODO   | —     | —        | —     |
| P7-S3 | AgentCore entrypoint                       | IN_PROGRESS | Atharv | —   | 09-08 |
| P7-S4 | Deploy to AgentCore Runtime                | TODO   | —     | —        | —     |
| P8-S1 | README                                     | TODO   | —     | —        | —     |
| P8-S2 | Architecture diagram                       | TODO   | —     | —        | —     |
| P8-S3 | Impact metrics                             | TODO   | —     | —        | —     |
| P8-S4 | Demo video                                 | TODO   | —     | —        | —     |
| P8-S5 | Devpost submission                         | TODO   | —     | —        | —     |

**Submittable line:** everything through `P6-S4` is required. `P7` and `P8-S1..S3` are upside; `P8-S4` and `P8-S5` are mandatory to actually submit.

---

## HANDOFF NOTES

*The only prose in this file. Say exactly what you were doing when you stopped, especially if mid-step.*

---

**2026-09-08 — Atharv** *(session 2)*

**P0 through P4 are complete.** `./scripts/verify.sh P4 --offline` exits zero at **223 tests** in
about two seconds. The session-1 note below is still worth reading, but its specifics are
superseded — the count is no longer 146 and P3-S3 is long done.

### Read this before starting P5

**P5-S1 and P5-S2 cannot start without a Gemini API key.** `have_credentials()` is currently
`False`, there is no `.env` on this machine, and no `cassettes/` namespace exists for the appeal
path — so there is nothing to replay and the first run must be live. P5-S3 and P5-S4 are
deterministic and need no quota.

**Enable billing on the key before starting.** P5 is the most prompt-iteration-heavy phase left,
and every prompt change forces a cassette re-record. The free tier is 20 requests per day *per
model* and four models were already spent on 09-08. At flash pricing the whole project is a few
dollars; see `docs/setup.md`.

**P5-S4 will probably hit `ArtifactRenderError`.** fpdf2's core fonts are latin-1 only and the
denial letter contains em-dashes, so an appeal PDF quoting it will refuse to render rather than
silently substitute the character. That refusal is deliberate — see DECISIONS.md — and the fix is
`FPDF.add_font` with a Unicode TTF plus the font file. Budget ten minutes for it.

**PLAN.md's `live` annotations are stale.** It marks several P3–P5 tests `(marker live)`, but
DECISIONS.md reserves `live` for calls that genuinely cannot be replayed. Every step since P3-S2
has used `@needs_model` instead. Follow the code, not that annotation — and note PLAN.md itself
has *not* been corrected, which is a deliberate open item rather than an oversight.

### Two platform bugs, fixed before any feature work

The recorded baseline did not reproduce on Windows, so this session started by fixing that:

1. `verify.sh` probed only `.venv/bin/pytest` (POSIX) and exited **127** while printing
   `GATE FAILED`. A missing runner now exits 2; `GATE FAILED` again means only that tests failed.
2. Every `read_text()` omitted `encoding=`, so Windows used cp1252. That crashed on the policy
   text and, worse, silently changed the cassette cache key — so a machine holding every cassette
   demanded a live API key for every model-backed test. The offline gate was Linux-only.
   **Never remove an explicit `encoding="utf-8"`.**

### Known and still open

`test_p2_s3.py::test_pa_tool_is_registered` is not marked `live` but still needs a key to be
*present* — any dummy string works, no request is made. Measured: a keyless run is **222/223**,
with a placeholder **223/223**. Fixing it means either letting `build_model()` construct without a
key, which contradicts a recorded decision, or skipping the test without credentials, which
weakens the gate. Not decided.

### Where the product stands

- **Verification:** 39/39 spans verify verbatim (100%) with **zero** criteria downgraded, so
  P3-S2's 30/30 ground-truth verdict accuracy is intact. Gap ids match ground truth exactly.
- **Gate 1 is enforced twice** — a `BeforeToolCallEvent` interrupt on the agent path, and an
  independent hash check in the emitter. Editing a packet after sign-off invalidates the approval.
- **Artifacts** emit as Markdown + PDF from one block list, so the checkable document and the sent
  document cannot drift.
- **P3-S3 through P4-S3 made zero model calls** — six consecutive steps, no quota touched.

### Not code, and overdue

- **AWS $50 credit form closes Sep 11, 12:00pm PT.** Not requested.
- **AWS Builder ID** — a required Devpost field. Not obtained.
- The Gemini key should be rotated; it was pasted into a chat transcript.
- `README.md` was brought up to date this session, but P8-S1 still owns the final pass.

---

**2026-09-08 — Atharv** *(session 1 — long session, ended on usage limit)*

**Done: all of P0, P1, P2, plus P3-S1 and P3-S2.** `./scripts/verify.sh P3-S2 --offline` is green:
146 tests in 0.5s, no API key needed.

**Next: `P3-S3`, the evidence-span verifier.** Good step to pick up on — it is fully
deterministic, needs no model calls and no quota, and it is the feature that makes the product's
central claim true rather than aspirational.

---

### Read DECISIONS.md before touching anything

Nine decisions are recorded there and several are counter-intuitive. The four that will bite you:

1. **Ground truth is authoritative. Never edit it to make a test pass.** It was wrong twice and
   the *model* was right both times — `denial.md` had no CPT codes, and `clean.md`/`gap.md` had no
   patient age. Both times the fix was to correct the note toward realism, not to relax the
   expectation. If you must change ground truth, say so in DECISIONS.md in the same commit.

2. **Never add a schema constraint that makes absence unrepresentable.** A `min_length=1` on
   `cpt_codes`, added to fix flakiness, forced the model to fabricate procedure codes for a note
   that stated none — the exact failure this product exists to prevent, reproduced in our own
   code. Two tests now guard it, one behavioural and one on the schema itself.

3. **`live` means "cannot be replayed from a cassette"** — provider connectivity only, three tests
   total. Everything else replays from `cassettes/`, so `--offline` **is** a valid gate pass. This
   supersedes the original P0-S3 rule that said otherwise.

4. **Facility criteria are deliberately excluded from packs.** Ingestion finds them (attendant
   training, resuscitation equipment) but nothing in a clinical note can ever evidence them, so
   they would sit permanently INSUFFICIENT and make complete cases look incomplete.

---

### The binding constraint: Gemini quota

**20 requests per day, per model.** Not per minute. Four models were spent on 09-08:
`gemini-3.5-flash`, `gemini-3.7-flash`, `gemini-3.6-flash`, and `gemini-3.8-flash` (currently the
reasoning tier, partially used).

Cassettes mean the *test suite* costs nothing — but **iteration does**, because changing a prompt
changes the cache key and forces a re-record.

If you hit 429:
- Rotate to an unused model in `DEFAULT_MODELS` (`src/attest/llm.py`). Cassettes are keyed on
  **tier**, not model id, so rotating no longer discards them. Remaining candidates:
  `gemini-3.1-flash-lite`, `gemini-omni-1.1-flash`, `gemini-3.5-flash-lite` (fast tier, partly used).
- Or wait for the daily reset.
- **The real fix is enabling billing** on the same Google AI Studio key. No code change, and at
  flash pricing the whole project is a few dollars. Recommended before P4/P5.

---

### State

- **Provider:** Gemini. `fast` = `gemini-3.5-flash-lite`, `reasoning` = `gemini-3.8-flash`.
  Bedrock deferred to P7 — AWS account not set up. Swapping is one constructor in
  `src/attest/llm.py`; nothing else names a provider.
- **Matching accuracy:** 30/30 verdicts correct across three cases and both payers.
- **Environment:** Python 3.12 in `.venv`. `python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.
- **Run the gate:** `./scripts/verify.sh P3-S2 --offline` should be green before you start.

**Outstanding, not blocking:** AWS Builder ID (required Devpost field), $50 AWS credit
(**Sep 11, 12:00pm PT**), and the Gemini API key should be rotated — it was pasted into a chat
transcript. See `docs/setup.md`.

Nothing is mid-flight. Working tree is clean.
