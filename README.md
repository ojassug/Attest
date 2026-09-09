# Attest

**An AI agent that handles the prior-authorization lifecycle for small specialty practices** — from deciding whether a service needs a prior authorization (PA), to assembling a criteria-matched request, to auto-drafting the appeal when a payer denies.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status: in development](https://img.shields.io/badge/status-in%20development-yellow.svg)](STATUS.md)
[![Hackathon: Agents for Humans](https://img.shields.io/badge/AWS-Agents%20for%20Humans-orange.svg)](https://agentsforhumans.devpost.com)
[![Built with: Strands Agents](https://img.shields.io/badge/built%20with-Strands%20Agents-232f3e.svg)](https://github.com/strands-agents)

> **Project status — the full loop runs.** Phases **P0 through P5 are complete and gated**: a clinical note becomes a criteria-matched submission packet behind a clinician approval gate, and a payer denial becomes an evidence-backed appeal behind a second one. The whole suite — **268 tests** — replays offline from recorded model responses in about two seconds, **with no API key and no network**. Case tracking and the reviewer UI (P6) are what remain. See [Project status & roadmap](#project-status--roadmap), and [STATUS.md](STATUS.md) for the live board.

---

## Contents

- [The problem](#the-problem)
- [What Attest does](#what-attest-does)
- [Who it's for](#who-its-for)
- [How it works](#how-it-works)
- [Design principles](#design-principles)
- [Tech stack](#tech-stack)
- [Project status & roadmap](#project-status--roadmap)
- [Repository layout](#repository-layout)
- [Getting started](#getting-started)
- [Compliance, safety & scope](#compliance-safety--scope)
- [Hackathon context](#hackathon-context)
- [License](#license)

---

## The problem

Prior authorization is insurer pre-approval required before a clinician can deliver a covered service. It is the largest administrative time-sink in outpatient care, and small/solo specialty practices (behavioral health, physical therapy, occupational/speech therapy, pain, imaging) absorb it directly because they have no dedicated PA staff.

- Practices complete **~39–43 PA requests per physician per week** (AMA 2024/2025 surveys).
- **~13 hours/week** of physician + staff time is consumed by PA.
- **~31% of physicians** report requests are often or always denied — and denials have risen over five years.
- **Appeals work but are under-used** — many practices don't appeal because they expect to lose, and those who do rebuild each appeal from scratch.

Existing PA vendors target large health systems and deep EHR integrations. Solo and small practices are left with manual portals, faxes, and copy-paste appeal letters. The judgment-heavy part — *does this need a PA? does the note satisfy the payer's criteria? how do we rebut this specific denial?* — is exactly what current tooling leaves to a human. That is the gap Attest fills.

## What Attest does

Given a patient's clinical note and insurance details, Attest:

1. **Reads and structures the case** — service requested, diagnosis, requested duration/units, payer, and plan.
2. **Determines whether a prior authorization is required** for that service under that payer/plan, and explains why, pointing to the policy it relied on.
3. **Finds the payer's own clinical criteria** and **checks the note against each one**, marking each as *met*, *unmet*, or *insufficiently supported* — quoting the exact note evidence for each.
4. **Flags gaps** — where a criterion isn't supported, it says so and asks the practice for the missing detail rather than guessing.
5. **Assembles a submission-ready request** — completed request fields, a medical-necessity justification written *only* from approved evidence, and a plain-language checklist of how each criterion is covered.
6. **Pauses for the clinician to approve or edit** every clinical assertion before anything is submitted. *(Gate 1)*
7. **Produces the outbound submission artifact** once approved.
8. **Turns a denial into an appeal** — reads the denial reason, identifies which criteria the payer contests, and drafts an appeal citing the payer's own policy language and the note evidence — again held for human approval. *(Gate 2)*
9. **Tracks each case and its appeal deadline**, and reuses language from prior successful appeals on similar future denials.

**The goal:** cut the human time per PA from ~20–30 minutes to a short review-and-approve step, raise first-pass approval rates by mapping every submission to the payer's stated criteria before it goes out, and make appeals the default rather than the exception.

## Who it's for

- **Primary:** the office manager, front-desk staff, or owner-clinician at a **1–10 provider specialty practice** who personally handles PAs.
- **Secondary:** the treating clinician who must approve the clinical justification.
- **Specialty focus:** one specialty at a time, so the product speaks that specialty's language and payer rules precisely. The flagship demo case is **outpatient behavioral health — TMS (transcranial magnetic stimulation) for treatment-resistant depression**, whose criteria are among the most enumerable of any common PA (age, confirmed severe MDD, failed antidepressant trials at adequate dose and duration, psychotherapy trial, seizure/implant contraindications, baseline PHQ‑9/HAM‑D, FDA-cleared device). Physical therapy ships later as an extensibility pack to prove the engine is specialty-agnostic.

## How it works

The engine runs autonomously between two hard human-approval gates:

```mermaid
flowchart TD
    A["Clinical note + insurance details"] --> B["Intake: structure the case"]
    B --> C{"PA required?"}
    C -- "unmapped" --> C1["Return UNKNOWN<br/>(never assume 'not required')"]
    C -- "yes" --> D["Find the payer's clinical criteria"]
    D --> E["Match each criterion to note evidence<br/>met / unmet / insufficient"]
    E --> F["Deterministic evidence verifier<br/>every quote must appear verbatim in the note"]
    F --> G["Gap list: ask the practice for missing detail"]
    F --> H["Assemble submission packet<br/>medical-necessity justification from verified evidence only"]
    H --> GATE1{{"Gate 1 · clinician approves & edits"}}
    GATE1 --> I["Emit submission artifact (Markdown + PDF)"]
    I --> J["Payer denies"]
    J --> K["Parse denial → contested criteria"]
    K --> L["Draft appeal citing the payer's own policy + verified evidence"]
    L --> GATE2{{"Gate 2 · clinician approves & edits"}}
    GATE2 --> M["Emit appeal artifact + track appeal deadline"]

    classDef gate fill:#f6c343,stroke:#7a5901,color:#1a1a1a;
    class GATE1,GATE2 gate;
```

Attest is built as a multi-step, tool-using agent system on the **Strands Agents SDK**, with specialist agents (intake, criteria matching, packet assembly, appeal drafting) composed under an orchestrator. Both approval gates are implemented on Strands' first-class human-in-the-loop primitive (`BeforeToolCallEvent.interrupt(...)`), so the gate holds even when the agent is driven headlessly — it is a product requirement, not UI logic.

## Design principles

These are non-negotiable and encoded as tests, not aspirations:

- **The agent assembles and argues; humans decide and submit.** It never makes a coverage or medical-necessity decision on its own. Two hard gates — before submission and before an appeal is sent — require a clinician to review and approve every clinical assertion.
- **Evidence-traceable by design.** No clinical claim enters any document unless a **deterministic verifier** confirms the quote appears verbatim in the source note (whitespace runs and Markdown emphasis markers are treated as equivalent; nothing else is). A semantically correct paraphrase is *rejected on purpose* — paraphrase is the hallucination failure mode being defended against. Unverifiable spans downgrade their criterion to *insufficient* and are logged, never silently dropped.
- **Absence of a policy is not evidence that no PA is needed.** An unmapped service returns `UNKNOWN`, never "not required" — telling a practice "no PA needed" because a policy wasn't found is the worst possible failure.
- **The engine is specialty-agnostic; specialties are data.** Policy packs and extraction schemas are data files; no specialty knowledge is hardcoded. Adding a specialty costs a pack, not a rewrite.
- **Synthetic data only.** All notes and denial letters are synthetic and banner-marked; ground-truth expected outcomes are committed *before* any matching code exists, which is what makes every later step objectively verifiable. Live payer-portal / EHR integration and real-PHI handling are explicitly post-hackathon.

## Tech stack

| Area | Choice |
|---|---|
| Language | Python |
| Agent framework | `strands-agents`, `strands-agents-tools` |
| Model | **Gemini** via Google AI Studio — `gemini-3.5-flash-lite` (fast) and `gemini-3.6-flash` (reasoning). Amazon Bedrock is the intended provider and the swap is one constructor in `src/attest/llm.py` — nothing else names a provider. See [DECISIONS.md](DECISIONS.md). |
| Structured output | Strands structured output → Pydantic models (typed verdicts, never parsed from prose) |
| Human-in-the-loop | `BeforeToolCallEvent.interrupt(...)` |
| Deployment | **Amazon Bedrock AgentCore Runtime** (`BedrockAgentCoreApp` + `@app.entrypoint`) — planned, P7 |
| UI | **Streamlit**, hosted on Streamlit Community Cloud for a free, public, judge-testable link |
| Documents | `fpdf2` for the submission and appeal PDFs |
| Validation / data | `pydantic`, `pyyaml` |
| Testing | `pytest`, with every build step gated behind a cumulative test marker |

## Project status & roadmap

Work is organized into small, individually verifiable steps. A step is **done only when its gate (`./scripts/verify.sh <STEP_ID>`) exits zero** — running that step's tests plus every prior step's, so a later step cannot silently break an earlier one. The authoritative Definitions of Done live in [PLAN.md](PLAN.md); live progress lives in [STATUS.md](STATUS.md).

| Phase | Focus | State |
|---|---|---|
| **P0** | Foundation, model provider access, engineering protocol, repo skeleton | ✅ done |
| **P1** | Domain models, policy-pack format, real public TMS policies, synthetic corpus + ground truth | ✅ done |
| **P2** | Intake (note → structured case) and PA-required determination | ✅ done |
| **P3** ▲ | Criteria engine — per-criterion evidence matching + the deterministic verifier *(the core)* | ✅ done |
| **P4** ▲ | Packet assembly & Gate 1 (approval before submission) | ✅ done |
| **P5** ▲ | Denial → appeal loop & Gate 2 (approval before appeal) | ✅ done |
| **P6** ▲ | Case tracking, precedent reuse, Streamlit UI, public deploy | 🟡 next |
| — | **Submittable product complete through here** | |
| **P7** | Multi-agent orchestration depth + AgentCore deployment | ⬜ upside |
| **P8** | Submission deliverables (README, architecture diagram, metrics, demo video, Devpost) | ⬜ planned |

▲ = required for a viable submission.

**The submission and appeal loops both run end to end**, and every number below is reproducible from a clean clone with no credentials:

| Measure | Result |
|---|---|
| Criterion verdicts vs. committed ground truth | **30/30** across three cases and two payers |
| Evidence spans verifying verbatim against their note | **39/39 (100%)**, with zero criteria downgraded |
| Gap list vs. ground truth | exact on all three cases |
| Contested criteria parsed from the denial letter | exact — plus the one objection that maps to no criterion, surfaced rather than dropped |
| `./scripts/verify.sh ALL --offline` | exits zero, **268 tests**, ~2s, no API key |

The same command runs in CI on every push, on Linux, with no credentials configured — the judge's scenario rather than ours.

## Repository layout

Alongside the engine, the repository holds the product definition and the engineering protocol that lets two contributors hand work off cleanly across sessions and machines:

| File | Purpose |
|---|---|
| [`Attest-PRODUCT.md`](Attest-PRODUCT.md) | The product specification — what it is, what it must achieve, and the rules it must satisfy. No architecture or build planning. |
| [`PLAN.md`](PLAN.md) | The contract: every phase, step, and machine-checkable Definition of Done. Changes rarely. |
| [`STATUS.md`](STATUS.md) | The live status board — one row per step; the single source of truth for progress. |
| [`DECISIONS.md`](DECISIONS.md) | Append-only decision log — every non-obvious choice and the reasoning behind it. |
| [`LICENSE`](LICENSE) | Apache License 2.0. |
| [`src/attest/`](src/attest) | The engine: domain models, policy-pack loader, intake, criteria matching, the evidence verifier, and the gap list. |
| [`data/synthetic/`](data/synthetic) | Synthetic notes and denial letters, plus ground truth committed *before* the matching code existed. |
| `cassettes/` | Recorded model responses, so the whole suite replays offline with no API key and no quota. |
| [`scripts/verify.sh`](scripts/verify.sh) | The step gate. Runs a step's tests plus every prior step's. |
| [`docs/setup.md`](docs/setup.md) | Developer setup, model provider, and the daily-quota notes. |

Still to land: `src/attest/packet/` and `src/attest/appeal/` (P4–P5), the case store (P6-S1), and `app.py` for the Streamlit UI (P6-S3).

### Working protocol

This is a two-person, sequential build (one contributor works until their usage limit, then the other resumes on another machine). Because context is lost at every handoff, the three committed files above — plan, status, decisions — *are* the shared memory. A session starting cold reads `STATUS.md` → `DECISIONS.md` → `PLAN.md`, runs the gate for the last step marked done to verify (not trust) the previous session's claim, then continues.

## Getting started

The engine and its full test suite run today, offline, with **no API key and no network** — every model call replays from a recorded cassette. `python -m attest.demo` and the Streamlit UI land in P4 and P6-S3 respectively.

```bash
git clone https://github.com/ojassug/Attest.git
cd Attest
```

Python **3.12** specifically — 3.13+ is too new for the Strands dependency tree. CPython's `venv` writes executables to `bin/` on POSIX and `Scripts/` on Windows:

```bash
# macOS / Linux
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

```bash
# Windows
py -3.12 -m venv .venv && .venv/Scripts/python.exe -m pip install -e ".[dev]"
```

Then run the gate. It needs nothing else:

```bash
./scripts/verify.sh P3 --offline
```

> One test (`test_pa_tool_is_registered`) constructs a Strands `Agent` and so wants a credential to be *present* — it makes no request, so any placeholder in `.env` satisfies it. Without one the run is 184/185. This is a known open item, tracked in [DECISIONS.md](DECISIONS.md).

To re-record cassettes or run the three provider-connectivity tests you need a free [Google AI Studio](https://aistudio.google.com/apikey) key in `.env`. Note the free tier allows **20 requests per day per model** — see [`docs/setup.md`](docs/setup.md) for the model roster, rotation, and why cassettes exist. Amazon Bedrock is deferred to P7; `docs/aws-setup.md` will cover it then.

## Compliance, safety & scope

- **Privacy-first.** The product is designed around encryption in transit and at rest, least-privilege access, and a complete audit trail of every agent action and every human approval.
- **Synthetic data only for the hackathon.** No real patient data is used in the build or the demo video. Live payer-portal / EHR integration and real-PHI handling are explicitly post-hackathon, gated on the appropriate agreements.
- **Honest scope.** Attest is an assistant that produces submission-ready and appeal-ready documents *for human approval* — not an autonomous authority over care decisions.

**Explicitly out of scope:** it is not an EHR, practice-management, or billing/clearinghouse system; not a coverage or medical decision-maker; not a general healthcare chatbot; and it does no live payer/EHR integration or real-PHI handling in the hackathon build.

## Hackathon context

Attest is being built for the **AWS "Agents for Humans" hackathon** (sponsored by Amazon Web Services, administered by Devpost), in the **Professional Agents** track. The submission window runs **Aug 10 – Sep 14, 2026**. The hackathon requires a newly built agent on the **Strands Agents SDK** that does real work end to end; deploying with **Amazon Bedrock AgentCore** is optional but strengthens the technical-implementation score. Judging weighs Technical Implementation, Design, Potential Impact, Creativity & Originality, and Presentation equally.

## License

Licensed under the [Apache License 2.0](LICENSE).

---

*"Attest" is a working name and may change.*
