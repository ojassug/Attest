# Attest — Phase Plan & Definitions of Done

> **This file is the contract.** It is the authoritative list of phases, steps, and what "done" means for each.
> It changes rarely — only to refine a Definition of Done, never to record progress.
> Progress lives in `STATUS.md`. Reasoning lives in `DECISIONS.md`.

---

## How to use this file

**If you are a Claude session starting cold, read in this order:**

1. `git pull`
2. `STATUS.md` — what is done, what is in flight, what the last session was mid-way through
3. `DECISIONS.md` — why things are the way they are
4. This file — the Definition of Done for the step you are about to start

Then run the gate for the last step marked `DONE`:

```bash
./scripts/verify.sh <LAST_DONE_STEP_ID>
```

**If it fails, the previous session's claim was false.** Correct `STATUS.md` first, before starting anything new. This check is the entire point of the protocol — it means you verify rather than trust.

---

## The rules

### 1. A step is done when its gate exits zero

Not when it looks right. Not when it seems finished.

```bash
./scripts/verify.sh P3-S2   # exit 0 == done, anything else == not done
```

Each step maps to a pytest marker. The gate runs that step's tests **plus every prior step's tests**, so a later step cannot silently break an earlier one.

### 1b. What the test markers mean

- **`live`** — genuinely cannot be replayed from a cassette. Provider connectivity and tool
  invocation only; exactly **three** tests carry it, and `--offline` deselects them.
- **`needs_model`** — needs a model *result*, which a cassette can serve. Runs offline.
- **`needs_key`** — needs a credential to be present, not a request to be made.

`--offline` is therefore a valid gate pass. Several DoD items below were written before this
distinction existed and said `live` where the code uses `needs_model`; they were corrected on
2026-09-09 to match the code. P7's are left alone - those tests do not exist yet, and guessing
their marker would be inventing contract rather than recording it.

### 2. Every DoD item must be machine-checkable

Exactly three permitted forms:

- **File** — a file exists at path X with property Y
- **Command** — a command runs and produces output Y / exits zero
- **Test** — a named test passes

Anything phrased as "works correctly", "is implemented", or "handles X properly" is not a DoD item. Rewrite it or delete it.

### 3. Leave the repo committed, always

Sessions end abruptly when the usage limit hits. Uncommitted work is invisible to the other machine and is therefore lost. Commit broken work rather than losing it — `STATUS.md` is where you say it is broken.

### 4. Steps are small on purpose

Roughly 30–90 minutes each, so a session dying mid-step costs little.

### 5. Record decisions as you make them

If you chose something non-obvious and the reason lives only in the conversation, it is gone the moment the session ends. Append it to `DECISIONS.md` in the same commit.

---

## Session protocol

**Starting:**

```bash
git pull
# read STATUS.md, DECISIONS.md, this file
./scripts/verify.sh <LAST_DONE_STEP_ID>     # confirm the baseline is real
# mark your step IN_PROGRESS in STATUS.md with your name
git commit -am "start <STEP_ID>"            # commit the marker IMMEDIATELY
git push
```

**Ending (including an abrupt limit-hit):**

```bash
git add -A
git commit -m "wip <STEP_ID>: <what actually landed>"
# update STATUS.md: status, gate SHA if it passed, and HANDOFF NOTES
git push
```

---

## Milestone markers

- `▲` — required for a viable submission
- `— SUBMITTABLE —` — the line after which everything is upside

**Hard deadlines:**

| What | When |
|---|---|
| AWS $50 credit request form | **Sep 11, 2026, 12:00pm PT** |
| Devpost submission closes | **Sep 14, 2026, 5:00pm PT** |

---

# P0 — Foundation & protocol

## P0-S1 — Model provider access

Human-driven. A free Gemini key from https://aistudio.google.com/apikey — no credit card, no
account provisioning. Bedrock is deferred to P7; see DECISIONS.md.

**DoD**
- [ ] **File** `.env` exists at the repo root containing a working `GOOGLE_API_KEY`, and is
      gitignored (never committed)
- [ ] **Command** `.venv/bin/python -c "from attest.llm import have_credentials; assert have_credentials()"` exits zero
- [ ] **File** `docs/setup.md` records the provider, both tier model ids, and how to obtain a key
- [ ] **File** `DECISIONS.md` names the provider and the reason

