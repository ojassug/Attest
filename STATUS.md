# Attest — Status Board

> **Single source of truth for progress.** Update this on every step transition.
> The contract (phases, steps, Definitions of Done) is in `PLAN.md`. The reasoning is in `DECISIONS.md`.

**Read this first if you are starting cold**, then `DECISIONS.md`, then `PLAN.md`.
Then run `./scripts/verify.sh <last DONE step>` to confirm the baseline is real before starting anything new.

---

## Current position

| | |
|---|---|
| **Phase** | **P0–P6 complete.** Every required phase is done; the product is submittable. |
| **Next step** | `P8-S4` (demo video) and `P8-S5` (Devpost) — both mandatory. P7 / P8-S1..S3 are upside. |
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
| P7-S1 | Orchestrator with specialist subagents     | TODO   | —     | —        | —     |
| P7-S2 | Physical-therapy extensibility pack        | TODO   | —     | —        | —     |
| P7-S3 | AgentCore entrypoint                       | TODO   | —     | —        | —     |
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

**2026-09-09 — Atharv** *(session 3)*

**P0 through P6-S3 are complete.** `./scripts/verify.sh ALL --offline` exits zero at **297 tests**
in about eleven seconds, with no API key and no network. This session added the case store,
precedent reuse, and the Streamlit console — all three deterministic, **no quota spent at all.**

**P6-S4 landed too — the console is live at <https://attest.streamlit.app>, public, no key
needed. Every required phase (P0–P6) is complete and the product is submittable.** What remains is
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

The account is **still under AWS verification**. Nothing is misconfigured: credentials
authenticate, IAM has `AmazonBedrockFullAccess`, the region is right. Check with one call:

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

Nothing is mid-flight. Working tree is clean.
