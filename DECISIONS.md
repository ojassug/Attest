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

---

## 2026-09-08 · Criteria carry a polarity; appeal windows must state their source

**Decision.** Two additions made during P1-S3, after authoring packs against real policies:

- `Criterion.polarity` (`present` / `absent`). A contraindication like "seizure disorder" is
  satisfied when the finding is **absent**. Without the distinction the matcher would report every
  healthy patient as failing every contraindication.
- `PolicyPack.appeal_window_source` is **required**. Neither retrieved policy PDF states an appeal
  window, so both packs currently record theirs as an unconfirmed placeholder.

**Why.** An invented filing deadline on a real appeal is worse than no deadline — it looks
authoritative and it is wrong. Making the provenance a required field means the gap stays visible
instead of decaying into an assumed fact. `test_appeal_window_states_its_source` holds it there.

**Outstanding.** Both windows (Highmark 60d, PacificSource 180d) are placeholders and must be
confirmed against the member appeal policy before any real filing. Not blocking for the demo,
which is synthetic throughout.

---

## 2026-09-08 · Packs are sourced from two payers on purpose

**Decision.** `highmark-hho-de-mp-1147` (Medicaid) and `pacificsource-commercial-tms` (Commercial).

**Why.** They set a materially different bar for the same service and diagnosis: Highmark requires
**four** psychopharmacologic trials plus a documented psychotherapy failure; PacificSource requires
**two** antidepressants of ≥8 weeks at therapeutic dose **plus** an augmentation trial, and has no
psychotherapy criterion at all. The same patient can clear one and fail the other.

That is the product's whole thesis — criteria are payer-specific, and matching them is the work.
Two packs that agreed would make the claim untestable. `test_packs_impose_materially_different_criteria`
and `test_highmark_requires_psychotherapy_failure_and_pacificsource_does_not` pin the difference.

---

## 2026-09-08 · Model provider is Gemini, not Bedrock — Bedrock deferred to P7

**Decision.** `build_model()` uses Strands' `GeminiModel` against a free Google AI Studio key.
Two tiers: `gemini-2.5-flash` for intake and denial parsing, `gemini-2.5-pro` for criterion
matching and appeal drafting. Both overridable via `ATTEST_MODEL_FAST` / `ATTEST_MODEL_REASONING`.

**Why.** Bedrock needs a full AWS account setup (IAM user, access keys, per-region model access)
that Atharv was not ready to do, and with the Sep 14 deadline the build could not sit idle waiting
for it. A Gemini key takes about a minute and needs no credit card. Claude Pro is a consumer plan
and carries no API access, so an Anthropic key was not available either.

**This costs us nothing on the rules.** §1.3 requires the **Strands Agents SDK**; Bedrock and
AgentCore are explicitly optional and only "strengthen" the Technical Implementation score
(`Attest-PRODUCT.md:29`, `:45`). AgentCore Runtime hosts *your code*, and that code may call any
model API — so a P7 AgentCore deployment remains available regardless of provider.

**Why two tiers.** The pipeline's demands are wildly uneven. Intake is field-pulling. Criterion
matching needs drug-class knowledge, therapeutic-dose judgement, date arithmetic against a
duration bar, and **exact verbatim quoting** — the verifier rejects paraphrase, and weaker models
paraphrase when asked to quote. Paying for reasoning only where it matters is free.

**Switching back is one file.** Nothing outside `src/attest/llm.py` names a provider. If the AWS
account gets set up, swap the constructor and the $50 credit covers the compute.

---

## 2026-09-08 · Strands' provider index page is stale — trust the per-provider page

**Decision.** The Gemini provider is `strands.models.gemini.GeminiModel`, installed with
`pip install 'strands-agents[gemini]'`.

**Why this is worth recording.** The docs contradict themselves. The model-providers index page
lists `strands.models.google.GoogleModel` under extra `google`; the dedicated Gemini page says
`strands.models.gemini.GeminiModel` under extra `gemini`. The second is correct — verified by
installing and enumerating `strands.models`, where `google` does not exist at all.

**How to apply.** When a Strands API detail matters, verify it against the installed package
rather than the index page. Do not spend a debugging cycle rediscovering this one.

---

## 2026-09-08 · Gemini free tier is 20 requests per DAY per model — hence cassettes

