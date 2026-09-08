# Attest — Status Board

> **Single source of truth for progress.** Update this on every step transition.
> The contract (phases, steps, Definitions of Done) is in `PLAN.md`. The reasoning is in `DECISIONS.md`.

**Read this first if you are starting cold**, then `DECISIONS.md`, then `PLAN.md`.
Then run `./scripts/verify.sh <last DONE step>` to confirm the baseline is real before starting anything new.

---

## Current position

| | |
|---|---|
| **Phase** | P0, P1, P2 complete. **P3-S1 is next — the core phase.** |
| **Next step** | `P3-S1` — policy ingestion. Watch the Gemini daily quota. |
| **Blocking deadline** | AWS $50 credit request — **Sep 11, 2026, 12:00pm PT** (now a P8-S5 item, not a build blocker) |
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
| P3-S1 | Policy ingestion to draft criteria         | TODO   | —     | —        | —     |
| P3-S2 | Per-criterion evidence matching            | TODO   | —     | —        | —     |
| P3-S3 | Evidence-span verifier                     | TODO   | —     | —        | —     |
| P3-S4 | Verifier enforcement in the pipeline       | TODO   | —     | —        | —     |
| P3-S5 | Gap list                                   | TODO   | —     | —        | —     |
| P4-S1 | Justification from verified evidence only  | TODO   | —     | —        | —     |
| P4-S2 | Gate 1 — approval before submission        | TODO   | —     | —        | —     |
| P4-S3 | Submission artifact                        | TODO   | —     | —        | —     |
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

**2026-09-08 — Atharv** *(session 1)*

**P0-S2, P0-S3 and all of P1 are DONE.** Full `./scripts/verify.sh P1` is green: 82 tests.

What exists: the handoff protocol, the gate runner, Pydantic domain models, the policy-pack
schema and loader, two real TMS policy packs, and three synthetic cases with committed ground
truth.

**The project is now blocked on `P0-S1` (AWS).** P0-S4 and everything in P2 onward calls a model,
and the Bedrock model id comes out of P0-S1. Do not guess it — run
`aws bedrock list-foundation-models` as the DoD says; regional availability varies.

Things worth knowing before you touch this:

- **Ground truth is the standard, and it is deliberately written ahead of the code.**
  `data/synthetic/expected/*.json` says exactly what verdict every criterion must receive for
  every case. When P3's matcher disagrees, the matcher is wrong until proven otherwise. Do not
  edit ground truth to make a test pass without saying so in DECISIONS.md.
- **The gap case's gap is subtle on purpose.** `gap.md` asserts "An augmentation trial was
  attempted" with no agent, no dose and no duration. Correct behaviour is `INSUFFICIENT` on
  `ps-04b` plus a question to the practice — not a guess, and not failing the whole request.
- **The denial case is fully documented and denied anyway.** That is the point: the payer is
  wrong, and the appeal quotes the medication table and CBT dates back at Highmark's own policy
  language. If someone "fixes" that note to be genuinely deficient, the appeal demo dies.
- **Schema changed mid-phase.** `Criterion.polarity` and a required `PolicyPack.appeal_window_source`
  were added during P1-S3 — see DECISIONS.md. The cumulative gate caught the resulting fixture
  breakage in P1-S2 immediately, which is the protocol working.
- **Both appeal windows are unconfirmed placeholders.** Neither payer PDF states one. Fine for a
  synthetic demo; must be verified before any real filing.

Environment: Python 3.12 in `.venv`. `python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.
`verify.sh` finds `.venv/bin/pytest` on its own.

Nothing is mid-flight. Working tree is clean.
