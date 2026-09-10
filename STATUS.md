# Attest — Status Board

> **Single source of truth for progress.** Update this on every step transition.
> The contract (phases, steps, Definitions of Done) is in `PLAN.md`. The reasoning is in `DECISIONS.md`.

**Read this first if you are starting cold**, then `DECISIONS.md`, then `PLAN.md`.
Then run `./scripts/verify.sh <last DONE step>` to confirm the baseline is real before starting anything new.

---

## Current position

| | |
|---|---|
| **Phase** | **P0–P6 complete, plus P7-S1..S3 and P9-S1.** Product is submittable; P7-S4 is blocked on AWS. |
| **Next step** | `P8-S2` (architecture diagram), `P8-S4` (video), `P8-S5` (Devpost) — all mandatory. `P9-S8` and `P9-S2` are done; `P9-S3` is the last small one worth landing *before* the video is recorded. |
| **Blocking constraint** | Gemini free tier: **20 requests/day per model**. Four models spent on 09-08. |
| **Submission deadline** | **Sep 14, 2026, 5:00pm PT** |
| **Public demo URL** | **<https://attest.streamlit.app>** — live, public, no key needed |
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
| P5-S1 | Denial parsing                             | DONE   | Atharv| 1948ff8  | 09-09 |
| P5-S2 | Rebuttal drafting                          | DONE   | Atharv| f211ce8  | 09-09 |
| P5-S3 | Gate 2 — approval before appeal            | DONE   | Atharv| d1ef57e  | 09-09 |
| P5-S4 | Appeal artifact and deadline               | DONE   | Atharv| bf62963  | 09-09 |
| P6-S1 | Case store                                 | DONE   | Atharv| d06930f  | 09-09 |
| P6-S2 | Precedent reuse                            | DONE   | Atharv| be5f410  | 09-09 |
| P6-S3 | Streamlit UI                               | DONE   | Atharv| 721143f  | 09-09 |
| P6-S4 | Public deploy for judges                   | DONE   | ojassug| 1593eb7 | 09-09 |
| P7-S1 | Orchestrator with specialist subagents     | DONE   | Atharv| f8e50fb  | 09-09 |
| P7-S2 | Physical-therapy extensibility pack        | DONE   | Atharv| f8e50fb  | 09-09 |
| P7-S3 | AgentCore entrypoint                       | DONE   | Atharv| f8e50fb  | 09-09 |
| P7-S4 | Deploy to AgentCore Runtime                | BLOCKED| —     | —        | —     |
| P8-S1 | README                                     | TODO   | —     | —        | —     |
| P8-S2 | Architecture diagram                       | TODO   | —     | —        | —     |
| P8-S3 | Impact metrics                             | TODO   | —     | —        | —     |
| P8-S4 | Demo video                                 | TODO   | —     | —        | —     |
| P8-S5 | Devpost submission                         | TODO   | —     | —        | —     |
| P9-S1 | Upload-driven intake, nothing preloaded    | DONE   | Atharv| ec06236  | 09-10 |
| P9-S2 | Console survives a note it has never seen   | DONE   | ojassug| f906041  | 09-10 |
| P9-S3 | A criterion says what it means              | TODO   | —     | —        | —     |
| P9-S4 | Landing screen makes the case               | TODO   | —     | —        | —     |
| P9-S5 | Gates look like gates; approval provenance  | TODO   | —     | —        | —     |
| P9-S6 | The note shows its own evidence             | TODO   | —     | —        | —     |
| P9-S7 | The run shows the agent that produced it    | TODO   | —     | —        | —     |
| P9-S8 | The keyless gate is green again             | DONE   | ojassug| 84cb86e  | 09-10 |

**Submittable line:** everything through `P6-S4` is required, and **P0–P6 are now complete**.