**Discovered.** Not 20/minute. `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, quotaValue 20.
A single full pipeline run over three cases makes roughly thirty calls, so the suite could not
otherwise be run even once a day.

**Decision.** `src/attest/cache.py` records every structured model response to `cassettes/`,
keyed by a hash of model id + full input. Cassettes are **committed**.

**Why this is a feature, not a workaround.** The rules require the project to be testable by
judges for free (`Attest-PRODUCT.md:42`). With cassettes committed, `./scripts/verify.sh ALL`
reproduces every result with no API key at all — verified by hiding `.env` and running the P2-S1
gate, which passed in 0.21s. Tests skip only when a call can be served neither by a key nor a
cassette; see `tests/conftest.py::model_available`.

Keys hash the full prompt and schema, so changing a prompt, a note, or a model invalidates the
entry automatically. A stale cassette cannot silently mask a regression.

`ATTEST_CACHE=off` bypasses; `ATTEST_CACHE=refresh` re-records.

**Model rotation.** Each model has its own daily quota, so `fast` moved to `gemini-3.7-flash`
after `gemini-3.5-flash` was exhausted. If quota becomes the bottleneck again, enabling billing on
the Google AI Studio key is the real fix — at flash pricing the entire project is a few dollars.

---

## 2026-09-08 · Never constrain a schema in a way that forces the model to invent

**What happened.** Intake extraction was intermittently returning an empty `cpt_codes`, so a
`min_length=1` constraint was added to force the model to fill it. The P2-S1 gate then failed on
the denial case — and the cause was not the model. `denial.md` contained **no CPT codes at all**,
and the constraint had forced the model to fabricate `90867` and `90868` from general knowledge of
TMS billing.

**Decision.** The constraint is removed. `cpt_codes` may be empty, its description explicitly
tells the model to return an empty list rather than supply codes typical for the service, and
`extract_case` raises `MissingFactError` when none are found.

**Why.** This is the precise failure the product exists to prevent, reproduced inside our own
code by a well-intentioned reliability fix. §6 of the spec requires the agent to *ask* when
evidence is missing, never assume. A schema constraint that makes absence unrepresentable
converts every missing fact into a confident fabrication.

Two tests hold the line: `test_absent_codes_are_reported_not_invented` (behaviour) and
`test_cpt_codes_are_not_forced_to_be_nonempty` (the schema itself, so the constraint cannot creep
back in as another flakiness fix).

**Ground truth was also wrong** and has been corrected — `denial.md` now states its requested
codes, as a real prior-authorization referral would. Flagged here because the protocol forbids
editing ground truth to make a test pass without saying so.

---

## 2026-09-08 · `live` means "cannot be replayed", and offline is a valid gate pass

**Superseded.** The original rule (P0-S3) said an `--offline` run was *not* a valid gate pass.
That predated cassettes and is now wrong.

**Decision.** The `live` marker means exactly one thing: **the assertion cannot be replayed from a
cassette**. Only provider-connectivity checks qualify — that tool calling and structured output
work against the real API, and that the agent genuinely invokes its tool rather than answering
from memory. A recorded response proves none of those.

Every other model-backed test replays from `cassettes/`. `./scripts/verify.sh <target> --offline`
therefore verifies all logic with no API key and **is** a valid gate pass.

**Why it changed.** Marking whole modules `live` meant every cumulative gate run burned daily
quota re-proving connectivity. With a 20-request daily cap per model, the gate became
self-defeating — running it exhausted the quota the next run needed. P2 now runs in 0.6s offline
versus two minutes and ~10 requests live.

It is also how a judge reproduces our results without credentials, which the rules require.

**Cache keys drop the model id** for the same reason: quotas are per model, so models get rotated,
and keying on the model id discarded every cassette each time. The producing model is recorded
inside each cassette instead, keeping results attributable for the P8-S3 metrics.

**Re-run live** after changing provider or model, and once before submission.

---

## 2026-09-08 · Not every policy requirement is checkable from a clinical note

**Observed during P3-S1.** Ingestion recovered all ten hand-authored Highmark criteria and found
four more the human pack omitted: an attendant trained in cardiac life support, resuscitation
equipment on site, emergency response times, and the maintenance-therapy exclusion.

**Decision.** They stay out of the shipped pack.

**Why.** They are real policy requirements but they are **facility attestations, not clinical
facts** — nothing in a patient's note could ever evidence them, so the matcher could only ever
return INSUFFICIENT and the gap list would ask the practice a question the note was never going
to answer.

This is a genuine product distinction worth naming in the pitch: a criterion the agent can check
against a note, versus one the practice attests to separately. Conflating them would make the
coverage checklist look permanently incomplete on cases that are in fact fully documented.

**Consequence for P3.** Ingestion recall is measured against note-checkable criteria only. If
facility criteria are ever added to a pack they need a separate attestation path, not evidence
matching.
