# Attest — Status Board

> **Single source of truth for progress.** Update this on every step transition.
> The contract (phases, steps, Definitions of Done) is in `PLAN.md`. The reasoning is in `DECISIONS.md`.

**Read this first if you are starting cold**, then `DECISIONS.md`, then `PLAN.md`.
Then run `./scripts/verify.sh <last DONE step>` to confirm the baseline is real before starting anything new.

---

## Current position

| | |
|---|---|
| **Phase** | P0 — Foundation & protocol |
| **Next step** | `P0-S1` (AWS setup — deadline-driven) and `P0-S3` (repo skeleton) |
| **Blocking deadline** | AWS $50 credit request — **Sep 11, 2026, 12:00pm PT** |
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
| P0-S1 | AWS account, Bedrock access, credits, ID   | TODO   | —     | —        | —     |
| P0-S2 | Protocol documents                         | DONE   | Atharv| pre-gate | 09-08 |
| P0-S3 | Repo skeleton, tooling, gate runner        | TODO   | —     | —        | —     |
| P0-S4 | Bedrock smoke test                         | TODO   | —     | —        | —     |
| P1-S1 | Pydantic domain models                     | TODO   | —     | —        | —     |
| P1-S2 | Policy pack format and loader              | TODO   | —     | —        | —     |
| P1-S3 | Two TMS policy packs                       | TODO   | —     | —        | —     |
| P1-S4 | Synthetic corpus and ground truth          | TODO   | —     | —        | —     |
| P2-S1 | Note to structured Case                    | TODO   | —     | —        | —     |
| P2-S2 | PA-required determination                  | TODO   | —     | —        | —     |
| P2-S3 | Intake agent wiring                        | TODO   | —     | —        | —     |
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

**2026-09-08 — Atharv**

Planning session. Nothing built yet — `PLAN.md`, `STATUS.md`, and `DECISIONS.md` are the only artifacts, plus the pre-existing `Attest-PRODUCT.md`.

Two steps are unblocked and independent, so whoever picks up next can take either:

- **`P0-S1`** is human-driven (AWS console, forms) and **time-critical** — the $50 credit form closes Sep 11, 12:00pm PT. Do this one first if you have AWS console access.
- **`P0-S3`** is pure code and needs no AWS. Note it introduces `scripts/verify.sh`, which every later step depends on, so the whole project is gated behind it.

`P0-S2` is marked DONE with gate `pre-gate` because `verify.sh` does not exist yet — it is created in `P0-S3`. Once `P0-S3` lands, its `test_status_covers_all_plan_steps` test retroactively validates this file.

Nothing is mid-flight. The repo is clean.
