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

---

## 2026-09-08 · Ground truth was wrong twice; the model was right both times

**What happened.** Two P1-S4 expectations failed against the matcher, and in both cases the data
was wrong, not the model:

1. `denial.md` listed no CPT codes at all, yet ground truth expected three (P2-S1).
2. Neither `clean.md` nor `gap.md` stated the patient's age, yet both expected `ps-02` (the
   18-or-older criterion) to be MET. The matcher correctly returned INSUFFICIENT.

**Decision.** Both notes were corrected — the denial note now states its requested codes and both
PacificSource notes state an age, as any real psychiatric evaluation would. The expectations were
**not** relaxed to match the output.

**Why this direction matters.** Editing ground truth to make a test pass converts the gate from a
standard into a mirror. The protocol requires saying so out loud when ground truth changes, which
is why both are recorded here. In each case the fix restored a *realistic* note rather than a
convenient one.

**Worth noting for the pitch.** The agent caught two documentation gaps that a human author
(me) had missed while deliberately trying to write complete notes. That is the product's actual
value proposition demonstrated against its own author.

**Result.** 30/30 criterion verdicts match ground truth across all three cases and both payers.

---

## 2026-09-08 · One batched call per case, not one call per criterion

**Decision.** `match_all` judges every criterion in a pack in a single model call.

**Why, beyond quota.** Highmark's `hho-03` is "ANY ONE of the following" across four alternatives.
A model shown one branch at a time cannot judge that correctly — it would have to decide whether
an alternative is satisfied without seeing the alternatives. Batching also lets the model reconcile
facts that bear on several criteria at once, which is how a human reviewer reads a note.

It happens to cut a full run from ~30 calls to 3, which is what makes the free tier survivable.

`match_criterion` remains for re-checking a single criterion after a practice answers a gap
question.

---

## 2026-09-08 · Every file read names its encoding; the offline gate was Linux-only

**What happened.** The P3-S2 baseline was recorded green offline — 146 tests, no API key. On the
Windows machine the same gate returned 5 failures and 28 errors. The claim was not false; it was
platform-specific, and nothing in the protocol could detect that.

**Root cause, single and shared.** Every `read_text()` in the project omitted `encoding=`. Python
uses the locale default, which is UTF-8 on Linux and cp1252 on Windows. Two failure modes followed
from that one omission:

1. **Hard crash.** `data/policies/raw/highmark-hho-de-mp-1147.txt` contains byte `0x9d`, which is
   undefined in cp1252 — `UnicodeDecodeError`. That was P3-S1.
2. **Silent corruption defeating the cassettes.** A note's `—` decoded as `â€"`, changing the
   SHA-256 payload in `cache._key()`. The cassette path no longer existed, so `cached_structured`
   fell through to `produce()`, which called `build_model()`, which demanded an API key. Every
   model-backed test therefore failed *as if uncached* on a machine that had every cassette.

**Decision.** All 16 reads and both writes now pass `encoding="utf-8"` explicitly. `.gitattributes`
pins `*.sh` to LF, because `core.autocrlf=true` on the Windows machine would smudge `verify.sh`
to CRLF and break its shebang.

**Why it mattered more than portability.** Rules §1.4 requires the project to install and run
consistently and be testable by judges for free. A judge on Windows got 33 errors and a demand for
an API key. This was a Stage One viability risk, not a convenience bug.

**Consequence.** Never rely on a locale default for any file this project reads. The cassette key
is a hash of decoded text, so *any* decoding difference silently converts a cache hit into a live
API call — the one thing the 20-request/day quota cannot absorb.

**Known and still open:** `test_p2_s3.py::test_pa_tool_is_registered` says "No API call" but calls
`build_intake_agent()` -> `build_model()`, which raises when no key is *present* (a dummy string
satisfies it; no request is made). So one non-`live` test still needs a credential to pass, which
contradicts the rule that `live` is the only marker allowed to require one. Left open deliberately:
the obvious fix — letting `build_model()` construct without a key — contradicts the recorded
decision that it should fail early with an actionable message rather than deep inside an agent run.

---

## 2026-09-08 · The verifier forgives whitespace and nothing else — and Markdown markup is the open question

**Decision (P3-S3).** `verify_span` matches a quote against the note verbatim, treating any run of
whitespace as equivalent to any other, and forgiving nothing else. Case differences, changed
numbers, substituted words and paraphrase all fail. Offsets are returned into the *original* note,
not the normalised copy, so a reviewer can land on the exact characters matched.

**Why whitespace specifically.** A model quoting honestly still flattens the note's line wrapping
and the double space after a full stop. Rejecting that would reject true evidence and make the
verifier useless. Whitespace is the only difference that carries no clinical content.

**Why nothing else.** A verifier that forgives case has started forgiving things, and the next
thing it forgives is a dose. `test_case_difference_is_rejected` and `test_paraphrase_is_rejected`
are tripwires against a future session deciding the verifier is "too strict".

**Measured on real matcher output: 38 of 39 spans verify (97.4%).** `gap` and `denial` are 100%.
The single rejection is on the `clean` case, and it is worth understanding before P3-S4:

    note:  **Evaluating provider:** Dr. R. Okonkwo, MD, board-certified psychiatrist
    model:   Evaluating provider:  Dr. R. Okonkwo, MD, board-certified psychiatrist

The model quoted the *rendered* text and dropped the Markdown emphasis markers. That is not a
paraphrase and not a fabrication — the clinical content is identical. But the notes are Markdown,
every bolded label in every note will hit this, and it lands on the one case whose entire purpose
is to demo a fully-documented approval.

**Open, to be decided in P3-S4** (which is the step that requires 100% of spans to verify):

- *Preferred:* treat Markdown emphasis markers as markup rather than content, and strip `**`/`*`/`_`
  when building the haystack, keeping offsets into the raw note. This is a lexical rule about
  syntax, not a semantic one about meaning, which is exactly the line that stops it being a
  slippery slope. It leaves every anti-fabrication guarantee intact.
- *Rejected:* re-prompting the model to include the markers. It costs quota to re-record every
  cassette and pushes a formatting concern into the model, where it will drift.
- *Rejected:* leaving it. `ps-01` would downgrade to INSUFFICIENT on the clean case, which is
  false — the note does document the criterion.

Deliberately NOT decided inside P3-S3: the step's DoD says "whitespace normalisation", and
widening the definition of verbatim is a change to the product's central claim. It belongs in the
step that owns enforcement, with the 100%-verification gate to prove it.

---

## 2026-09-08 · Markdown markup is syntax, not content — and the verifier is now binding

**Resolves the question left open by P3-S3.** The verifier drops Markdown emphasis characters
(`*`, `_`) from both the note and the quote before comparing.

**The evidence that settled it.** Every `*` run in all three notes is exactly two characters long —
always `**`, never a single or a triple — and `_` does not occur anywhere in the corpus. So the
rule is precise rather than speculative: it addresses the observed failure and nothing else.

**Why this is not the first step down a slope.** It is a *lexical* rule about markup characters,
not a semantic one about meaning. It cannot forgive a changed word, a changed number or a changed
case, because none of those are markup — `test_markup_tolerance_does_not_admit_paraphrase` pins
exactly that, using the same bolded line with one substituted word and one altered number.
**Known limit:** a literal underscore inside a word would also be dropped. No note contains one.

Offsets still bracket only the matched run. For `**PHQ-9:** 21` the match starts at the `P`, so
the leading `**` falls outside the offsets while the closing `**` sits inside them, and
`matched_text` reports that honestly rather than pretending the note is clean prose.

**Enforcement (P3-S4).** `enforce_verification(coverage, note) -> VerifiedCoverage` makes the
check binding. Any criterion carrying even one unverifiable span drops to `INSUFFICIENT` —
partly fabricated evidence is not partly trustworthy, and INSUFFICIENT is the honest verdict,
because it is a question for the practice rather than an argument with the payer.

