# Agents for Humans: Building a Prior-Authorization Agent That Can't Make Things Up

*How we used the Strands Agents SDK to put four specialist agents, a deterministic evidence verifier, and two hard human approval gates between a clinical note and an insurance company — and what happened when our AWS account never opened.*

---

## The origin story: a problem everyone complains about and nobody fixes

We didn't start with prior authorization. We started by looking for the kind of problem that everyone in an industry complains about and nobody has fixed, because fixing it isn't glamorous. Prior authorization kept coming up.

Prior authorization is the approval an insurer demands before a patient can get a treatment that is, in every other respect, already covered. We expected an annoyance. The research says it's closer to a second job. The American Medical Association's surveys put it at **39 to 43 prior authorizations per physician per week**, consuming around **13 hours** of physician and staff time. That's most of a working day, every week, spent re-typing clinical facts into someone else's form. Roughly **31% of physicians** say their requests are often or always denied, and denials have been climbing for five years straight.

Then we found the detail that actually made us build this. **Appeals work. Most practices never file them.** They assume they'll lose, and every appeal has to be written from scratch by whoever has a spare hour, so it never happens. A denial that should have been a conversation quietly becomes treatment the patient doesn't get.

The tools that do exist are sold to large hospital systems with deep records integrations. A three-provider behavioral health clinic doesn't get any of that. They get a portal login and a fax number, and the hard part is still theirs: *does this even need an authorization? does the note actually satisfy this insurer's criteria? how do we argue back?*

That's the part we wanted to take off their desk — and the AWS **Agents for Humans** hackathon was the deadline that made us actually do it.

---

## The solution: Attest

**Attest reads a clinical note the practice has already written, works out which insurer's policy applies from the document itself, checks the note against that insurer's published criteria one at a time, and assembles a submission packet — then stops and waits for a clinician. When the denial comes back, it reads that too and drafts the appeal using the insurer's own policy wording, backed by exact quotes from the chart.**

Nothing gets re-typed. There's no dropdown for the payer and no setting to configure.

**What it does, concretely:**

- **Routes by reading.** It derives the applicable policy from the note's payer, plan and procedure codes. When it hits an insurer we have no policy on file for, it returns `UNKNOWN` and says so — never "no authorization needed."
- **Grades every criterion separately** as *met*, *not met*, or *insufficient evidence*, with the exact sentence from the note behind each verdict, highlighted in place.
- **Asks instead of assuming.** Where something's missing it asks a specific question back to the practice — which medication, at what dose, for how long — rather than filling in the blank itself.
- **Stops at a human gate** before anything is submitted. A named clinician approves a content hash.
- **Turns a denial into an appeal**, identifying which criteria the insurer is actually contesting and arguing with the insurer's own policy language.
- **Tracks the filing deadline**, and files approved appeal language as precedent so nobody writes the same argument twice.
- **Runs two insurers for the same treatment on purpose.** Highmark Health Options (Medicaid) wants four failed psychopharmacologic trials plus a failed psychotherapy course. PacificSource (Commercial) wants two trials at therapeutic dose for at least 8 weeks plus an augmentation trial. **Same patient, same treatment, different answer.**

That's the shape of the whole product: it does the assembling and the arguing, a person does the deciding and the sending.

**Try it yourself — no signup, no API key, no cost:** <https://attest.streamlit.app>

> `[SCREENSHOT: the criteria console — verdict chips, the note with its evidence highlighted in place, and the Gate 1 approval panel]`
>
> `[DEMO VIDEO — 2 min: upload a Highmark note, watch the criteria resolve, approve at Gate 1, upload the denial, watch the appeal draft itself]`

Every note and denial letter in the demo is synthetic and banner-marked. There is no real patient information anywhere in this build, and real records integration is deliberately out of scope.

---

## The AWS architecture and tech stack

Here is the honest version, stated up front, because a diagram that quietly disagrees with reality is worth less than no diagram:

> **The Strands Agents SDK is the only AWS SDK in this project. There is no Amazon Bedrock and no AgentCore. You do not need an AWS account to build, test or run Attest.**

That is a decision, not a gap waiting to close — and the story of how we got there is in the Challenges section below. What it leaves is small, reproducible, and leans on Strands harder than most hackathon projects lean on anything.

