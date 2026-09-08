# Attest — Decision Log

> **Append-only.** Never edit or delete an entry; supersede it with a newer one that says what changed and why.
>
> This file exists because we work in alternating sessions on two machines. A decision made in conversation is
> invisible to the next session — it gets silently re-litigated or reversed. If the reason lives only in a chat
> window, it does not exist. Write it here in the same commit as the work.

**Format:** date · decision · why · what would change our mind.

---

## 2026-09-08 · Working sessions are sequential, not parallel

**Decision.** Two contributors on separate Claude subscriptions, alternating: one works until their usage limit is
exhausted, then the other resumes on a different machine.

**Why it matters.** This is a *cold-start handoff* problem, not a concurrency problem. There is no merge-conflict
risk worth designing around, but there is total context loss at every switch. Hence three committed files
(`PLAN.md` / `STATUS.md` / `DECISIONS.md`) and executable Definitions of Done.

---

## 2026-09-08 · A step is done when its gate exits zero

**Decision.** Every step maps to a pytest marker. `./scripts/verify.sh <STEP_ID>` runs that step's tests plus all
prior steps'. `STATUS.md` records the commit SHA at which the gate passed.

**Why.** "Done" judged by eye is not transferable across a session boundary. The incoming session runs the gate for
the last `DONE` step and *verifies the previous session's claim* instead of trusting it. A later step also cannot
silently break an earlier one, because the gate is cumulative.

**Consequence.** Every DoD item must be a file check, a command, or a named test. Anything reading "works
correctly" is not a DoD item.

---

## 2026-09-08 · Specialty: outpatient behavioral health, TMS for treatment-resistant depression

**Decision.** TMS is the flagship demo case. Physical therapy ships later as an extensibility pack only
(one policy pack, one worked case, one test) — not as a second product.

**Why.** `Attest-PRODUCT.md` §3 requires one specialty but names none. TMS criteria are the most enumerable and
near-binary of any common PA: age, confirmed severe MDD, failed ≥2 antidepressant trials at adequate dose and
duration in the current episode, psychotherapy trial, no seizure history, no ferromagnetic cranial implants,
baseline PHQ-9/HAM-D, FDA-cleared device.

