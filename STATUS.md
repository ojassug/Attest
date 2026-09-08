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
| **Next step** | `P0-S1` (AWS setup — deadline-driven), then `P0-S4` (Bedrock smoke test) |
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
| P0-S3 | Repo skeleton, tooling, gate runner        | DONE   | Atharv| 93c3aa3  | 09-08 |
| P0-S4 | Bedrock smoke test                         | TODO   | —     | —        | —     |
| P1-S1 | Pydantic domain models                     | IN_PROGRESS | Atharv | —        | 09-08 |
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

**2026-09-08 — Atharv** *(session 1)*

`P0-S2` and `P0-S3` are done. The protocol is live and self-enforcing.

`./scripts/verify.sh` is the gate runner everything depends on. It reads the canonical step
order from `PLAN.md`, so `PLAN.md` really is the single contract — adding a step there without
adding a `STATUS.md` row and a pytest marker makes the gate fail. That was tested by deliberately
desyncing the files; both invariant tests fired and the gate exited 1.

Two behaviours worth knowing before you use it:

- **No tests is not a pass.** pytest exits 5 when nothing is collected; the gate converts that to
  a failure. A step with no test cannot be marked DONE. (`P0-S2` is the one exception, recorded as
  `pre-gate` — it predates the runner and is covered by `test_status_covers_all_plan_steps`.)
- **`--offline` skips the Bedrock tests and says so.** It prints that its result is NOT a valid
  gate pass. Never record a gate SHA from an offline run.

Environment: Python 3.12 in `.venv` (3.14 is the system default but is too new for the Strands
dependency tree). Set up with `python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"`.
`verify.sh` prefers `.venv/bin/pytest` automatically, so you do not need to activate anything.

**Next.** `P0-S1` is the priority — it is human-driven and the **$50 AWS credit form closes
Sep 11, 12:00pm PT**. It also picks the Bedrock model id, which `P0-S4` needs, so `P0-S4` is
blocked until someone with console access finishes `P0-S1`. Do not guess the model id; confirm it
with `aws bedrock list-foundation-models` as the DoD says — regional availability varies.

`P1` needs no AWS at all and can be started in parallel if `P0-S1` is stuck.

Nothing is mid-flight. Working tree is clean.