## P0-S2 — Protocol documents

**DoD**
- [ ] **File** `PLAN.md` exists with a step entry for every step
- [ ] **File** `STATUS.md` exists with one table row per step in `PLAN.md`
- [ ] **File** `DECISIONS.md` exists with the decisions carried over from planning

## P0-S3 — Repo skeleton, tooling, and the gate runner

**DoD**
- [ ] **File** `pyproject.toml` declares `strands-agents`, `strands-agents-tools`, `bedrock-agentcore`, `pydantic`, `pytest`, `streamlit`, `pyyaml`
- [ ] **File** `LICENSE` exists and is Apache 2.0 (added in PR #1; the rules accept MIT or Apache)
- [ ] **File** `src/attest/__init__.py` exists
- [ ] **File** `scripts/verify.sh` exists and is executable
- [ ] **Command** `pip install -e .` exits zero
- [ ] **Command** `./scripts/verify.sh P0-S3` exits zero
- [ ] **Test** `tests/test_p0_s3.py::test_status_covers_all_plan_steps` — parses `PLAN.md` and `STATUS.md` and asserts every step id in the plan has exactly one row in the status board, and no orphan rows exist
- [ ] **Test** `tests/test_p0_s3.py::test_every_step_has_a_marker` — asserts every step id is a registered pytest marker

## P0-S4 — Model provider smoke test

**DoD**
- [ ] **File** `src/attest/llm.py` exposes `build_model(tier)` returning a configured Strands model
- [ ] **Test** `tests/test_p0_s4.py::test_model_tool_roundtrip` (marker `live`) — a trivial `@tool`
      agent returns a non-empty response and the tool was actually invoked
- [ ] **Test** `tests/test_p0_s4.py::test_structured_output_roundtrip` (marker `live`) — a Pydantic
      model comes back populated, since every later phase depends on structured output working
- [ ] **Command** `./scripts/verify.sh P0` exits zero

---

# P1 — Domain data layer (no LLM calls in this phase)

## P1-S1 — Pydantic domain models

**DoD**
- [ ] **File** `src/attest/models.py` defines: `InsuranceInfo`, `ServiceRequest`, `Case`, `Criterion`, `Verdict` (enum: `MET` / `UNMET` / `INSUFFICIENT`), `EvidenceSpan`, `CriterionVerdict`, `CriteriaCoverage`, `GapItem`, `Packet`, `Denial`, `ContestedCriterion`, `Appeal`, `ApprovalRecord`
- [ ] **Test** `test_p1_s1.py::test_models_roundtrip` — every model serialises to JSON and back unchanged
- [ ] **Test** `test_p1_s1.py::test_evidence_span_rejects_empty_quote` — an `EvidenceSpan` with an empty or whitespace-only quote raises `ValidationError`
- [ ] **Test** `test_p1_s1.py::test_verdict_is_closed_enum` — an unknown verdict string raises `ValidationError`

## P1-S2 — Policy pack format and loader

**DoD**
- [ ] **File** `src/attest/policies/schema.py` defines `PolicyPack` with: `payer`, `plan`, `service`, `cpt_codes`, `source_url`, `source_title`, `retrieved_date`, `pa_required`, `appeal_window_days`, `criteria[]`
- [ ] **File** `src/attest/policies/loader.py` exposes `load_pack(path)` and `list_packs()`
- [ ] **Test** `test_p1_s2.py::test_pack_requires_source_url` — a pack missing `source_url` fails to load
- [ ] **Test** `test_p1_s2.py::test_pack_rejects_duplicate_criterion_ids`
- [ ] **Test** `test_p1_s2.py::test_criterion_requires_source_section` — every criterion must name the policy section it came from

## P1-S3 — Two TMS policy packs from real public payer policies

**DoD**
- [ ] **File** two packs under `src/attest/policies/packs/` derived from real, publicly published payer TMS policies
- [ ] **Test** `test_p1_s3.py::test_both_packs_load`
- [ ] **Test** `test_p1_s3.py::test_packs_have_minimum_criteria` — each pack has ≥ 8 criteria
- [ ] **Test** `test_p1_s3.py::test_every_criterion_traceable` — every criterion has non-empty `text`, `source_section`, and `category`
- [ ] **Test** `test_p1_s3.py::test_source_urls_are_https`

## P1-S4 — Synthetic corpus and ground truth

The ground-truth files are what make every later phase's DoD objective. Without them "the criteria matcher works" is unfalsifiable.

**DoD**
- [ ] **File** `data/synthetic/notes/clean.md`, `gap.md`, `denial.md`
- [ ] **File** `data/synthetic/denials/denial_001.md`
- [ ] **File** `data/synthetic/expected/{clean,gap,denial}.json` — per case: expected service, CPT, payer, PA-required determination, and expected verdict for every criterion id
- [ ] **Test** `test_p1_s4.py::test_all_notes_carry_synthetic_banner` — every note begins with a `SYNTHETIC — NOT REAL PATIENT DATA` banner
- [ ] **Test** `test_p1_s4.py::test_expected_criterion_ids_exist_in_pack` — every criterion id referenced in ground truth exists in the named pack
- [ ] **Test** `test_p1_s4.py::test_gap_case_has_at_least_one_unmet` — the gap case's ground truth actually contains a gap
- [ ] **Command** `./scripts/verify.sh P1` exits zero

---

# P2 — Intake & PA determination

## P2-S1 — Note → structured Case

**DoD**
- [ ] **File** `src/attest/agents/intake.py` exposes `extract_case(note_text, insurance) -> Case` using `structured_output_model`
- [ ] **Test** `test_p2_s1.py::test_extraction_matches_ground_truth` (marker `needs_key`) — all three synthetic notes produce a `Case` whose service, CPT, payer, and primary diagnosis match `expected/*.json`

## P2-S2 — PA-required determination (deterministic, no LLM)

**DoD**
- [ ] **File** `src/attest/tools/pa_lookup.py` exposes `check_pa_required(cpt, payer, plan) -> PADetermination` with `.requirement`, `.policy_id`, `.citation`, `.rationale`
      *(refined from `.required`: a boolean would collapse `UNKNOWN` into `False`, which is the
      exact bug this step exists to prevent — hence a three-state enum)*
- [ ] **Test** `test_p2_s2.py::test_determination_matches_ground_truth` — correct for all three cases
- [ ] **Test** `test_p2_s2.py::test_unmapped_cpt_returns_unknown_not_false` — an unmapped CPT returns `UNKNOWN`, never `required=False`. Absence of a policy is not evidence that no PA is needed, and the agent must never imply otherwise.

## P2-S3 — Intake agent wiring

**DoD**
- [ ] **File** `src/attest/agents/intake_agent.py` builds a Strands `Agent` with `check_pa_required` registered as a `@tool`
- [ ] **Test** `test_p2_s3.py::test_agent_invokes_pa_lookup_tool` (marker `live`) — the tool is actually called during a run
- [ ] **Command** `./scripts/verify.sh P2` exits zero

---

# P3 ▲ — Criteria engine & evidence matching (the core)

This phase is the product. Section 9 of `Attest-PRODUCT.md` names "criteria matching looks shallow" as the top risk — this is where that is won or lost.

## P3-S1 — Policy ingestion → draft criteria

Automated decomposition, whose output is human-reviewed into a pack. The shipped packs stay human-reviewed; this demonstrates the path without putting unreviewed model output into a submission.

**DoD**
- [ ] **File** `src/attest/criteria/ingest.py` exposes `ingest_policy(text) -> list[Criterion]`
- [ ] **Test** `test_p3_s1.py::test_ingest_recovers_known_criteria` (marker `needs_model`) — run against the source text of an existing pack, recovers ≥ 70% of its criterion topics
- [ ] **Test** `test_p3_s1.py::test_ingest_output_is_not_auto_shipped` — asserts no file under `policies/packs/` is written by `ingest_policy`

## P3-S2 — Per-criterion evidence matching

**DoD**
- [ ] **File** `src/attest/criteria/match.py` exposes `match_criterion(criterion, note) -> CriterionVerdict` returning verdict, `spans[]`, and reasoning, via `structured_output_model`
- [ ] **File** `src/attest/criteria/match.py` exposes `match_all(pack, note) -> CriteriaCoverage`
- [ ] **Test** `test_p3_s2.py::test_clean_case_all_criteria_met` (marker `needs_model`)
- [ ] **Test** `test_p3_s2.py::test_gap_case_flags_the_expected_criterion` (marker `needs_model`) — the criterion id flagged matches ground truth exactly. Flagging *a* gap is not enough; it must be the right one.

## P3-S3 — The evidence-span verifier (deterministic, no LLM)

This is what makes "evidence-traceable by design" a guarantee rather than a prompt instruction.

**DoD**
- [ ] **File** `src/attest/verifier.py` exposes `verify_span(span, note) -> SpanVerification` (verbatim containment under whitespace normalisation, returning exact character offsets) and `verify_coverage(coverage, note) -> VerificationReport`
- [ ] **Test** `test_p3_s3.py::test_exact_quote_verifies`
- [ ] **Test** `test_p3_s3.py::test_paraphrase_is_rejected` — a semantically identical paraphrase fails. Paraphrase is precisely what we are defending against.
- [ ] **Test** `test_p3_s3.py::test_whitespace_and_newline_variants_verify`
- [ ] **Test** `test_p3_s3.py::test_fabricated_quote_is_rejected`
- [ ] **Test** `test_p3_s3.py::test_returned_offsets_are_correct` — slicing the note at the returned offsets reproduces the quote

## P3-S4 — Verifier enforcement in the pipeline

**DoD**
- [ ] **Test** `test_p3_s4.py::test_unverifiable_span_downgrades_criterion` — injecting a fabricated span downgrades that criterion to `INSUFFICIENT`; it is never silently dropped
- [ ] **Test** `test_p3_s4.py::test_rejection_is_logged` — the rejection appears in the audit log with the offending quote
- [ ] **Test** `test_p3_s4.py::test_no_unverified_span_survives` (marker `needs_model`) — across all three cases, 100% of spans in the final coverage verify verbatim

## P3-S5 — Gap list

**DoD**
- [ ] **File** `src/attest/criteria/gaps.py` exposes `build_gap_list(coverage) -> list[GapItem]`, each carrying `criterion_id`, what is missing, and a question addressed to the practice
- [ ] **Test** `test_p3_s5.py::test_gap_case_produces_expected_gap` (marker `needs_model`) — criterion id matches ground truth
- [ ] **Test** `test_p3_s5.py::test_every_gap_asks_a_question` — each gap's `question` field is non-empty and ends in `?`
- [ ] **Command** `./scripts/verify.sh P3` exits zero

---

# P4 ▲ — Packet assembly & Gate 1

## P4-S1 — Medical-necessity justification from verified evidence only

**DoD**
- [ ] **File** `src/attest/packet/justification.py` exposes `build_justification(coverage, case) -> Justification` with `claims[]`, each claim carrying `supporting_span_ids`
- [ ] **Test** `test_p4_s1.py::test_every_claim_has_supporting_spans` — no claim has an empty `supporting_span_ids`
- [ ] **Test** `test_p4_s1.py::test_all_referenced_spans_are_verified` — every referenced span id is in the verified set from P3-S3

## P4-S2 — Gate 1: approval before submission

**DoD**
- [ ] **File** `src/attest/gates.py` registers a `BeforeToolCallEvent` hook that calls `interrupt()` before `emit_submission_artifact`
- [ ] **Test** `test_p4_s2.py::test_artifact_blocked_without_approval` — no file is written and an interrupt is raised
- [ ] **Test** `test_p4_s2.py::test_artifact_written_after_approval`
- [ ] **Test** `test_p4_s2.py::test_approval_record_persisted` — `ApprovalRecord` carries approver, ISO timestamp, and a content hash
- [ ] **Test** `test_p4_s2.py::test_content_hash_matches_emitted_artifact` — proves what was approved is what was emitted

## P4-S3 — Submission artifact

**DoD**
- [ ] **File** `src/attest/packet/emit.py` exposes `emit_submission_artifact(packet) -> Path` producing Markdown and PDF
- [ ] **Test** `test_p4_s3.py::test_artifact_contains_every_criterion`
- [ ] **Test** `test_p4_s3.py::test_artifact_contains_every_verified_quote`
- [ ] **Test** `test_p4_s3.py::test_artifact_embeds_approval_hash`
- [ ] **Command** `./scripts/verify.sh P4` exits zero

---

# P5 ▲ — Denial → appeal loop & Gate 2

## P5-S1 — Denial parsing

**DoD**
- [ ] **File** `src/attest/appeal/parse.py` exposes `parse_denial(text, pack) -> Denial` with `contested[]` mapped to real criterion ids
- [ ] **Test** `test_p5_s1.py::test_contested_ids_match_ground_truth` (marker `needs_model`)
- [ ] **Test** `test_p5_s1.py::test_unmappable_reason_is_surfaced_not_dropped` — a denial reason that maps to no criterion appears in `Denial.unmapped_reasons`

## P5-S2 — Rebuttal drafting

**DoD**
- [ ] **File** `src/attest/appeal/draft.py` exposes `draft_rebuttal(contested, coverage, pack) -> Rebuttal`
- [ ] **Test** `test_p5_s2.py::test_rebuttal_cites_real_policy_section` (marker `needs_model`) — every citation resolves to a `source_section` present in the pack
- [ ] **Test** `test_p5_s2.py::test_rebuttal_cites_verified_spans_only`
- [ ] **Test** `test_p5_s2.py::test_every_contested_criterion_is_addressed` — no contested criterion is left unrebutted

## P5-S3 — Gate 2: approval before appeal

**DoD**
- [ ] **Test** `test_p5_s3.py::test_appeal_blocked_without_approval`
- [ ] **Test** `test_p5_s3.py::test_appeal_written_after_approval`
- [ ] **Test** `test_p5_s3.py::test_appeal_approval_record_persisted`

## P5-S4 — Appeal artifact and deadline

**DoD**
- [ ] **File** `src/attest/appeal/emit.py` exposes `emit_appeal_artifact(appeal) -> Path`
- [ ] **Test** `test_p5_s4.py::test_appeal_deadline_computed` — denial date + the pack's `appeal_window_days`
- [ ] **Test** `test_p5_s4.py::test_appeal_contains_rebuttal_per_contested_criterion`
- [ ] **Command** `./scripts/verify.sh P5` exits zero

---

# P6 ▲ — Case tracking & UI

## P6-S1 — Case store

Strands session managers are not thread-safe and take no distributed lock — one case, one session id, no sharing.

**DoD**
- [ ] **File** `src/attest/store.py` exposes `save_case(case)` and `load_case(case_id)` backed by `SnapshotSessionManager`
- [ ] **Test** `test_p6_s1.py::test_case_survives_process_restart` — write in one subprocess, read in another
- [ ] **Test** `test_p6_s1.py::test_one_session_id_per_case`

## P6-S2 — Precedent reuse

**DoD**
- [ ] **File** `src/attest/appeal/precedent.py` exposes `find_precedents(criterion_id) -> list[Appeal]` over previously approved appeals
- [ ] **Test** `test_p6_s2.py::test_seeded_precedent_is_retrieved`
- [ ] **Test** `test_p6_s2.py::test_unapproved_appeals_are_never_returned` — only human-approved appeals become precedent

## P6-S3 — Streamlit UI

**DoD**
- [ ] **File** `app.py` renders: case list, criteria-coverage table with evidence quotes, gap list, both approval gates, artifact download
- [ ] **Command** `streamlit run app.py --server.headless true` starts and `curl -sf localhost:8501` returns HTTP 200
- [ ] **Test** `test_p6_s3.py::test_app_imports_without_error`
- [ ] **File** `docs/ui-checklist.md` — the manual walkthrough a human runs before the video

## P6-S4 — Public deploy for judges

**DoD**
- [ ] **Command** `curl -sf <PUBLIC_URL>` returns HTTP 200 from a machine with no local state
- [ ] **File** `README.md` and `STATUS.md` both record the public URL
- [ ] **Command** `./scripts/verify.sh P6` exits zero

---

## — SUBMITTABLE FROM HERE —

Everything above is a complete, coherent, submittable product. Do not start P7 until `./scripts/verify.sh P6` is green.

---

# P7 — Multi-agent depth & AgentCore

## P7-S1 — Orchestrator with specialist subagents

Judging criterion 1 scores *how thoroughly and skilfully the project uses Strands*. This step is that score.

**DoD**
- [ ] **File** `src/attest/agents/orchestrator.py` composes intake / criteria / packet / appeal specialists via `agent.as_tool(name=..., description=...)`
- [ ] **Test** `test_p7_s1.py::test_orchestrator_routes_to_each_specialist` (marker `live`)
- [ ] **Test** `test_p7_s1.py::test_end_to_end_parity` (marker `live`) — the orchestrator produces the same criterion verdicts as the direct pipeline on all three cases

## P7-S2 — Physical-therapy extensibility pack

**DoD**
- [ ] **File** one PT policy pack + one synthetic PT case + ground truth
- [ ] **Test** `test_p7_s2.py::test_pt_case_runs_with_zero_code_changes` — asserts the PT run touches no specialty-specific branch; the pack is data
- [ ] **Test** `test_p7_s2.py::test_pt_verdicts_match_ground_truth` (marker `live`)

## P7-S3 — AgentCore entrypoint

**DoD**
- [ ] **File** `agent_runtime.py` uses `BedrockAgentCoreApp` with an `@app.entrypoint` handler
- [ ] **File** `requirements.txt` pins the runtime dependencies
- [ ] **Command** `python agent_runtime.py` then `curl -X POST localhost:8080/invocations -H 'Content-Type: application/json' -d '{"prompt":"..."}'` returns a valid packet payload

## P7-S4 — Deploy to AgentCore Runtime

**DoD**
- [ ] **Command** `agentcore configure` and `agentcore launch` complete without error
- [ ] **Command** `agentcore invoke` against the deployed runtime returns a correct packet for a synthetic case
- [ ] **File** `docs/aws-setup.md` records the runtime ARN and the IAM role used
- [ ] **Command** `./scripts/verify.sh P7` exits zero

---

# P8 — Submission deliverables

These are scored as heavily as the code. Two of the five judging criteria — Presentation and Potential Impact — live entirely in this phase.

## P8-S1 — README

**DoD**
- [ ] **File** `README.md` covers: what it is, who it is for, setup, how to run the demo, the public link, the synthetic-data stance, the human-approval gates
- [ ] **Command** clone into an empty directory, follow the README verbatim, `python -m attest.demo --case clean` succeeds. The rules require the project to install and run consistently for judges.

## P8-S2 — Architecture diagram

**DoD**
- [ ] **File** `docs/architecture.png` (or `.svg`) showing the agent graph, the two gates, the verifier, and the AWS deployment surface
- [ ] **File** `README.md` embeds it

## P8-S3 — Impact metrics

**DoD**
- [ ] **File** `docs/metrics.md` reporting, across all demo cases: criteria-coverage rate, span-verification rate, gaps correctly identified, and measured agent wall-clock vs. the 20–30 minute manual baseline from `Attest-PRODUCT.md` §5
- [ ] **Command** `python -m attest.metrics` regenerates the numbers in that file

## P8-S4 — Demo video

**DoD**
- [ ] **File** `docs/video-script.md`
- [ ] Video ≤ 5:00, public on YouTube or Vimeo, opening with problem / who it is for / why it matters, then one synthetic case end to end: note → packet → Gate 1 → denial → appeal → Gate 2
- [ ] **File** `STATUS.md` records the public video URL

## P8-S5 — Devpost submission

**DoD**
- [ ] **File** `docs/submission-checklist.md` with every `Attest-PRODUCT.md` §1.4 requirement ticked: text description, public repo, README, architecture diagram, video, AWS Builder ID, Apache 2.0 licence visible in the repo About section, optional live demo link
- [ ] Submitted on Devpost before **Sep 14, 2026, 5:00pm PT**
- [ ] **File** `docs/setup.md` records the AWS Builder ID (a required Devpost submission field)
- [ ] AWS $50 credit requested (form closes **Sep 11, 12:00pm PT** — request it even if Bedrock
      is never used, since P7 deployment would consume it)
- [ ] Optional: builder.aws blog post, title containing "Agents for Humans" (+0.2 each, max +0.6)