**Corrected 09-09.** This line previously called `P8-S1..S3` upside. That was wrong and had been
since P0-S2: `Attest-PRODUCT.md` §1.4 lists a **README** and an **architecture diagram** among the
things you must submit, so **P8-S1, P8-S2, P8-S4 and P8-S5 are all mandatory**. Only **P8-S3**
(impact metrics) and **all of P7** are genuinely upside. Stage One is pass/fail on baseline
viability, so a missing architecture diagram risks not being scored at all.

---

## HANDOFF NOTES

*The only prose in this file. Say exactly what you were doing when you stopped, especially if mid-step.*

---

**2026-09-10 — ojassug** *(session 7)*

**A UI/UX review of the P9-S1 console is written up in `docs/uiux-review.md`, and P9-S2 through
P9-S7 are drafted in `PLAN.md` from it.** No code changed this session — the six new steps are
contract, not work done. `pyproject.toml` gained the six matching markers in the same commit,
because `test_p0_s3.py::test_every_step_has_a_marker` reads step ids straight out of `PLAN.md` and
would have taken the P0 gate red — and with it every cumulative run — the moment the headings
landed alone.

**Two findings in that review are demo-blockers, not design opinions.**

1. **On a Windows checkout, uploading the committed corpus file misses every cassette.**
   `.gitattributes` pins only `*.sh` to LF, so `git ls-files --eol PLAN.md` reads `i/lf w/crlf`:
   Markdown is CRLF in the working tree. `read_upload` decodes those bytes directly, giving 2424
   characters where `Path.read_text` — which recorded the cassettes and which every test uses —
   gives 2371. Different string, different `cache._key`, cassette miss, live call, and on a keyless
   run a `RuntimeError: No Gemini API key found` rendered as a traceback in the page. Reproduced on
   the first attempt. The hosted app is unaffected (Linux clone, LF both ways), so this bites
   whoever records the demo locally, and `docs/ui-checklist.md` tells them to do exactly the thing
   that fails.
2. **`app.py` catches only `MissingFactError`**, so any other failure renders a red traceback. A
   second one was reproduced by pointing `ATTEST_STORE_DIR` at a long path. P9-S1 made this more
   likely, not less: an open uploader invites a note the cassettes do not have.

**Both are fixed — P9-S2 is DONE, gate passed at `f906041`.** `.gitattributes` pins `*.md` to
`eol=lf`, `read_upload` normalises newlines after decoding, and every engine call in `app.py` runs
inside `guarded`, which renders a failure instead of raising it. `verify.sh ALL --offline` is
**361 passed, 5 deselected** and now passes on Windows as well as Linux.

Two things worth carrying forward. **The fix is at both ends on purpose:** the attribute fixes the
checkout, `read_upload` fixes the upload, and only the second survives a judge downloading a note,
re-saving it in Notepad, and uploading CRLF from a file git never touches. And **normalising the
corpus once and committing it would have fixed nothing** — the index was already LF; the smudge
happens on every checkout.

**A judge who uploads their own note now gets a sentence, not a stack trace:** the screen says the
note is not one of the recorded ones, explains that the demo replays recorded responses so it costs
nothing and needs no key, and expands the sample downloads underneath. Walked in a browser, not
only asserted. `docs/ui-checklist.md` §6 covers it.

Reasoning in `DECISIONS.md`, 2026-09-10.

**And a third, found while checking that the first two were not self-inflicted: the gate is red on
`main`, and has been for at least five runs.** `gh run list --branch main` reports `failure` on
every recent push including the P9-S1 merge. The most recent run says **`2 failed, 355 passed,
5 deselected`**, both failures in `tests/test_p7_s1.py`, both `RuntimeError: No Gemini API key
found`. `build_orchestrator` constructs Strands `Agent`s, `Agent` construction calls
`build_model()`, and neither test carries the `skipif` that `test_p0_s4.py` and `test_p2_s1.py`
define for exactly this. They are the only two tests in the repo that need a credential to check
something structural.