| Layer | Choice |
|---|---|
| **Agent framework** | `strands-agents` — orchestrator, four specialists, `agent.as_tool()` composition, structured output, hook interrupts, session persistence |
| **Model** | Gemini via Strands' `GeminiModel` (`strands-agents[gemini]`), named in exactly one file |
| **Everything safety-critical** | Plain deterministic Python — the evidence verifier, policy routing, the gap list, both emitters |
| **UI** | Streamlit, on Streamlit Community Cloud — public and keyless for judges |
| **Documents** | `fpdf2` for submission and appeal PDFs |
| **Tests** | `pytest` — 380 tests, replayed offline from committed model responses |

![Attest architecture: a clinical note is read by the intake specialist, routed to the payer's policy, matched criterion by criterion, and every quote checked verbatim by a deterministic verifier before Gate 1 stops for a named clinician. A denial letter arrives separately and the appeal specialist drafts rebuttals, held again at Gate 2.](UPLOAD_docs/architecture.png_AND_PASTE_URL_HERE)

### The one rule the whole architecture serves

**The orchestrator decides what happens next. It never decides what's true.**

Anything that could be checked is checked by ordinary code. Everything below is a way of enforcing that split with a Strands primitive instead of a prompt instruction.

### 1. Four specialists, composed as tools

The intake, criteria, packet and appeal specialists are each a Strands `Agent`, handed to an orchestrator through `agent.as_tool()`:

```python
return Agent(
    model=build_model("reasoning"),
    name="attest_orchestrator",
    system_prompt=SYSTEM_PROMPT,
    tools=[a.as_tool(name=a.name, description=a.description) for a in specialists],
)
```

Two things about this are load-bearing, and both are about keeping orchestration from eroding guarantees the deterministic pipeline already provides.

**Specialists exchange identifiers, never clinical content.** Every tool reads and writes a shared, code-owned `Run` object and returns a short factual summary — counts, criterion IDs, verdicts. It never returns a quote. If evidence travelled between agents as prose, each hop would be a chance for a model to paraphrase it, and the paraphrase would arrive at the packet builder looking exactly like a quote. The verifier couldn't catch it, because by then the note it would check against is two agents away. So the note is read once and the spans live in `Run`, where only code touches them.

**Verification lives inside the criteria tool, not as a step the orchestrator can choose.** A router that *could* skip verification would eventually skip it. `assess_criteria` matches and enforces in one indivisible call, and there is no tool anywhere that returns unverified coverage. No routing decision, however confused, can produce a packet built on unverified evidence.

A test pins this: the orchestrated run must produce **byte-identical verdicts** to the direct pipeline.

### 2. Structured output, so verdicts are never parsed from prose

Every model call in Attest returns a typed Pydantic model, not text we regex afterwards:

```python
agent = Agent(model=build_model("reasoning"), system_prompt=SYSTEM_PROMPT)
coverage = agent(prompt, structured_output_model=DraftCoverage).structured_output
```

A verdict of *insufficient evidence* is an enum member, not a phrase we hope to recognise. This matters more than it sounds — the distinction between "the note says this requirement wasn't met" and "the note doesn't say" is the single most important thing this product communicates, and it survives all the way to the screen only because it was never prose in the first place.

### 3. Human gates on `BeforeToolCallEvent.interrupt()`

Both approval gates are a Strands `HookProvider` that interrupts before the emitting tool runs:

```python
def register_hooks(self, registry, **kwargs):
    registry.add_callback(BeforeToolCallEvent, self.require_approval)

def require_approval(self, event: BeforeToolCallEvent) -> None:
    if event.tool_use["name"] != self.TOOL:
        return
    approver = event.interrupt(self.INTERRUPT, reason=reason)
    if not isinstance(approver, str) or not approver.strip():
        event.cancel_tool = self.REFUSAL   # nobody said yes is not nobody said no
        return
```

Strands stops the event loop and hands the interrupt back to the caller, so **the gate holds even when the agent is driven headlessly**, with no UI in the loop to remember to ask. This was the deciding reason we built the gates on the SDK's primitive rather than in the Streamlit layer: a gate implemented in a UI is a gate with a door beside it.

Two details we'd repeat on any human-in-the-loop agent:

- **The approval covers a content hash.** An approval record without one proves an approval happened at *some* point. With one, it proves a clinician approved *this* content — so editing a document after sign-off invalidates the approval rather than riding on it.
- **The emitters independently refuse to write** without a matching approval record. Enforcing the same rule in two places that don't know about each other is the cheapest insurance we bought all week.

### 4. Session persistence for the case store

Cases persist through Strands' own session machinery — `SnapshotSessionManager` over `LocalFileStorage`, one session per case:

```python
agent = Agent(agent_id=AGENT_ID, state=state)
asyncio.run(manager.save_snapshot(agent, is_latest=True))
```

This is what makes precedent reuse possible: once a clinician approves an appeal argument, that language comes back as a starting point the next time the same criterion gets contested.

### 5. The model provider is one file, and that turned out to matter

```python
# src/attest/llm.py - the single place the rest of the codebase learns which model to use.
DEFAULT_MODELS = {"fast": "gemini-3.5-flash-lite", "reasoning": "gemini-3.6-flash"}
```

Nothing else in the codebase names a provider. Two tiers, because the pipeline's demands are wildly uneven — intake extraction is field-pulling that any current model handles, while criterion matching needs drug-class knowledge, therapeutic-dose judgement, date arithmetic against a duration bar, and exact verbatim quoting.

Strands' model-provider interface is what made this a real boundary rather than an aspiration. When we were forced to change providers mid-build, **the change cost one file and no engine code.**

### Insurer policies are data, not code

Each policy is a YAML file listing that policy's criteria, quoted word for word from the real published document, with a source URL and section reference on every single criterion:

```yaml
pack_id: highmark-hho-de-mp-1147
payer: Highmark Health Options
service: Transcranial magnetic stimulation for major depressive disorder
cpt_codes: ["90867", "90868", "90869"]
source_url: https://www.highmarkhealthoptions.com/.../hho-de-mp-1147-...pdf
criteria:
  - id: hho-05
    category: contraindication
    source_section: "POLICY POSITION, contraindications, bullet 1"
    polarity: absent
    text: "Seizure disorder or any history of seizure with increased risk of future seizure"
```

Late in the build we added an entirely different specialty — physical therapy, VNS Health Medicare — to see how much code it would take. **It took none. It was one more file.**

### The verifier: a checker, not an instruction

Before any quote can appear in any generated document, it is checked character by character against the source note. Not asked for politely in a prompt. Checked. Runs of whitespace are treated as equivalent and Markdown emphasis markers are stripped, because a model quoting an honest sentence flattens the note's line wrapping. **Nothing else is forgiven** — case differences, changed numbers, substituted words and paraphrase all fail.

It is strict enough that it rejects a *correct* paraphrase, which felt wrong for about a day. Then we remembered that paraphrase is exactly the thing we're defending against. In a document that goes to an insurer about a real patient, "close enough" is how a sentence nobody ever said ends up in someone's file. Unverifiable spans downgrade their criterion to *insufficient* and get logged, never silently dropped.

---

## Challenges and breakthroughs

### The cloud we planned on never opened for us

The intent from day one was Amazon Bedrock with AgentCore Runtime. Our AWS account went into verification and never came out. Bedrock model access read `authorizationStatus: NOT_AUTHORIZED` account-wide, with `agreementAvailability: NOT_AVAILABLE`, on every re-check across four days.

Nothing was misconfigured. Credentials authenticated. IAM carried `AmazonBedrockFullAccess`. The region was right. The control plane cheerfully returned all 116 models — we just couldn't invoke any of them. It wasn't our gate to open, and it didn't move.

So we moved the model provider to Gemini behind that one file, and with the deadline closing, "blocked on a third party" stopped being a status and became an answer. On the last day we did the thing that felt worse and was right: **we deleted the AgentCore entrypoint and its dependency outright**, rather than shipping a README that said "no AgentCore" on a repository whose `pip install -e .` quietly pulls an AgentCore SDK. That entrypoint was real, working, gated code with fifteen passing tests. It went because the runtime it was an entrypoint *for* was gone.

The test that used to assert the dependency **now asserts its absence** — `bedrock-agentcore` sits on a forbidden-dependency list, and the build fails if it ever returns. This project rejects paraphrase in a medical-necessity justification on exactly that principle: a claim must be checkable against its source. The principle doesn't get suspended for our own packaging.

The path back is cheap by construction. Nothing outside `llm.py` names a provider, and no engine module ever imported AgentCore.

### Then the free tier turned out to be 20 requests per day

Per *day*, not per minute. One full pass over our test cases is about thirty calls. We literally could not run our own tests twice in an afternoon.

**This produced the best feature we didn't plan.** To survive the quota we started recording every model response to disk and committing the recordings, so tests replay them instead of calling out. What that actually produced is a project anyone can clone and run with **no API key, no network and no cost**: all **380 tests**, offline, with the same results we get. The public demo works the same way, which is why it never asks anyone for credentials.

```bash
./scripts/verify.sh ALL --offline
```

Cache keys hash the *tier* and the full input, deliberately not the model ID, because free-tier quotas are per model and we rotated models as each one burned out. Changing a prompt, a schema or a note still invalidates the entry automatically, so a stale recording can never silently mask a regression.

### Our own bug fix taught the model to lie

The note-reading step kept occasionally returning an empty list of procedure codes, so we did the obvious thing and made the field required. Next run, it confidently produced two procedure codes for a note that contained none — filled in from general knowledge of how that treatment is usually billed.

We had built a form where *"there's nothing here"* was impossible to say, so it made something up instead. That is precisely the failure this entire product exists to prevent, and we had reproduced it ourselves with a fix meant to improve reliability. We took the constraint back out and made absence something the model could report.

**Never build a form where "nothing here" can't be said.** Not for a model, not for a person.

### Saying the right thing the wrong way is still wrong

Some criteria are requirements to be *absent* — a seizure history, for this treatment. Our console showed a green tick next to **"Seizure disorder or any history of seizure,"** which is the technically correct verdict and reads, to anyone who isn't a clinician, as *this patient has a seizure disorder*. It means the exact opposite.

A correct answer displayed badly is a wrong answer with extra steps. We rewrote how every negative-polarity verdict is worded. We had spent weeks making sure the system couldn't produce an unsupported claim and then nearly undid it with a tick mark: **the interface is part of the safety argument.**

### Twice our answer key was wrong and the agent was right

We built the answer key before we built the grader — realistic synthetic notes, worked through by hand first, writing out criterion by criterion what a careful human reviewer should conclude and why, committed before any matching code existed. "It works" stopped being a judgment call and became a score.

Then the agent flagged that one note requested a treatment and never stated the procedure codes, and two others never stated the patient's age — which is itself one of the criteria. **We had written those notes ourselves, on purpose, trying to make them complete.** We fixed the notes rather than lowering the bar. The agent caught documentation gaps its own authors had missed, which is the product's entire pitch demonstrated against the people who built it.

---

## What we learned

- **A checker beats an instruction.** Asking a model to quote exactly is a hope. Verifying the quote is a guarantee. Every time we found ourselves writing a more emphatic prompt, the better move was to stop asking and start checking.
- **"I don't know" is a feature and it needs protecting.** It's the answer that's easiest to lose, because it looks like a gap in the product rather than an honest result. It's usually the most useful thing the system can say.
- **Hard limits made a better product than a bigger budget would have.** We only built the offline, reproducible version because we couldn't afford to call the model. It's now the thing that makes the project verifiable by anyone.

---

## Try it, break it, tell us

- **Live demo** (public, no key, no signup): <https://attest.streamlit.app>
- **GitHub** (Apache 2.0, 380 tests that run offline in one command): <https://github.com/ojassug/Attest>
- **Hackathon**: [AWS Agents for Humans](https://agentsforhumans.devpost.com)

Clone it and run `./scripts/verify.sh ALL --offline` — no API key, no AWS account, nothing to sign up for. Upload a note for one insurer, then a note for a different one into the same untouched screen, and watch it reach two completely different sets of criteria because it worked out which policy applied by reading the document.

Then feed it an insurer we have no policy for, and watch it refuse to guess. Telling a practice "no authorization needed" when the truth is "we couldn't find the rules" is the single most expensive mistake this tool could make — so it doesn't make it.

If you've worked a prior-auth desk and we've got something wrong, we'd genuinely like to hear it. Open an issue.

*Built for the AWS Agents for Humans hackathon on the [Strands Agents SDK](https://github.com/strands-agents). All clinical data shown is synthetic.*
