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