**That made two sentences in `README.md` false** — "exits zero, 357 tests, no API key" and "the
same command runs in CI on every push … the judge's scenario rather than ours" — on a public
repository that invites judges to clone and run exactly that command.
`.github/workflows/gate.yml` was built to catch this; it did, on every push, and nobody opened it.

**P9-S8 is DONE — gate passed at `84cb86e`.** `./scripts/verify.sh ALL --offline` now exits zero
with no `GOOGLE_API_KEY` and no `.env`: **357 passed, 5 deselected**. The fix was two lines of test
setup, not new design: `test_p2_s3.py` had already solved this at P2-S3 by injecting a placeholder
credential, on the grounds that constructing an `Agent` makes no request, and P7-S1 simply never
applied it. A `needs_key` skip was rejected — it would have left `agent.as_tool()` composition
unverified in the one environment that matters. Reasoning in `DECISIONS.md`, 2026-09-10.

**The count in that README sentence was right all along**: the command selects 357 tests and now
passes all 357, so no number needed correcting. Only "exits zero" had to become true.

**One item on the P9-S8 DoD is still open, and it needs a merge, not a commit:** *the `gate`
workflow reports success on the commit carrying this fix.* The workflow triggers on pushes to
`main` and on pull requests, so it has not run for this branch. Open a PR or merge, then check
`gh run list --branch main` — do not mark that box from a local pass.

**Local numbers on Windows, for whoever picks this up:** `verify.sh ALL --offline` reported
`15 failed, 342 passed` here. Normalising *only* the corpus line endings to LF took it to
`2 failed, 355 passed` — identical to CI. That is the experiment that pins finding 1: thirteen of
those fifteen were CRLF, and **the P6-S3 and P9-S1 gates do not pass on a Windows clone at all.**

**The deployed app is already the P9-S1 screen.** Session 6's note below says it still runs the old
picker until the branch is merged; that is now stale. <https://attest.streamlit.app> serves the
upload-driven console, and it was walked at desktop and at 375 px this session. Nobody has yet run
`docs/ui-checklist.md` against it end to end, so that item stands.

**Also worth knowing before the video:** four of the ten Highmark criteria carry `polarity: absent`,
and the screen renders a tick beside "Seizure disorder or any history of seizure" — which reads to
a non-clinician as the inverse of what was found. That is P9-S3, and it is a label change over data
already loaded.

---

**2026-09-10 — Atharv** *(session 6)*

**P9 is a new phase — "Final improvements" — and it is deliberately open.** It collects changes to
a product that already passes every gate, and more steps will be appended to it. `PLAN.md` says so
in the phase header so the next session does not read the single step as the whole phase.

**P9-S1 is DONE: the console no longer has preloaded cases.** The three-case radio is gone. A note
is uploaded, intake reads it, and the policy pack is chosen by `find_pack(cpt, payer, plan)` from
what the model extracted — so uploading a PacificSource note and a Highmark note into the same
unchanged screen reaches two different policies. The denial letter is a second upload at step 5,
which is also how it arrives in a practice. Reasoning in `DECISIONS.md`, 2026-09-10.

**What this cost, and what it did not.** `tests/test_p6_s3.py` drove the app through the radio's
session-state key, so its helpers were rewritten to upload the corpus files through `AppTest`'s
`FileUploader.set_value()`. Every assertion in it is unchanged in substance — only the way a case
reaches the screen differs. **No engine code changed**; the diff is `app.py`, two test modules, one
pytest marker, and the docs.

**The uploads read the committed corpus files byte-for-byte, which is what keeps the demo free.**
Cassette keys hash the note text, so an uploaded `clean.md` hits the same cassette the radio used
to. Re-type a note, export it via a PDF round-trip, or edit one character, and it is a live API
call against a 20-request daily cap. If the hosted app ever asks for a key, this is the first
thing to check.