The antidepressant-trial criterion is the centrepiece: the agent must read a medication history and reason about
whether each drug reached a therapeutic dose *and* was sustained long enough to count. That is real reasoning, not
keyword matching — and the canonical denial ("documentation does not establish adequate trials of two
antidepressants") yields an appeal that quotes doses and dates back at the payer.

PT's equivalent criterion ("documented functional progress") is fuzzier and easier to fake convincingly, which is
exactly the "criteria matching looks shallow" risk named in §9.

**Known wrinkle, stated openly rather than discovered on stage.** Evernorth/Cigna dropped PA for TMS effective
Mar 6, 2026. We build against payers that still require it (PacificSource, Highmark Health Options, BCBS MA,
AmeriHealth Caritas; CMS billing article A57528). Worth one line in the pitch — PA requirements churn constantly,
which is part of the burden being described.

**What would change our mind.** If sourcing two credible public TMS policies proves harder than expected in P1-S3,
PT is the fallback — the engine is specialty-agnostic by construction, so the swap costs a pack, not a rewrite.

---

## 2026-09-08 · The engine is specialty-agnostic; specialties are data

**Decision.** Policy packs and extraction schemas are data files. No specialty knowledge is hardcoded in agent
logic. P7-S2 asserts this with a test that the PT case runs with zero code changes.

**Why.** It makes the generality claim in the README true and testable rather than aspirational, and it costs
nothing extra if it is the design from step one.

---

## 2026-09-08 · Anti-hallucination is code, not a prompt

**Decision.** `src/attest/verifier.py` programmatically checks that every quoted evidence span appears verbatim
in the source note (under whitespace normalisation) before it may enter any document. Unverifiable spans downgrade
their criterion to `INSUFFICIENT` and are logged — never silently dropped, never softened.

**Why.** `Attest-PRODUCT.md` §6 makes evidence traceability non-negotiable. A model instruction is a hope; a
deterministic verifier is a guarantee. It is also the single most demonstrable trust feature in the video.

**Deliberate consequence.** A semantically correct paraphrase is *rejected*. That is the point — paraphrase is the
failure mode we are defending against. `test_paraphrase_is_rejected` encodes this so a future session does not
"fix" the verifier by loosening it.

---

## 2026-09-08 · Absence of a policy is not evidence that no PA is needed

**Decision.** `check_pa_required` returns `UNKNOWN` for an unmapped CPT, never `required=False`.

**Why.** Telling a practice "no prior authorization needed" because we failed to find a policy is the worst
possible failure — it causes an unreimbursed service. Encoded as `test_unmapped_cpt_returns_unknown_not_false`.

---

## 2026-09-08 · Stack: Strands + Bedrock + AgentCore, Streamlit UI

**Decision.** Python. `strands-agents`, `strands-agents-tools`, `bedrock-agentcore`. Streamlit for the UI, hosted
on Streamlit Community Cloud for the free public judge-testable link. AgentCore Runtime hosts the agent (P7).

**Verified against current Strands docs (2026-09-08), not from memory:**

- `from strands import Agent, tool`; model via `BedrockModel(model_id=..., region_name=...)`
- Structured output: `agent(prompt, structured_output_model=PydanticModel)` → `result.structured_output`.
  Every criterion verdict is produced this way — typed, never parsed out of prose.
- Human-in-the-loop is first-class: `BeforeToolCallEvent.interrupt(...)`. Both hard gates are built on this
  rather than on ad-hoc UI logic, so the gate holds even when the agent is driven headlessly.
- Multi-agent: `agent.as_tool(name=..., description=...)`, plus Graph / Swarm / Workflow primitives.
- Sessions: `SnapshotSessionManager` / `S3SessionManager`. **The docs warn these are not thread-safe and take no
  distributed lock** — hence one case, one session id, never shared.
- Deploy: `BedrockAgentCoreApp` + `@app.entrypoint`, local test on `:8080/invocations`, then
  `agentcore configure` / `launch` / `invoke`.

**Model id is not yet fixed.** Target Claude Opus 5 on Bedrock (Bedrock ids take an `anthropic.` prefix, and may
need a `us.` / `global.` cross-region prefix). P0-S1's DoD confirms the exact available id via
`aws bedrock list-foundation-models` before anything is hardcoded. Do not guess it — regional availability varies.

---

## 2026-09-08 · Build order is gated on a submittable core

**Decision.** P0–P6 is the required product. Do not start P7 (AgentCore deployment) until
`./scripts/verify.sh P6` is green.

**Why.** Six days, sequential rather than parallel work, ~36 steps. AgentCore deployment strengthens the Technical
Implementation score, but a half-deployed agent with no working demo scores nothing on any of the five criteria.
Depth on the criteria engine is worth more than breadth.

---

## 2026-09-08 · Synthetic data only, and the ground truth is committed

**Decision.** All notes and denial letters are synthetic, each carrying a
`SYNTHETIC — NOT REAL PATIENT DATA` banner enforced by a test. Expected outcomes for every case live in
`data/synthetic/expected/*.json` and are written in P1-S4, before any matching code exists.

**Why.** §7 of the product spec requires it. Separately, committing ground truth *first* is what makes every later
DoD objective — without it, "the criteria matcher works" is unfalsifiable and a session can mark a step done on
vibes.

---

## 2026-09-08 · Licence: Apache 2.0

**Decision.** Apache 2.0, added via PR #1.

**Why.** `Attest-PRODUCT.md` §1.4 requires "MIT or Apache" — either satisfies the rules. Apache 2.0 was the
collaborator's choice and there is no reason to churn it.

**Action still outstanding.** The rules require the licence to be **visible in the GitHub repo's About section**,
which is a repo setting, not just a file. Tracked in P8-S5.