A rejected span is removed from the returned coverage so nothing downstream can cite it, but it is
never *silently* dropped: it is written to the `attest.audit` logger with its quote and criterion
id, and stays reachable on `report.rejected`.

**Result: 39/39 spans verify verbatim (100%), across all three cases, with zero criteria
downgraded.** The 30/30 ground-truth verdict accuracy from P3-S2 is therefore untouched — nothing
was traded away to reach 100%. The one rejection P3-S3 measured was the false positive this
decision removed, not a real catch.

**Marker note.** `test_no_unverified_span_survives` is marked `needs_model`, not `live`, although
PLAN.md's DoD says `live`. It replays from cassettes, and the recorded decision reserves `live`
for calls that genuinely cannot be replayed. Same precedent as every P3-S2 test.

---

## 2026-09-08 · A gap is an INSUFFICIENT criterion, and it is built without a model

**Decision (P3-S5).** `build_gap_list(coverage)` emits one `GapItem` per criterion whose verdict is
`INSUFFICIENT`. `UNMET` is deliberately **not** a gap.

**Why the distinction decides who gets asked.** INSUFFICIENT means the note does not say enough to
tell — a question for the practice. UNMET means the note shows the requirement is genuinely not
satisfied — an argument to have with the payer. Asking a practice to document something the record
shows is absent sends them chasing a document that cannot exist. `test_unmet_is_not_a_gap` pins it.

**No model call.** `missing` is the matcher's own reasoning, carried straight through. The matcher
already worked out exactly what the note failed to establish — for `ps-04b` it names the agent, the
dose, the therapeutic-dose threshold and the 8-week duration — so a template could only be vaguer.
It is also free, which matters against a 20-request-per-day ceiling. The whole of P3-S3 through
P3-S5 therefore costs no quota at all.

**The question quotes the requirement verbatim** rather than summarising it. The practice is being
asked to satisfy the payer's words, and a paraphrased payer requirement is how the wrong document
gets pulled from the chart.

**Ordered by the pack, not by the coverage**, because the practice reads a gap list as a checklist
against the policy.

**Fails loudly** on an unknown pack or a criterion absent from it. A gap list built against the
wrong pack would quote one payer's requirements at another.

**Integration worth noting:** a criterion that P3-S4 downgraded for unverifiable evidence is
INSUFFICIENT, so it automatically becomes a gap. That closes the loop the verifier opened — a
criterion cannot be quietly stripped of its evidence and then never asked about.
`test_a_verifier_downgraded_criterion_becomes_a_gap` holds that door shut.

**Result: gap ids match ground truth exactly on all three cases** — `["ps-04b"]` for `gap`, empty
for `clean` and `denial`. `./scripts/verify.sh P3` exits zero at 185 tests. **P3, the phase the
product lives or dies on, is complete.**

---

## 2026-09-08 · The justification is built, not written — and that is what makes it safe

**Decision (P4-S1).** `build_justification(coverage, case)` is fully deterministic. One `Claim` per
`MET` criterion, in the policy's order, citing only spans the verifier marked `verified`.

**Why not have a model write it.** Three reasons, in order of weight:

1. **It makes the guarantee structural.** "Every referenced span is verified" is true by
   construction — there is no code path that emits a claim without evidence. A model would make it
   true by instruction, which is the distinction this whole product exists to draw.
2. **`Claim.supporting_span_ids` carries `min_length=1`.** Handing that to a model reproduces the
   exact failure already recorded here: a `min_length` on `cpt_codes` made the model fabricate
   procedure codes for a note that stated none. A schema constraint the model cannot satisfy
   honestly is a constraint that teaches it to lie — and here it would teach it to invent a span
   id, which is the single worst thing this document could contain.
3. **It costs no quota.** P3-S3 through P4-S1 now run with zero model calls.

The cost is prose that reads as structured rather than flowing. That is an acceptable trade for a
payer-facing document whose whole value is that every sentence is checkable.

**Only MET criteria become claims.** INSUFFICIENT is a question for the practice and belongs in the
gap list. UNMET is a criterion the note shows is *not* satisfied — arguing it would hand the payer
its own denial rationale.

**Fails in the safe direction.** Spans default to `verified=False`, so a coverage that skipped
`enforce_verification` produces an *empty* justification rather than an unverified one. An empty
document is recoverable; an unsupported one is not.
`test_a_coverage_that_never_went_through_the_verifier_yields_no_claims` pins that.

**Fails loudly on a case mismatch.** A justification built from another case's coverage would argue
the wrong patient, so `coverage.case_id != case.case_id` raises.

**The diagnosis is deliberately not repeated per claim.** It is one fact about the case; restating
it on all ten claims reads as machine output. It belongs in the packet header, emitted once in
P4-S3.

**Measured:** clean 10 claims / 15 spans, gap 9 / 12, denial 10 / 11 — every cited span verified in
all three cases. `./scripts/verify.sh P4-S1 --offline` exits zero at 197 tests.

---

## 2026-09-08 · Gate 1 is enforced twice, and the hash is what makes an approval mean anything

**Decision (P4-S2).** Human approval before submission is enforced in two independent places:

1. **The agent path.** `SubmissionGate` (a Strands `HookProvider`) registers on
   `BeforeToolCallEvent` and calls `event.interrupt("gate1_submission", ...)` before
   `emit_submission_artifact`. Strands raises `InterruptException`, stops the event loop, and
   returns the interrupt to the caller — so the tool never runs, and the gate holds even when the
   agent is driven headlessly with no UI in the loop to remember to ask.
2. **The emitter.** `emit_submission_artifact` independently refuses to write unless the packet
   carries an `ApprovalRecord` whose hash matches the content in front of it.

**Why both.** Each alone leaves a way around. The hook guards only the agent path — a direct call
to the emitter bypasses it entirely. The emitter guards only the filesystem — it cannot stop an
agent from trying, or ask a human anything. `Attest-PRODUCT.md` §6 calls this non-negotiable
product behaviour, and non-negotiable means it should not depend on which entry point was used.

**The content hash is the load-bearing part.** Without it an `ApprovalRecord` proves an approval
happened at *some* point. With it, it proves a clinician approved *this* content — so editing the
packet after sign-off invalidates the approval rather than riding on it.
`test_tampering_after_approval_is_refused` approves one packet, emits another, and requires the
refusal.

`content_hash` **excludes the `approval` field**, which is not fastidiousness but necessity: the
record contains the hash, so including it would be circular — attaching the approval would change
the hash stored inside that approval. The dump is canonicalised (sorted keys, no incidental
whitespace) so a packet always hashes the same way regardless of field construction order.

**Refusal is not silence.** An empty or blank approver sets `cancel_tool` rather than falling
through. "Nobody said yes" must never be treated as "nobody said no" — the same reasoning that
makes `PARequirement.UNKNOWN` exist.

**Validation happens strictly before anything is created**, so a refused emit leaves no directory,
no empty file, and nothing that could be mistaken for a partial submission.
`test_artifact_blocked_without_approval` asserts the output directory is still empty.

**How the approval reaches the emitter.** The hook is the only place that knows who approved and
when, so on resume it writes the `ApprovalRecord` into the tool's input against the packet the
human was actually shown. Without that wiring the agent path would approve and then fail at the
emitter, which is why it is pinned by a test rather than left implicit.

**Testable without a model.** `event.interrupt()` touches only `agent._interrupt_state`, so the
gate is exercised against a constructed `BeforeToolCallEvent` and a stub agent — real Strands
behaviour, no quota, no cassette. The full agent loop is left to P7's orchestrator tests.

**Note on scope.** `src/attest/packet/emit.py` exists now because Gate 1 is meaningless without
something to gate. It writes Markdown; **P4-S3 adds the PDF and the artifact-content
requirements.**