**A judge with no note of their own can still use the public deploy.** The landing screen offers
the synthetic notes and the denial letter as *downloads* — they are never loaded into the pipeline,
which is the whole point of the step. `test_the_landing_screen_hands_a_stranger_a_note_to_try`
holds that door open, because an upload-only screen with nothing to upload would be untestable by
exactly the audience P6-S4 deployed it for.

**Not done, and it is a real gap:** the deployed app at <https://attest.streamlit.app> still runs
the old picker until this branch is merged and redeployed, and nobody has walked the rewritten
`docs/ui-checklist.md` against the deployed app. `docs/deploy.md` is emphatic that a 200 is not
sufficient — the first deploy returned 200 over a `FileNotFoundError`.

---

**2026-09-09 — Atharv** *(session 3)*

**P0 through P6-S3 are complete.** `./scripts/verify.sh ALL --offline` exits zero at **297 tests**
in about eleven seconds, with no API key and no network. This session added the case store,
precedent reuse, and the Streamlit console — all three deterministic, **no quota spent at all.**

**P6-S4 landed too — the console is live at <https://attest.streamlit.app>, public, no key
needed. Every required phase (P0–P6) is complete and the product is submittable.**

**P7-S1 through P7-S3 are also done** — the `agent.as_tool()` orchestrator, the physical-therapy
extensibility pack, and the AgentCore entrypoint. 340 tests. Both P7-S1 live tests pass.

**P7-S4 is BLOCKED and not on anything in this repo.** `agentcore configure/launch/invoke` needs,
on one machine: AWS credentials, Docker, `bedrock-agentcore-starter-toolkit` (which provides the
`agentcore` CLI and is deliberately *not* a declared dependency), **and** Bedrock model access,
which is still `authorizationStatus: NOT_AUTHORIZED` account-wide pending AWS verification.
`agent_runtime.py` is ready and verified locally against the DoD's own curl command, so P7-S4 is a
deployment errand, not a coding one.

**Session 5 (09-10) re-check.** AWS credentials now exist on Ojas's machine and authenticate —
account `847169883477`, user `ojassugur`, us-west-2 — so the "no credentials" half of that
blocker is gone; Docker and `bedrock-agentcore-starter-toolkit` are still unhandled. **Bedrock
authorization has not moved.** `anthropic.claude-opus-5` and `anthropic.claude-sonnet-5` both still
read `NOT_AUTHORIZED` / `agreementAvailability: NOT_AVAILABLE`, and a live `bedrock-runtime
converse` on `us.anthropic.claude-sonnet-5` fails with `ValidationException: Operation not
allowed`. The control plane is healthy (`list-foundation-models` returns 116), so this is AWS's
gate, not our configuration. Poll it with one command — no venv, and note boto3 is **not**
installed, so the `boto3` snippet further down will not run as written:

```bash
aws bedrock get-foundation-model-availability --model-id anthropic.claude-opus-5 --region us-west-2 --query authorizationStatus --output text
```

**The AWS credit came through on 09-10: $170 total, expiring Oct 31.** The Bedrock swap is no
longer deadline-bound. Remember `AUTHORIZED` is only the first gate — model access still has to
be enabled in the Bedrock console afterwards.

**Quota, if you pick up model work.** `gemini-3.6-flash` and `gemini-3.5-flash-lite` were exhausted
on 09-09. Parity passed on `ATTEST_MODEL_REASONING=gemini-3.7-flash` /
`ATTEST_MODEL_FAST=gemini-3.1-flash-lite`. Still unused: `gemini-omni-1.1-flash`, `gemini-3.8-flash`
(the 503-prone one). Everything is cassetted, so only *new* prompts cost anything. What remains is
mandatory but not code: **the demo video (P8-S4) and the Devpost submission (P8-S5)**, which needs
an AWS Builder ID nobody has obtained yet.

**Checking the live app with curl needs a cookie jar** (`-c/-b`). Streamlit mints an anonymous
session via a redirect to `/-/auth/app`; without stored cookies curl loops and exits 47, which
looks exactly like a private app. See `docs/deploy.md`.

