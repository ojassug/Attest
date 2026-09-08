# Setup

## Prerequisites

- **Python 3.12.** The system default on this machine is 3.14, which is too new for the Strands
  dependency tree. Use 3.12 explicitly.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

`scripts/verify.sh` finds `.venv/bin/pytest` on its own — you do not need to activate anything.

## Model provider

**Google AI Studio (Gemini).** Free, no credit card, no account provisioning.

1. Get a key at <https://aistudio.google.com/apikey>
2. `cp .env.example .env`
3. Paste the key after `GOOGLE_API_KEY=`

`.env` is gitignored. Never commit it.

Verify:

```bash
.venv/bin/python -c "from attest.llm import have_credentials; assert have_credentials()"
./scripts/verify.sh P0
```

### Models in use

| Tier | Model | Used for |
|---|---|---|
| `fast` | `gemini-3.5-flash-lite` | Intake extraction, denial parsing |
| `reasoning` | `gemini-3.8-flash` | Criterion matching, appeal drafting |

These rotate as daily quotas are exhausted. Cassettes are keyed on **tier**, not model id, so
rotating a model does not discard recorded responses.

Override with `ATTEST_MODEL_FAST` / `ATTEST_MODEL_REASONING` in `.env`.

### Why these models

Chosen by probing the live API on 2026-09-08, **not** from the Strands docs, which still name
`gemini-2.5-*`. Those are retired for new keys and return 404.

- **Pro-class models are unusable on the free tier.** `gemini-3.1-pro-preview` and
  `gemini-pro-latest` both return `429 RESOURCE_EXHAUSTED` — there is effectively no free Pro
  quota. If billing is ever enabled, point `ATTEST_MODEL_REASONING` at a Pro model and re-run the
  P3 gate to measure the difference.
- **`gemini-3.8-flash` is capacity-constrained.** It returned 503 on every attempt. `3.6` and
  `3.5` both work and both handle structured output correctly.
- **No `-latest` aliases.** They shift underneath us, which would let demo behaviour drift between
  the recorded video and the judges' run.

### Quota: 20 requests per day, per model

Not per minute. This is the project's binding constraint.

Mitigations already in place:
- **Cassettes** (`cassettes/`) record every structured response. The full suite replays offline in
  under a second with no API key — run `./scripts/verify.sh ALL --offline`.
- **Batching**: all criteria for a case go in one call, so a full run is 3 calls rather than 30.
- **Rotation**: each model has its own daily allowance. Change `DEFAULT_MODELS` in
  `src/attest/llm.py` when one is exhausted.

Iteration still costs quota, because changing a prompt changes the cache key and forces a
re-record. **Enabling billing on the same key removes the ceiling** — no code change, and at
flash pricing the entire project is a few dollars. Recommended before P4/P5.

`attest.llm.with_retry` also handles transient `503 high demand`, which the free tier returns
unpredictably. Permanent errors (bad key, retired model) are re-raised immediately.

## Switching to Amazon Bedrock

Nothing outside `src/attest/llm.py` names a provider. To move to Bedrock, swap the constructor in
`build_model()` for `BedrockModel` and set the region. See `DECISIONS.md` for why Bedrock was
deferred to P7.

## Submission accounts (P8-S5, not needed to build)

- **AWS Builder ID** — required Devpost field. <https://profile.aws.amazon.com>
- **AWS $50 credit** — form closes **Sep 11, 2026, 12:00pm PT**. Worth requesting even though the
  build uses Gemini, since a P7 AgentCore deployment would consume it.

| Item | Status |
|---|---|
| Gemini API key | done |
| **Rotate the Gemini key** | **outstanding** — it was pasted into a chat transcript on 09-08. Regenerate at <https://aistudio.google.com/apikey> and update `.env`. Low stakes (free-tier key, gitignored), but worth closing. |
| Enable Gemini billing | recommended before P4/P5 — removes the 20/day ceiling |
| AWS Builder ID | **outstanding** — required Devpost field, free, no AWS account needed |
| AWS $50 credit request | **outstanding** — closes Sep 11, 12:00pm PT. Only useful if P7 AgentCore happens. |