---

## 2026-09-08 · The artifact renders from one block list, and refuses rather than mangles

**Decision (P4-S3).** `emit_submission_artifact` builds a single ordered list of content blocks and
renders it twice — Markdown and PDF. There are not two templates.

**Why.** A payer reads the PDF; a machine checks the Markdown. If the two were written separately
they would drift, and the checkable artifact would stop being the one that was sent.

**Nothing is written until both render.** Documents are built in memory first, so a refused or
unrenderable emit leaves no directory, no empty file, and nothing that could be mistaken for a
partial submission.

### The latin-1 limit, and why it fails loudly

fpdf2's core fonts cover latin-1 only, fpdf2 ships no Unicode font, and **all four synthetic
documents contain em-dashes**. Verified against fpdf2 2.8.8: an em-dash raises
`FPDFUnicodeEncodingException` rather than degrading.

Substituting a character *inside a quoted passage* would make the PDF disagree with the note it
claims to quote — reintroducing, at the very last step, the exact failure the verifier exists to
prevent. So an unrenderable character raises `ArtifactRenderError` and writes nothing.

- Every string this module writes itself is ASCII, so the failure can only ever come from evidence
  or payer criteria, never from our own chrome.
- **No verified quote in the corpus currently contains a non-latin-1 character** (0 of 39), so this
  does not fire today.
- **P5 is where it likely bites**, because the appeal quotes the denial letter, which has em-dashes.
  The fix is `FPDF.add_font` with a Unicode TTF plus the font file — a few lines here, deliberately
  not done speculatively, and the error message names it.

### Evidence on unclaimed criteria

A test failure on real data caught this: `ps-04b` in the gap case is INSUFFICIENT but still carries
verified evidence — the note *does* say an augmentation trial happened, just not with what, at what
dose, or for how long. Only MET criteria become claims, so that quote reached no section of the
document.

Omitting it would make the record look thinner than it is. The coverage ledger now renders evidence
for any criterion no claim argued, and `test_each_verified_quote_appears_exactly_once` keeps it from
being printed twice. The result is that the gap case's artifact shows, in one place, that the
practice documented something, that it was not enough, and precisely what to send — which is the
product's whole thesis on one page.

**P4 is complete.** `./scripts/verify.sh P4` exits zero at 223 tests.

---

## 2026-09-09 · A criterion id the model proposes is not a criterion id until the pack agrees

**Decision (P5-S1).** `parse_denial` asks the model to split a denial letter into reasons and to
suggest which criterion each one disputes. `resolve_contested` then checks every suggestion against
the pack and demotes anything it cannot find to an unmapped reason.

**Why the check is code, not prompt.** This is the same discipline `attest.verifier` applies to
quotes: the model may point, but only our data confirms. A fabricated criterion id is worse than an
unmapped reason, because the appeal would then argue against something the payer never raised —
and it would look confident doing it.

**No reason is ever dropped.** `len(contested) + len(unmapped) == len(reasons)` always holds,
except where two paragraphs dispute one criterion, which becomes one contested criterion carrying
both. The unmapped reason is the important one: in the demo case it is a site-of-service
requirement that maps to no clinical criterion, and a practice that never hears about it will fix
the two clinical objections and be denied again for the same third thing.

**Empty string, not a required or nullable id.** `DraftReason.criterion_id` defaults to `""` and
the prompt says plainly that an empty string is a correct and expected answer. This is the lesson
already recorded here about `min_length` on `cpt_codes`: a schema that makes "none" unrepresentable
teaches the model to invent one. Making absence easy to express is what keeps the mapping honest.

**One call per letter, not per paragraph.** A model shown one paragraph at a time cannot tell a
second objection from a restatement of the first.

**A missing or unreadable date raises.** The appeal deadline is computed from it in P5-S4, so a
guessed date is a missed appeal.

**Result:** contested ids match ground truth exactly (`hho-03`, `hho-04`), the site-of-service
reason is surfaced as the single unmapped reason, and the determination date parses to 2026-08-03 —
all on the first live run, with no prompt iteration. `./scripts/verify.sh P5-S1 --offline` exits
zero at 234 tests.

**Provider note.** This cassette was recorded against Gemini. The AWS account is still under
verification (`authorizationStatus: NOT_AUTHORIZED` account-wide), so Bedrock could not be used.
When it clears, `ATTEST_CACHE=refresh` re-records and re-asserts this against Claude in one command.

---

## 2026-09-09 · The model writes the argument; code supplies everything checkable

**Decision (P5-S2).** In `draft_rebuttals` the model produces one thing — the argument prose.
Both fields a payer could check are supplied by code:

* `policy_citation` comes from the criterion in the pack, so "every citation resolves to a real
  `source_section`" is true by construction rather than by instruction.
* `supporting_span_ids` come from the verified coverage. `Rebuttal` carries `min_length=1` on that
  field, and handing that to a model reproduces the failure already recorded here, where a
  `min_length` on `cpt_codes` taught it to invent procedure codes. Here it would invent a span id —
  the worst thing an appeal could contain, because a payer who checks one citation and finds
  nothing dismisses the whole letter.

**A contested criterion with no verified evidence raises rather than drafting.** You cannot argue a
point you cannot evidence. If the payer contests something our own matcher found INSUFFICIENT, that
is a conversation with the practice, not an argument with the payer.

### Disclosed case changes in quoted prose are allowed; nothing else is

`test_the_argument_quotes_nothing_it_cannot_support` initially failed on three quotes. They were
not fabrications — every one resolved to **exactly verbatim** source text once a bracketed leading
capital was undone:

    argument: "[f]our psychopharmacologic trials have been completed during the current episode..."
    note:     "Four psychopharmacologic trials have been completed during the current episode..."

That is the standard convention for lowering a capital to embed a quote mid-sentence. The brackets
*announce* the alteration, which makes it the opposite of a silent paraphrase, and the words are
untouched. The test now resolves a disclosed leading case change and nothing else: an elision, an
inserted word, a changed number, or an *undisclosed* case change all still fail, and
`test_an_undisclosed_alteration_would_still_fail` guards the guard.

Same shape as the Markdown-markup decision in P3-S4 — a narrow lexical rule about a marked
convention, not a relaxation about meaning. It also leaves the structural guarantee untouched,
because the cited spans are code-supplied and independently verified.

### The reasoning tier moved to `gemini-3.6-flash`