---

### Do this first

```bash
git pull
.venv/bin/pip install -e ".[dev]"      # see the venv note below
./scripts/verify.sh ALL --offline      # expect 297 passed
streamlit run app.py                   # then walk docs/ui-checklist.md
```

**The venv sync is not optional.** This session started with 15 failures on `verify.sh P4`, all
`ModuleNotFoundError` from `packet/emit.py`. Nothing was wrong with the code — `fpdf2` was declared
in `pyproject.toml` for P4-S3 but the local `.venv` predated it. Re-running the editable install
fixed it. Any gate failure that is a `ModuleNotFoundError` is this, not a regression.

---

### Finishing P6-S4 — the last required step

Full instructions in **`docs/deploy.md`**. Short version: push to GitHub, deploy `app.py` on
[share.streamlit.io](https://share.streamlit.io), leave Secrets **empty**, then `curl -sf <URL>`
and record the URL in `README.md` and in the Public demo URL row above.

Everything code-side is ready: `requirements.txt` is one line (`.`) so the deployed environment
installs from `pyproject.toml` and cannot drift, and the app needs no credentials because every
model call replays from committed cassettes. If the deployed app ever asks for a key, a live call
has crept back in — find it rather than adding a key.

---

### What P6 actually built

- **`src/attest/store.py`** — one Strands session per case. A case id that cannot be a session id
  is *refused, never slugified*: `SYNTH/001` and `SYNTH-001` would collapse onto one session and
  silently serve one patient's record for another's. Partitioning is the whole safety model here,
  because Strands session managers take no lock.
- **`src/attest/appeal/precedent.py`** — an appeal becomes precedent only if its approval hash
  still matches its content. Approve, edit, and a presence check would pass unapproved language to
  the next case wearing a signature. Note "approved" is **not** "successful" — nothing tracks payer
  outcomes, and `Appeal.outcome` was deliberately not invented.
- **`app.py`** — the whole loop on one screen, driven in tests by Streamlit's `AppTest` rather than
  smoke-imported. The UI cannot weaken a gate: approving builds a real `ApprovalRecord` and calls
  the same emitters the tests use.

---

### Landmines added this session

**`store_dir()` resolves per call, and must keep doing so.** It was a module-level constant bound
at import, so the UI tests set `$ATTEST_STORE_DIR` too late and the app wrote cases into the repo —
silently, because the data went somewhere real, just not where it was asked to. A hosted deploy
redirecting the store would have failed the same way. `test_the_store_directory_is_read_per_call`
sets the variable *after* import, which is the only ordering that reproduces it.

**Do not style `PARequirement.UNKNOWN` as a success in the UI.** Green means "no authorization
needed", which is the failure UNKNOWN exists to prevent, reintroduced in CSS.

---

**2026-09-09 — Atharv** *(session 2, spanning 09-08 and 09-09)*

**P0 through P5 are complete.** `./scripts/verify.sh ALL --offline` exits zero at **268 tests** in
about two seconds, **with no API key and no network**. CI runs that same command on Linux on every
push. The session-1 note below is history now — its counts and "next step" are long superseded.

The full loop runs: note -> intake -> PA determination -> criteria matching -> span verification ->
gap list -> justification -> **Gate 1** -> submission artifact (Markdown + PDF) -> denial parsing ->
rebuttal drafting -> **Gate 2** -> appeal with a deadline.

---

### Start here

```bash
git pull
./scripts/verify.sh ALL --offline      # expect 268 passed; needs nothing
```

If that is green you have a working baseline and can start **P6-S1 (case store)**. Every remaining
step in P6 is deterministic — **no model calls, no quota, no credentials needed.**
*(Session 3 note: P6-S1 through P6-S3 are now done. This paragraph is history.)*

---

### The provider situation — read before touching `llm.py`

**We are on Gemini and want to be on Bedrock.** Bedrock was originally deferred because the AWS
account did not exist. It exists now, but:

    authorizationStatus: NOT_AUTHORIZED     <- account-wide, every model
    agreementAvailability: NOT_AVAILABLE
    entitlementAvailability: AVAILABLE      <- eligibility is fine
    regionAvailability: AVAILABLE           <- us-west-2 is fine

The account is **still under AWS verification** *(re-checked 09-10 — unchanged; see the top
handoff note for the current reading and a CLI check that needs no boto3)*. Nothing is
misconfigured: credentials authenticate, IAM has `AmazonBedrockFullAccess`, the region is right.
Check with one call:

```python
boto3.client('bedrock', region_name='us-west-2').get_foundation_model_availability(
    modelId='anthropic.claude-opus-5')          # watch authorizationStatus
```

**When it flips to `AUTHORIZED`:** enable model access in the Bedrock console (a separate gate),
then swap the provider. The swap is small — **no production file outside `src/attest/llm.py`
constructs a model** — but four things change there: `DEFAULT_MODELS` (Bedrock ids carry an
inference-profile prefix; `us.anthropic.claude-opus-5` and `us.anthropic.claude-sonnet-5` are both
ACTIVE), the credential check (boto3 chain, not an API key), `build_model`, and **`is_retryable`,
which currently matches Gemini's `429 RESOURCE_EXHAUSTED` / `503` strings that Bedrock never
emits** — miss that and retries silently stop working.

**Then re-record.** Cassettes are keyed on the prompt, not the model, so all of them replay under
Bedrock and the gate goes green *having never called AWS*. That is a trap, not a win:

```bash
ATTEST_CACHE=refresh ./scripts/verify.sh ALL     # re-records and re-asserts ground truth
```

Ground-truth accuracy (30/30 verdicts) was measured on Gemini and is not guaranteed to transfer.
The gate will tell you exactly which criterion moved.

---

### Landmines

**`gemini-3.8-flash` returns `503 high demand` on structured output.** The reasoning tier is now
`gemini-3.6-flash`. `docs/setup.md` had already documented this while `DEFAULT_MODELS` still
pointed at the constrained model — cost an hour.

**A failing module-scoped pytest fixture re-runs for every test that uses it.** Six tests times
four retries burned ~24 API calls on a failure one direct call would have shown. Reproduce a
failing model call on its own, with retries off, before re-running a suite.

**Never remove an explicit `encoding="utf-8"`.** Python otherwise uses the locale default — cp1252
on Windows — which crashes on the policy text and, far worse, silently changes the cassette cache
key so a machine holding every cassette starts demanding live API calls.

**P5-S4 emits Markdown only.** If an appeal PDF is added it will raise `ArtifactRenderError`: the
denial letter contains em-dashes and fpdf2's core fonts are latin-1 only. That refusal is
deliberate — substituting a character inside a quoted passage would make the PDF disagree with the
note it quotes. The fix is a Unicode TTF via `FPDF.add_font`, about ten minutes.

---

### What is left

| | |
|---|---|
| **P6** ▲ | The last required phase. All four steps deterministic. |
| **P8-S4** | Demo video, ≤5 min, public on YouTube/Vimeo. **Mandatory.** |
| **P8-S5** | Devpost submission. **Mandatory.** Needs an AWS Builder ID. |
| P7, P8-S1..S3 | Upside only. Do not start until P6 is green. |

**Deadline: Sep 14, 2026, 5:00pm PT.** The $50 AWS credit form was submitted on 09-08.

**P6-S4 needs a public URL judges can reach** — that means a Streamlit Community Cloud account or
similar. Worth creating before you need it.

**Still outstanding:** an AWS Builder ID (a required Devpost field), and the Gemini key should be
rotated — the original was pasted into a chat transcript.

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

*(Session 5 note: the credit was approved on 09-10 — $170 total, expiring Oct 31. That deadline is
history. The Builder ID and the key rotation are still outstanding.)*

Nothing is mid-flight. Working tree is clean.