`gemini-3.8-flash` returned `503 high demand` on every structured-output attempt. This was already
recorded in `docs/setup.md` ("`3.6` and `3.5` both work and both handle structured output
correctly") — the note existed and the default still pointed at the constrained model. Rotating
costs nothing: **cassettes are keyed on tier, not model id**, so no recording was discarded.

**Quota hazard worth knowing:** a module-scoped pytest fixture that raises is re-executed for every
test that depends on it. Six tests times four retries burned roughly two dozen calls on a failure
that a single call would have diagnosed. Reproduce a failing model call directly, with retries off,
before re-running a suite.

---

## 2026-09-09 · Two gates, one implementation, and they must not accept each other's approvals

**Decision (P5-S3).** Gate 2 mirrors Gate 1 exactly: `AppealGate` interrupts on
`BeforeToolCallEvent` before `emit_appeal_artifact`, and `emit_appeal_artifact` independently
refuses to write without an `ApprovalRecord` whose hash matches. Both gates now share one
implementation, `_ApprovalGate`, with subclasses supplying only the tool name, interrupt name,
payload key, document type and refusal message.

**Why refactor rather than copy.** The two gates differ in five strings and a summary block.
Duplicating forty lines of interrupt-and-record logic would mean a future fix to one gate silently
not applying to the other — and these are the two places in the product where "it silently did not
apply" is least acceptable. Gate 1's thirteen tests made the refactor verifiable rather than
hopeful; they passed unchanged.

**Separation is a property, not an accident.** Three tests pin it:

- `test_gate2_does_not_fire_on_the_submission_tool`
- `test_gate1_does_not_fire_on_the_appeal_tool`
- `test_an_approval_for_a_different_case_is_refused`

The last one matters most and comes free from the hash: `content_hash` covers `case_id`, so an
approval for one patient's appeal cannot authorise another's, and a Gate 1 packet approval can
never satisfy Gate 2. Two gates that accept each other's approvals are one gate wearing a disguise.

**`content_hash` now takes `Packet | Appeal`.** Both carry an `approval` field and nothing else in
common, and the function only ever needed `model_dump(exclude={"approval"})`. Generalising it was a
type change, not a behaviour change.

**Verified end to end:** an unapproved appeal writes nothing at all, and an approved one emits
`appeal.md` plus `approval.json` carrying the approver, an ISO timestamp and the content hash.
`./scripts/verify.sh P5-S3 --offline` exits zero at 257 tests.

---

## 2026-09-09 · A deadline travels with its provenance, and an unanswerable objection still travels

**Decision (P5-S4).** `appeal_deadline(denial_date, pack)` is the determination date plus
`pack.appeal_window_days`, read from the pack rather than assumed. The two shipped packs disagree —
Highmark 60 days, PacificSource 180 — so a constant would be wrong half the time and silently so.
`test_deadline_reads_the_window_from_the_pack_not_a_constant` compares the two packs so the
constant can never creep back in.

**`build_appeal` raises if any contested criterion has no rebuttal.** A partial appeal is the
dangerous shape: it looks complete, it is sent, and it is denied again on the objection nobody
answered — and the practice does not find out until the second denial.

### Two additions beyond the written DoD, both closing holes the product's own claims opened

**1. `Appeal.deadline_source`.** Neither payer's policy states an appeal window; both packs say so
in `appeal_window_source`, and `PolicyPack` gives the reason: *an invented deadline on an appeal is
worse than no deadline*. That warning was worthless while it lived only in the pack — the artifact
showed a confident date with no way to tell a policy-stated deadline from our placeholder. The
appeal now carries the source and prints it directly beneath the date. It also makes the artifact
renderable from the `Appeal` alone, which a document should be.

**2. `Appeal.unmapped_reasons`.** P5-S1 surfaces payer reasons that map to no criterion, on the
stated grounds that such a reason "is the one most likely to sink a resubmission, because the
practice never learns it was raised." But `Appeal` had nowhere to carry them, so they died at the
`Denial` and reached no document. A reason surfaced at parse time and dropped before the artifact
is still dropped — just later, and somewhere nobody is looking. They now appear under their own
heading, explicitly *not* rebutted, with a note that they need a separate response.

Both are additive fields with defaults, so nothing existing broke; `test_p1_s1` and the Gate 2
suite passed unchanged. Recorded here rather than done quietly because they are schema changes to a
P1 model made during P5.

**P5 is complete.** `./scripts/verify.sh P5 --offline` exits zero at 268 tests. The full loop runs:
note -> criteria -> verified evidence -> packet -> Gate 1 -> denial -> contested criteria ->
rebuttals -> Gate 2 -> appeal with a deadline.

---

## 2026-09-09 · A keyless clone now passes 268/268, and CI proves it on a second platform

**The open item is closed.** `test_p2_s3.py::test_pa_tool_is_registered` said "No API call" but
needed a credential to be *present*, because `build_model` refuses to construct without one. A
keyless clone therefore failed 1 of 268, which quietly made the "judges can clone and run it" claim
untrue.

The fix injects a placeholder credential in the test via `monkeypatch`. That keeps the test's
actual coverage — catching the tool silently falling off the agent — without weakening
`build_model`'s deliberate fail-early behaviour, which exists so a missing key reads as a setup
problem rather than as an auth error deep inside an agent run. Constructing an agent makes no
request, so any string does. The two alternatives were both worse: relaxing `build_model`
contradicts a recorded decision, and skipping the test without credentials removes the coverage
exactly where CI would need it.

**CI added: `.github/workflows/gate.yml`.** Fresh Linux checkout, Python 3.12, `pip install -e
".[dev]"`, then `./scripts/verify.sh ALL --offline`, with **no credentials configured for the job**.

That combination is the point. It is the judge's scenario rather than ours, and it makes rules
§1.4 — "must install and run consistently" — a check instead of a claim. It would also have caught
the encoding bug that opened this session: the baseline was green on Linux while every file read
omitted `encoding=`, which crashed on Windows and silently changed the cassette cache key. A single
developer machine could not see that; two platforms can.

If that CI step ever needs a key added to pass, the offline claim has stopped being true and the
cause should be found rather than the key added.

**PLAN.md marker annotations corrected.** Eight DoD items said `(marker live)` where the code uses
`needs_model`, and one uses `needs_key`. They were written before the distinction existed. PLAN is
the contract and changes rarely, but a contract that disagrees with the code is worse than one that
is edited — this is a refinement to match reality, recorded rather than done quietly. A new section
in PLAN's rules now states what the three markers mean and that exactly three tests carry `live`.
P7's annotations are deliberately untouched: those tests do not exist yet, and guessing their
marker would be inventing contract rather than recording it.

---

## 2026-09-09 · A case id that cannot be a session id is refused, never repaired

**Decision (P6-S1).** `session_id_for(case_id)` raises `CaseIdError` on a case id carrying a path
separator, surrounding whitespace, or a relative-path segment. It does not slugify it.

**Why refusing beats repairing, here specifically.** Sanitising is the friendlier-looking option and
it is the dangerous one. `SYNTH/001` and `SYNTH-001` both flatten to `SYNTH-001`, so the second case
saved overwrites the first and the store then serves one patient's record for another's — with no
error at any point. PLAN's own note for this step says why there is no other defence: Strands'
session managers are not thread-safe and take no distributed lock, so *partitioning is the whole
safety model*. A mapping that can collide has removed it.

A refusal is recoverable in a way a collision is not. The same reasoning as `PARequirement.UNKNOWN`:
when the honest answer is "this input cannot be represented", inventing a representation is worse
than stopping.

**The invariant is checked again on the way out.** `load_case` re-reads the stored case's `case_id`
and raises if it disagrees with the id it was filed under. Only an out-of-band write can produce
that, which is exactly when a store that answers anyway does the most damage.
`test_a_misfiled_case_is_refused_not_served` holds it.

**`load_case` returns `None` for an unknown case but raises for a damaged one.** "No such case" is
an ordinary answer a UI must be able to get. A snapshot that no longer validates as a `Case`, or
holds no case at all, is a corrupted record — returning it half-populated would put missing fields
into a document downstream, where the failure surfaces far from its cause.

**The `Agent` is a persistence vehicle, not a reasoning agent.** `SnapshotSessionManager` captures
and restores *agents*, so the case rides in agent state. That agent is never invoked and sends no
prompt, so it needs no credential — `test_store_needs_no_credentials` pins it, because a keyless
clone must be able to open a case and a bare `Agent()` constructs a `BedrockModel` by default.

It is deliberately built **without** `session_manager=`: passing it restores the stored snapshot
over the state just set, so `save_case` would write back the *previous* case. The explicit
`save_snapshot` / `restore_snapshot` pair also returns whether a snapshot existed, which is what
distinguishes "never saved" from "saved and empty".

**`list_cases` is an addition beyond the written DoD.** A case store that cannot be enumerated is
not a case store — P6-S3's UI has to render a case list, and without this it would reach into the
storage layout itself. It is the one place in the module coupled to Strands' session key layout, so
`test_saved_cases_are_listed` pins that: an upgrade that changes the layout fails a test instead of
quietly reporting that the practice has no open cases.

**Durability is tested across two real subprocesses**, not by clearing a cache in one. Every
in-memory store ever written passes a single-process round-trip; only a second interpreter tells
durability from a dictionary that happened to still be there.

**Known limit.** The store is a synchronous API built on `asyncio.run`, so it cannot be called from
inside a running event loop. Streamlit and the tests are synchronous, so this does not bite today;
an async caller needs the manager's coroutines directly.

`./scripts/verify.sh P6-S1 --offline` exits zero at **277 tests**.

---

## 2026-09-09 · Precedent is what a clinician approved — enforced by the hash, not the record

**Decision (P6-S2).** An appeal becomes precedent only when it carries an `ApprovalRecord` whose
hash **still matches its content**. `is_precedent` is that rule, and `find_precedents` is a filter
over the case store built on it.

**Why presence of the record is not enough.** Approve an appeal, edit the argument, and the record
is still attached — a presence check passes it, and language nobody signed is offered to the next
case wearing a clinician's signature. That is the same laundering route the gates' `content_hash`
closes at emit time, reopened at reuse time, and it deserved the same answer.
`test_an_appeal_edited_after_approval_is_not_precedent` seeds exactly that shape.

**"Approved" is not "successful", and the module says so rather than implying otherwise.**
`Attest-PRODUCT.md` §4.9 promises reuse of *prior successful* appeals. We know a human signed the
appeal; we do not know the payer overturned the denial, because nothing tracks outcomes. Precedent
is therefore offered as **language a clinician has already approved for this criterion**, never as
a winning template.

An `Appeal.outcome` field is the obvious next move and is **deliberately not invented here**.
Nothing in the demo could set it, and a field that is always `unknown` is worse than a stated
limit: it looks like the gap is covered. When outcomes are tracked, that field lands and
`find_precedents` prefers overturned appeals.

**No precedent index.** `find_precedents` reads the case store directly rather than maintaining a
second table. An index is a second source of truth that can disagree with the approved appeals it
indexes, and here that disagreement surfaces as an appeal citing language nobody approved. Scanning
is honest at the scale of a 1–10 provider practice; the day it is not, the fix is a cache derived
from the store, not a table written beside it.

**Ordering is most-recently-approved first**, with `appeal_id` breaking ties so the result is
stable. Payer criteria churn constantly — the decision log opens with Evernorth dropping PA for TMS
mid-build — so the newest approved language is the most likely to still fit.

### Consequential change to P6-S1's store

**An appeal is stored in its case's session, not a separate one.** They are one case, and
partitioning is per case. That made `save_case` read-modify-write rather than write-whole: it
previously replaced the session state outright, which would have discarded the appeal every time a
case was edited. `test_saving_an_appeal_does_not_discard_the_case` pins it, and the P6-S1 suite
passed unchanged through the refactor.

**`save_appeal` refuses an appeal whose case is not stored.** An orphan appeal would have its
language offered as precedent with no case behind it and nothing able to answer "which patient was
this?". Same shape as the gap list failing loudly on an unknown pack.

`./scripts/verify.sh P6-S2 --offline` exits zero at **287 tests**.

---

## 2026-09-09 · The console cannot be the place a gate gets weakened, and the UI is tested by driving it

**Decision (P6-S3).** `app.py` approves by building a real `ApprovalRecord` with a real
`content_hash` and calling the same `emit_submission_artifact` / `emit_appeal_artifact` the tests
exercise. There is no UI-side path to a document. Delete `app.py` and both gates are exactly as
strong as before.

**And the UI is tested by driving it, not by importing it.** The written DoD asks only for
`test_app_imports_without_error`, which proves the file parses. That is not enough for the screen a
clinician approves from, so `tests/test_p6_s3.py` uses Streamlit's `AppTest` to click the real
buttons.

The distinction is specific. `test_p4_s2.py` proves the gate refuses an unapproved packet — and it
would keep passing in front of a broken screen that renders an enabled approve button with no
approver, or that writes a document before anyone presses anything. Those are UI failures with
correct engine behaviour behind them, and only driving the UI catches them.
`test_gate_1_writes_nothing_until_a_clinician_is_named` asserts both halves: the control is disabled
*and* the output directory is empty.

**Found by writing those tests: `STORE_DIR` was bound at import.** The UI tests set
`$ATTEST_STORE_DIR` in a fixture, by which point `attest.store` was already imported, so the app
wrote cases into the repository instead of a scratch directory — silently, because the data went
somewhere real, just not where it was asked to. A hosted deploy redirecting the store to writable
space would have missed in the same way, on an ephemeral filesystem, with nothing to show for it.

`store_dir()` now resolves per call — explicit argument, then `$ATTEST_STORE_DIR`, then `sessions/`
— and `test_the_store_directory_is_read_per_call` sets the variable *after* import, which is the
only ordering that reproduces the bug.

**UNKNOWN is not styled as a negative.** The PA panel renders REQUIRED as an error, NOT_REQUIRED as
a success, and UNKNOWN as a warning. Colouring UNKNOWN green would tell a practice "no
authorization needed" because we failed to find a policy — the failure `PARequirement.UNKNOWN`
exists to prevent, reintroduced in CSS at the last step.

**Per-case state, keyed by case name.** Switching cases must never leave the previous case's
verdicts on screen; two payers with materially different criteria are one click apart, and a stale
coverage table would be read as this patient's. The checklist's fail conditions list it.

**`docs/ui-checklist.md` covers only what a test cannot see** — whether the screen *reads* correctly
to someone who has never used it, whether a quoted passage in the downloaded PDF still matches the
note character for character, whether the synthetic-data banner is visible without scrolling. It
ends in fail conditions that stop a recording rather than suggestions.

**Verified:** `streamlit run app.py --server.headless true` serves HTTP 200, and the gap case renders
9/10 criteria met, 13/13 quotes verified verbatim, with `ps-04b` flagged and its question quoting
the payer's requirement. `./scripts/verify.sh P6-S3 --offline` exits zero at **297 tests**.

---

## 2026-09-09 · The orchestrator routes; code decides what is true

**Decision (P7-S1).** `src/attest/agents/orchestrator.py` composes intake / criteria / packet /
appeal specialists via `agent.as_tool()`. Two properties keep the routing layer from eroding
guarantees the deterministic pipeline already provides.

**Specialists exchange identifiers, never clinical content.** Every tool reads and writes a shared
`Run` and returns a short factual summary — counts, criterion ids, verdicts — never a quote. If
evidence travelled between agents as prose, each hop would be a chance to paraphrase it, and the
paraphrase would reach the packet builder looking exactly like a quote. The verifier cannot catch
that: by then the note it would check against is two agents away.
`test_no_specialist_hands_back_a_clinical_quote` asserts no summary contains a line from the note.

**Verification is inside the criteria step, not a stage a router can choose.** `do_criteria` matches
and enforces in one indivisible call, and there is no tool anywhere that returns unverified
coverage — so no routing decision, however confused, can produce a packet built on evidence the
verifier never saw.

**Parity is the claim, and it is measured twice.** `test_end_to_end_parity` (live) requires the
orchestrated run to produce byte-identical verdicts to the direct pipeline on all three cases; it
**passed**. An offline twin runs the same assertion without a routing model, so a regression is
caught for free, and it also checks both paths against committed ground truth — otherwise parity
could be satisfied by both being wrong in the same way.

**The steps are plain functions; the `@tool` closures are wrappers.** That is what lets the offline
twin exist, and it states the design claim in code: orchestration contributes routing and nothing
else, so the steps must be complete on their own.

**Router on the reasoning tier, specialists on the fast one.** Routing is the one call nothing
downstream can check — a misbehaving specialist still lands in `Run` where code sees it, but a
router that silently omits the criteria specialist just produces a thinner case. It also splits the
work across two daily quotas, which is what makes the live tests runnable at all.

**Found by running it: the orchestrator had no retry.** The first parity attempt completed case one
and died mid-intake on case two with a provider `ServerError`. Every other model call in the project
goes through `with_retry`; this one did not. An orchestrated run is many calls deep and therefore
*more* exposed to the free tier's 503s, not less. Now wrapped.

**Then it hit the real ceiling.** The second attempt exhausted `gemini-3.6-flash`'s 20-request daily
cap — the retry worked correctly, but a daily quota does not clear in 51 seconds. Parity passed on
`ATTEST_MODEL_REASONING=gemini-3.7-flash` / `ATTEST_MODEL_FAST=gemini-3.1-flash-lite`. Recorded
because the result is model-attributable and the next session will need to rotate again.

---

## 2026-09-09 · A specialty is a pack and a note — proven by AST, not by assertion

**Decision (P7-S2).** `vnshealth-medicare-pt` ships: outpatient physical therapy, VNS Health Plans,
Medicare Advantage, hand-authored from a real published policy committed at
`data/policies/raw/vnshealth-medicare-pt-ot-st.txt`.

**The extensibility test parses the AST rather than grepping.** `test_pt_case_runs_with_zero_code_changes`
walks every module under `src/attest`, discards docstrings (prose names specialties deliberately, and
does) and comments (never in the tree), and fails if a specialty word appears in any remaining string
literal or identifier. It passes: **no engine module names a specialty.** A grep would have failed on
the docstrings; a hand-wave would have proven nothing.

**PT was chosen because it is the harder specialty, and this is where that gets tested.** The
original decision record picked TMS for near-binary criteria and named PT's "documented functional
progress" as fuzzier and easier to fake convincingly. `pt-06` is exactly that requirement.

**All-MET ground truth is weakly discriminating, so there is a negative case too.** Every PT criterion
is MET, which a matcher that agreed with everything would satisfy. `test_the_progress_criterion_fails_when_the_measurements_are_removed`
truncates the note to a bare claim of progress with no measurements. The engine returns
**INSUFFICIENT** — and independently flags `pt-07`, `pt-08` and `pt-11` for the same absence, with
`pt-11` correctly reasoning that it cannot rule out an *exclusion* without interim measurements.
INSUFFICIENT rather than UNMET is the right answer: a question for the practice, not an argument
with the payer.

The degraded note is built by truncation, not surgery. The real note quotes current measurements in
three places, so editing one out leaves the others and the test quietly stops meaning what it says.

**Verdicts matched committed ground truth on the first run**, 11/11, with no ground-truth adjustment
— written before the matcher ever saw the note, as the protocol requires.

### Three earlier tests were amended, and that is worth stating plainly

Adding a third pack broke tests that had encoded *corpus facts* as invariants: "there are exactly two
packs", "from two payers", "all carrying the TMS CPT codes", and an ingestion allow-list naming two
files. Those were true in P1-S3 and are not properties of a pack.

The split now made explicit: TMS-specific assertions run over `TMS_PACKS`; assertions true of **any**
pack — traceability, https source, stated appeal-window provenance, contraindication polarity, unique
ids — still run over all of them, so the new pack is held to the same standard rather than exempted.
Recorded rather than done quietly, because editing an earlier gate to make a later step pass is
exactly the move the protocol exists to make visible. **No production code changed.**

---

## 2026-09-09 · The runtime stops at Gate 1, and `requirements.txt` stays one line

**Decision (P7-S3).** `agent_runtime.py` returns the assembled packet and the `content_hash` a
clinician must approve — and writes nothing. A headless deployment is precisely where Gate 1 would
otherwise decay from a product rule into a UI convention.

**Two modes, defaulting to the boring one.** `direct` runs the deterministic pipeline; `orchestrated`
routes the same work through P7-S1's specialists. They are required to agree — that is
`test_end_to_end_parity` — so the switch changes what a caller can observe, never what comes back.
Direct is the default because a deployed service should not spend a routing model's quota, and a 503
inside a routing loop is a failed request rather than a slower one.

**`requirements.txt` deliberately does not pin, against PLAN's wording.** The first P7-S3 attempt
carried a hand-maintained list of `==` pins beside `pyproject.toml`; the commit that reverted it said
at the time that it was a second source of truth. It is now also a *shared* file: P6-S4 deploys the
live, judge-facing Streamlit console from the same `requirements.txt`, and the original pinned list
correctly omitted `streamlit` because the UI is not part of the runtime image. Restoring it would
break the public demo to satisfy a word in the plan. The file is one line — `.` — and if reproducible
image builds are ever needed the mechanism is a generated lockfile, not a second hand-edited list.

**`pythonpath = ["."]` is back in `pyproject.toml`**, exactly as the revert commit anticipated: it was
removed with P7-S3 on the stated grounds that it should return alongside the module that needs it.
AgentCore requires `agent_runtime.py` at the image root, so tests cannot import it otherwise.

**Verified with the DoD's own command.** `python agent_runtime.py`, then
`curl -X POST localhost:8080/invocations -d '{"case":"gap"}'` returns a valid packet: 10 verdicts,
9 claims, gap `ps-04b` matching ground truth, no rejected spans, `approval_required: true`. The PT
case runs through the same handler and returns 11 verdicts — extensibility holds all the way to the
deployment surface. Unknown cases, empty payloads and bad modes come back as `{"error": ...}` rather
than a 500.

`./scripts/verify.sh P7-S3 --offline` exits zero at **340 tests**.

---

## 2026-09-09 · HTTP 200 was the wrong check, and the repo root is now found rather than counted

**What happened.** P6-S4 was marked done on a `curl` that returned 200. The hosted console then
raised `FileNotFoundError` on the synthetic corpus. A 200 proves Streamlit's *shell* booted; the
traceback renders inside a page the server is perfectly happy to serve. The checklist step that
would have caught it — walk `docs/ui-checklist.md` **against the deployed app** — had not been done.

**Root cause.** `requirements.txt` said `.`, a plain install, so `attest` landed in site-packages.
Four modules located repo assets with `Path(__file__).resolve().parents[2]`, which is the repo root
only under an **editable** install — the layout every test and every developer runs. Installed
normally it points at a directory inside the virtualenv that has never contained anything.

Not a crash at import: a wrong path that fails later, at whatever read touches data first. Every
test stayed green because every test runs editable.

**Two more failures were queued behind it.** Building the wheel and looking inside showed 35 files,
all `.py`: the policy packs, the synthetic corpus and the cassettes were *all* absent. Fixing only
the reported error would have surfaced the next one on the next click — a cassette-less deploy
would have demanded an API key, breaking the "judges reproduce it for free" claim outright.

**The fix has two halves, because the assets are two kinds.**

*Package assets* — the YAML packs live inside `src/attest/` and must ship with the package.
`[tool.setuptools.package-data]` now declares them; a rebuilt wheel carries all three.

*Repo assets* — `data/` and `cassettes/` sit outside `src/` and are not installable. `attest.paths`
now **searches** for the root instead of computing it: `$ATTEST_REPO_ROOT`, then upward from
`__file__` (editable install, source checkout), then upward from the working directory (an ordinary
install with the repo checked out around it — the hosted case, where Streamlit runs `app.py` from
`/mount/src/<repo>`). The marker is `data/synthetic` itself rather than something incidental like
`.git`, which a deployment checkout or a Docker image may not have.

**`requirements.txt` is now `-e .`**, which supersedes the P7-S3 entry above. Editable keeps the
deployed layout identical to the tested one. The resolver alone would have sufficed — verified by
installing the wheel into a separate directory and importing it with `src/` off `sys.path`, where
the corpus, the packs and the cassettes all resolved — but a deployment that matches what the tests
exercise is worth more than a fallback that happens to work.

**Four tests hold it**, in `tests/test_p6_s4.py`:

- `test_no_module_computes_the_repo_root_by_counting_parents` walks the AST of every engine module
  and fails on `parents[...]` anywhere but `paths.py`. This is the tripwire for the actual bug.
- `test_repo_root_is_found_from_the_working_directory` reproduces the deployed shape — package
  somewhere else, repo around the process — which is the exact path that broke.
- `test_the_policy_packs_are_declared_as_package_data` and
  `test_requirements_installs_editable_so_repo_assets_resolve` hold the packaging half.

**The wider lesson, and it is the second time this session.** The cookie-jar false alarm and this
one are the same error in opposite directions: trusting a proxy signal (a redirect chain; an HTTP
status) instead of the thing the DoD actually claims. A step whose DoD is "judges can use it" is
not done until someone has used it. `docs/deploy.md` now says the `curl` check is necessary and not
sufficient.

---

## 2026-09-10 · The case is uploaded, and the payer's policy is derived rather than chosen

**Decision (P9-S1).** `app.py` takes its case as an uploaded document. The three-case radio is
gone, `attest.corpus` is no longer imported, and the policy pack comes from
`find_pack(cpt, payer, plan)` applied to what intake extracted.

**Why the picker had to go.** It settled the payer, the pack and the case id *before the model read
a word*. Everything downstream then ran correctly against a case whose identity had been supplied
by the person opening the app — so the screen could demonstrate the renderer and never the product.
The step a practice actually cares about is Attest working out, from a document it has not seen,
whose rules apply; with a picker there is no honest way to show it, and a judge is right to suspect
the three cases are the only three that work.

The routing was never the missing part. `find_pack` has existed since P2-S2 and `check_pa_required`
has always used it. **The UI was bypassing a decision the engine was already making** — `pack` came
straight off the corpus object. Removing the picker did not add a capability; it stopped hiding one.

**No pack means the review stops.** This is the same rule as `PARequirement.UNKNOWN`, one layer up:
we cannot check a note against criteria we do not have, and proceeding would render an empty
coverage table that reads as *nothing to answer*. The intake stays on screen — the run is stopped,
not discarded — and the screen says a policy was not found and that the payer should be asked
directly. `test_an_unlisted_payer_stops_the_review_instead_of_guessing` patches both bindings of
`find_pack`, because `pa_lookup` imported it by name at its own import time and patching only the
loader would produce a screen claiming a policy was found while the router said otherwise.

### Supersedes: "per-case state, keyed by case name" (P6-S3)

That entry required switching cases never to leave the previous case's verdicts on screen. The
property still holds; the key changed. Scratch space is now keyed by a **hash of the note text**,
not a filename, and that is the stronger version: re-uploading the same note continues the same
review, and re-uploading an *edited* note starts a fresh one — which is correct, because the edit
is exactly what invalidates the verdicts already rendered. A filename key would silently show
yesterday's coverage for a note that had been rewritten under the same name.

### Downloading a sample is not preloading one

P6-S4 put this console on a public URL specifically so judges could use it. An upload-only screen
is useless to someone with no clinical note on their machine, and there is no lawful place for
them to get one — so the landing screen offers the synthetic corpus as **downloads**.

The distinction is not a dodge. Nothing enters the pipeline until a human uploads it, which is the
entire content of "nothing is preloaded"; the app hands over a file and forgets it.
`test_the_landing_screen_hands_a_stranger_a_note_to_try` keeps the affordance from being tidied
away by a later session reading the rule too literally.

### The uploads must be byte-identical, and that is load-bearing

Cassette keys hash the note text (`cache._key`). Uploading the committed `clean.md` therefore hits
the cassette the radio used to, and the demo still costs nothing. Re-typing the note, round-tripping
it through a PDF, or changing one character makes it a live call against a 20-request daily cap.

This is the encoding landmine already recorded here, arriving through a new door: `read_upload`
decodes `utf-8` explicitly rather than trusting the platform default, because a note decoded two
ways on two machines would not merely look wrong — it would shift every character offset the
verifier reports, so evidence spans would point at the wrong text *while still appearing verified*.

### An earlier gate's tests were rewritten, and that is worth stating plainly

`tests/test_p6_s3.py` drove the app by writing the radio's key into session state. Those helpers now
upload the corpus files through `AppTest`'s `FileUploader.set_value()`. Every assertion is unchanged
in substance — the gates are still asserted inert until a clinician is named, no document still
exists before approval, every quote still carries the verifier's mark — but `test_the_landing_screen_names_the_payer_and_the_policy`
genuinely could not survive: the screen cannot name a payer before a note has been read, so it now
asserts the same thing after intake and is named for what it checks.

Same shape as the three P1-S3 tests amended in P7-S2. Editing an earlier gate to make a later step
pass is the move the protocol exists to make visible, so it is recorded rather than done quietly.
**No engine code changed** — the diff is `app.py`, two test modules, one marker, and the docs.

**What would change our mind.** If a demo ever needs to open on a populated case — a recorded video
that cannot afford an upload interaction, say — the answer is a query parameter that *pre-fills the
uploader* from the corpus, leaving the pipeline entry point unchanged. Reinstating a picker that
sets the pack directly would put the bypass back.

## 2026-09-10 · Constructing an agent is not asking a model, and P7-S1 forgot it

**Decision (P9-S8).** The two composition tests in `tests/test_p7_s1.py` inject a placeholder
credential before calling `build_orchestrator`. `./scripts/verify.sh ALL --offline` now exits zero
on a keyless clone — **357 passed, 5 deselected** — where it had been reporting `2 failed,
355 passed`.

**This was not a new problem and did not need a new answer.** `test_p2_s3.py` hit it at P2-S3,
against `build_intake_agent`, and wrote the reasoning into its own docstring: `build_model` refuses
to construct without a key *deliberately*, so a missing key surfaces as a setup problem rather than
as an auth error deep inside an agent run — but constructing an `Agent` makes no request, so any
string will do. That test even records the cost of getting it wrong: "made a keyless clone fail 1
of 268 and left the 'judges can clone and run it' claim untrue."

P7-S1 built five agents the same way — four specialists plus the router — and never applied the
pattern. The two properties under test are settled before any provider is touched: which
specialists exist, what they are named, and what their descriptions say.

**What was rejected, and why.**

*A `needs_key` skip.* Available, one line, and wrong. It would leave `agent.as_tool()` composition
— the thing P7-S1 exists to demonstrate, and the thing judging criterion 1 scores — unverified in
the only environment that matters. `.github/workflows/gate.yml` is deliberately "the judge's
scenario, not ours"; a skip would make the gate green by agreeing not to look.

*Threading a model factory through `build_orchestrator` and the four `_*_agent` helpers.* Drafted
first, and discarded on reading `test_p2_s3.py`. It changes production code to serve a test, adds a
parameter to five functions, and is a second solution to a problem this repository had already
solved. The smaller diff is also the more honest one: the test says "constructing this needs no
model", which is exactly true.

**The failure was in reading CI, not in writing it.** The workflow caught this on every push and
reported `failure` on at least five consecutive runs, including the P9-S1 merge to `main`. Nobody
opened it. Two sentences in `README.md` — "exits zero, 357 tests, ~13s, no API key" and "the same
command runs in CI on every push … the judge's scenario rather than ours" — were false for days on
a public repository that invites judges to clone and run exactly that command, against rules that
require a project which "installs and runs consistently".

The count in that sentence turned out to be right: the command selects 357 tests and now passes all
357, so no number needed correcting. Only "exits zero" was false.

**What would change our mind.** If a future specialist ever needs a *live* model at construction —
to negotiate a context window, say — the placeholder stops being honest and the model factory comes
back. Nothing in Strands' `Agent.__init__` does that today.

### The corollary, which is now P9-S2

The same session found `verify.sh ALL --offline` reporting `15 failed, 342 passed` on a Windows
checkout. Normalising *only* the corpus line endings to LF took it to `2 failed, 355 passed` —
identical to CI, which is what isolated these two failures in the first place. The other thirteen
are `.gitattributes` pinning `*.sh` and nothing else, so `read_upload` decodes CRLF where
`Path.read_text` recorded the cassettes against LF. **The P6-S3 and P9-S1 gates do not pass on a
Windows clone.** That is P9-S2 and it is not fixed here; this entry records only that the two
problems were separate, and were separated by experiment rather than by assumption.

## 2026-09-10 · A newline is an encoding, and an uploader is an invitation

**Decision (P9-S2).** `.gitattributes` pins `*.md` to `eol=lf`, `read_upload` normalises newlines
after decoding, and every engine call in `app.py` runs inside `guarded`, which renders a failure
instead of raising it into the page.

### The newline half

`docs/setup.md` and this log already record that every file read must name its encoding, because a
note decoded two ways on two machines shifts every character offset the verifier reports —
"evidence spans would point at the wrong text *while still appearing verified*". That was fixed.
This is the same bug through a different door, and it was invisible for the same reason: it does
not fail, it *diverges*.

Every reader in this codebase goes through `Path.read_text`, whose universal-newline handling
collapses `\r\n` to `\n` before anything sees it. That is the text the cassettes were recorded
against, the text the ground truth describes, and the text every offset in `tests/` refers to.
`read_upload` is the single exception: an upload is raw bytes, and `.decode("utf-8")` translates
nothing. With `.gitattributes` pinning only `*.sh`, a Markdown note checked out on Windows reached
the pipeline as **2424 characters where the recorded one is 2371** — a different string, a
different `cache._key`, a cassette miss, a live call, and on a keyless clone a traceback.

**The shape of the failure is what makes it worth this much prose.** `verify.sh ALL --offline`
failed 13 tests on Windows and passed on Linux. CI is Linux, both prior sessions worked on Linux or
macOS, and the whole of `tests/test_p9_s1.py` — the gate for the step that *introduced* the upload
path — was among the 13. A gate that passes on the machine that wrote it and fails on the other one
is worse than a gate that fails everywhere, because it gets recorded as DONE.

Fixed at both ends deliberately. The attribute fixes the checkout; `read_upload` fixes the upload.
Only the second survives the case nothing in git can reach: a judge who downloads a synthetic note,
opens it in Notepad, saves it, and uploads CRLF from a file that was never in the repository.

**Not fixed by normalising the corpus once and committing it.** The index was already LF — the
smudge happens on checkout, every checkout, so a one-time normalisation would have looked like a
fix on the machine that ran it and changed nothing for anyone else.

### The uploader half

P9-S1 replaced a three-case radio with a file uploader and, in doing so, quietly changed what the
screen promises. A radio offers three things that work. An uploader invites anything — and the
first thing a judge will upload is a note of their own, which this deploy has no key to answer.
`app.py` caught `MissingFactError` and nothing else, so that arrived as a Python traceback: the
first entry under *Fail conditions* in `docs/ui-checklist.md`.

`guarded` distinguishes exactly one case, and only where it can be sure of it. When a *model-backed*
stage fails and no credential is configured, the call can only have been reached by missing a
cassette, so the screen says the note is not one of the recorded ones, explains why that is by
design rather than broken, and expands the sample downloads underneath — saying what went wrong
without handing over something that works is half an answer. Every other failure is named as what
it is. **The screen never claims a real failure was expected**, which is the line this repo has
held everywhere else: `UNKNOWN` is not "not required", and a placeholder deadline says it is a
placeholder.

`ApprovalRequired` travels through the same path on purpose. When `emit_submission_artifact`
refuses a packet whose hash moved after sign-off, that is the gate working, and it is now rendered
rather than raised — **still stopping**, just legibly. No guard swallows a failure and continues;
every branch ends in `st.stop()`.

### What the gate proves, and how it was checked

`tests/test_p9_s2.py` drives the real screen. The strongest assertion needs no comparison: scratch
space is keyed by a hash of the note text, so uploading the CRLF copy into a session that already
read the LF copy **continues that review** instead of offering *Run intake* again. Two strings that
hash alike are one string.

The normalisation was then temporarily reverted and the suite re-run, to confirm the gate actually
fails without it. It does. A test that has never been seen to fail is a test that has not been
shown to test anything.

**What would change our mind.** If Attest ever accepts a format where `\r` is data rather than a
line ending — a fixed-width payer export, say — `read_upload` stops being the right place and the
normalisation moves to the Markdown path only.

## 2026-09-10 · A verdict is not a sentence until you know which way the criterion points

**Decision (P9-S3).** The criterion label carries the id, the category and what the verdict *means*
— `✅ hho-05 · Contraindication — Ruled out`. The payer's wording moves inside the expander, still
verbatim. A criterion with `polarity: absent` gets its own wording table and a line saying how it
is satisfied.

### The tick meant the opposite of what a reader would take it for

`Polarity` has existed since P1-S1, and its docstring is exactly right: "Collapsing both senses
into one would make every contraindication read as unmet, so the distinction is explicit." The
engine respects it — `match.py` tells the model a contraindication is satisfied by absence, and the
verdicts are correct. **The screen then threw the distinction away**, rendering from the verdict
alone:

    ✅ hho-05 — Seizure disorder or any history of seizure with increased risk of future seizure

To anyone who is not a clinician that says the patient *has* a seizure disorder. It says the
opposite. Four of Highmark's ten criteria are `absent`, and three of PacificSource's, so the
flagship demo case had four lines stating the inverse of the finding on the screen
`Attest-PRODUCT.md` §9 calls "the product's core".

`INSUFFICIENT` is the pair worth reading twice. On an absent criterion it does not mean the finding
might be present — it means nobody wrote it down, and `match.py` already says "an undocumented
contraindication is unknown, not ruled out". **"Not ruled out"** is that sentence in two words, and
it is deliberately not reassuring.

### The label was the whole policy text

Up to 524 characters (`hho-03`), wrapping to four lines, ten stacked in a column, all collapsed —
so the core screen showed **no evidence at rest** and cost ten clicks to reveal any. The id and the
category, which are the two things a reviewer scans a list of ten for, were hidden inside.

The wording moves in rather than being summarised. Quoting the payer verbatim is the product's
argument, not decoration: the appeal cites this language back at them. A label that paraphrased the
policy would be a paraphrase on the one screen built to refuse paraphrase.

### The category is read as English, and nowhere else

`humanise` turns `treatment_resistance` into `Treatment resistance` in the label only. Categories
stay raw wherever code groups by them. A label is doing a different job from a key.

### What the gate proves, and how it was checked

`tests/test_p9_s3.py` asserts over *every* criterion in the pack rather than a chosen few, because
the fault was a rendering rule that happened to be wrong for one polarity — the kind that hides
until a pack nobody was looking at ships. `test_the_packs_still_contain_the_case_this_gate_exists_for`
guards the fixture itself: if no pack has an absent criterion, the polarity tests assert nothing
and would go on passing.

Both behaviours were then temporarily reverted and the suite re-run. Polarity-blind wording fails
`test_a_contraindication_that_was_ruled_out_is_not_labelled_met`; the policy text back in the label
fails `test_no_criterion_label_is_longer_than_a_scannable_line`. Neither test passes vacuously.

**What would change our mind.** If a pack ever ships a criterion whose polarity is genuinely
ambiguous — "document either A or the absence of B" — the two-value table stops being enough, and
the honest answer is a per-criterion display sentence in the pack rather than a third enum value
the model has to infer.

### Not fixed here

The evidence quote is still the faintest thing in the expander, and the note itself is still a
separate collapsed block rather than the place the spans are shown. That is P9-S6, and it is the
one recommendation in `docs/uiux-review.md` worth building even if nothing else on the list is.
