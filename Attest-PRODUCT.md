# Attest — Product Specification

> **Working name:** Attest (placeholder — swap freely).
> **One line:** An AI agent that handles the prior authorization (PA) lifecycle for small specialty practices — from deciding whether a service needs a PA, to assembling a criteria-matched request, to auto-drafting the appeal when a payer denies.
> **Track:** Professional Agents — AWS "Agents for Humans" hackathon.
> **Scope of this doc:** *what the product is, what it must achieve, and the rules it must satisfy.* It deliberately contains no architecture, technology choices, or build-phase planning.

---

## 1. Hackathon requirements (exact, from the official rules)

**Source:** agentsforhumans.devpost.com/rules (rules updated 8/12/26). Sponsor: Amazon Web Services. Administrator: Devpost.

### 1.1 Dates
- **Submission period:** Aug 10, 2026 (9:00am PT) – **Sep 14, 2026 (5:00pm PT)**.
- **Judging:** Sep 15 – Oct 8, 2026.
- **Winners announced:** on or around Oct 14, 2026.
- **AWS promotional credits ($50):** must be requested via the official form by **Sep 11, 2026, 12:00pm PT**; credits expire Oct 31, 2026.

### 1.2 Eligibility (relevant points)
- Open to individuals at the age of majority where they reside, teams of such individuals, and organizations.
- Excluded residents/domiciles include (non-exhaustive): Argentina, Australia, Brazil, Hong Kong, Indonesia, Italy, Malaysia, Philippines, Thailand, Vietnam, Singapore, Belarus, UAE, Quebec, Russia, Crimea, Cuba, Iran, North Korea, Syria, and OFAC-designated countries. **India is not excluded — eligible.**

### 1.3 What to build (project requirements)
- A **new** AI agent built with the **Strands Agents SDK** that does real work for real people and handles a task **end to end** (not just chat).
- Enter it in **one track** (this project: Professional Agents).
- Must be newly created during the submission period. Standard frameworks, libraries, starter templates, and AI coding assistants are allowed; any pre-existing code/work incorporated must be disclosed.
- Must install and run consistently and function as shown in the video/description.
- **Deploying with Amazon Bedrock AgentCore is optional** but explicitly strengthens the Technical Implementation score.
- Any third-party SDK/API/data used must be properly licensed/authorized.

### 1.4 What to submit
- **Text description** of features and functionality.
- **Public code repo** (GitHub/GitLab/Bitbucket) with all source, assets, and setup instructions; **MIT or Apache license** file, visible in the repo's About section.
- **README**.
- **Architecture diagram.**
- **Demo video, max 5 minutes**, showing the working project and a pitch covering (1) the problem, (2) who it's for, (3) why it matters. Slides/screen-recording/voiceover fine; no need to be on camera. Must be public on YouTube or Vimeo.
- **AWS Builder ID.**
- **(Optional) live demo link** — improves the Technical Implementation score.
- **(Optional) builder.aws blog post(s)** — bonus scoring (see 1.6).
- All materials in English (or with English translation).
- A working project must be testable by judges for free until judging ends (include credentials/instructions if access is gated).

### 1.5 Judging criteria (five, equally weighted)
1. **Technical Implementation** — how thoroughly and skillfully the project uses Strands Agents; genuine, non-trivial, working implementation. A live demo and/or AgentCore deployment strengthens this.
2. **Design** — a complete, coherent product experience, not just a technical proof of concept.
3. **Potential Impact** — a credible, specific case for solving a real problem for a real audience, and a solution that actually addresses it as demonstrated.
4. **Creativity & Originality** — a creative, non-obvious use of Strands Agents plus demonstrated understanding of the problem space.
5. **Presentation** — the video clearly shows the project working end to end; the pitch communicates what/who/why; overall clarity.

*Judging is two-stage: Stage One is pass/fail on baseline viability + fit with theme and required tools; Stage Two scores the five criteria above.*

### 1.6 Prizes
- **Grand Prize:** $10,000 + AWS social feature + roundtable with AWS experts (all eligible submissions).
- **Per track (Everyday / Professional / Good Neighbor):** Gold $5,000 · Silver $3,000 · Bronze $2,000.
- A project can win a maximum of one prize.
- **Bonus:** up to **+0.6** points for builder.aws blog post(s) (0.2 each; title must use "Agents for Humans"). Final scores range 1–5.6.

### 1.7 What this means for our build (constraints, not architecture)
- Must be a Strands Agents project, newly built, that runs end to end and is judge-testable.
- Prioritize a live demo and (if feasible) AgentCore deployment for the Technical Implementation score.
- The 5-minute video and the impact case carry as much weight as the code — plan for them as first-class deliverables.

---

## 2. Problem

Prior authorization is insurer pre-approval required before a clinician can deliver a covered service. It is the largest administrative time-sink in outpatient care, and small/solo specialty practices (behavioral health, physical therapy, occupational/speech therapy, pain, imaging) absorb it directly because they have no dedicated PA staff.

Verified pain (cite the survey year you use):
- Practices complete ~39–43 PA requests per physician per week (AMA 2024/2025 surveys).
- ~13 hours/week of physician + staff time consumed by PA (AMA); an earlier AMA survey put physician + staff time at 16.4 hrs/week.
- ~31% of physicians report requests are often/always denied; denials have risen over five years.
- Appeals are effective but under-used — many practices don't appeal because they expect to lose, and those who do rebuild each appeal from scratch.

Why it stays unsolved for this user: existing PA vendors target large health systems and deep EHR integrations. Solo/small practices are left with manual portals, faxes, and copy-paste appeal letters. The judgment-heavy part — does this need a PA? does the note satisfy the payer's criteria? how do we rebut this specific denial? — is precisely what current tooling leaves to a human.

---

## 3. Target user

- **Primary:** the office manager, front-desk staff, or owner-clinician at a 1–10 provider specialty practice who personally handles PAs.
- **Secondary:** the treating clinician who must approve the clinical justification.
- **Specialty focus:** one specialty at a time (e.g. outpatient behavioral health or physical therapy), so the product speaks that specialty's language and payer rules precisely.

---

## 4. What the product does

Given a patient's clinical note and insurance details, Attest:

1. **Reads and structures the case** — pulls out the service requested, diagnosis, requested duration/units, payer, and plan.
2. **Determines whether a prior authorization is required** for that service under that payer/plan, and explains why, pointing to the policy it relied on.
3. **Finds the payer's own clinical criteria** for the service and **checks the note against each criterion**, marking each as met, unmet, or insufficiently supported, and quoting the exact note evidence for each.
4. **Flags gaps** — where a criterion isn't supported, it says so and asks the practice for the missing detail rather than guessing.
5. **Assembles a submission-ready request** — the completed request fields, a medical-necessity justification written only from approved evidence, and a plain-language checklist of how each criterion is covered.
6. **Pauses for the clinician to approve or edit** every clinical assertion before anything is submitted.
7. **Produces the outbound submission artifact** once approved.
8. **Turns a denial into an appeal** — when a payer denies, it reads the denial reason, identifies which criteria the payer contests, and drafts an appeal that cites the payer's own policy language and the note evidence — again held for human approval before it goes out.
9. **Tracks each case and its appeal deadline**, and reuses language from prior successful appeals on similar future denials.

---

## 5. Goals

1. Cut the human time per PA from ~20–30 minutes to a short review-and-approve step.
2. Raise first-pass approval rates by ensuring every submission is mapped to the payer's stated criteria before it goes out.
3. Make appeals the default rather than the exception, by generating a strong, criteria-cited appeal automatically on denial.
4. Keep a clinician in control: the agent drafts and assembles; a human approves every clinical claim and every outbound document.

---

## 6. Human-in-the-loop (non-negotiable product behavior)

Two hard gates where the agent stops and a human acts:
1. **Before submission** — the clinician reviews and edits every clinical assertion and the criteria coverage, then approves.
2. **Before an appeal is sent** — the same review on the appeal letter.

Everywhere else the agent runs autonomously. The gates are a product requirement, not a limitation: they are what makes the tool safe to adopt in a real practice. Every clinical claim in any generated document must be traceable to a quoted span in the source note; the agent must not invent clinical facts, and where evidence for a criterion is missing it asks rather than assumes.

---

## 7. Compliance & safety (product requirements)

- **The agent assembles and argues; humans decide and submit.** It never makes a coverage or medical-necessity decision on its own.
- **Evidence-traceable by design.** No clinical claim appears in any document unless it is backed by a quote from the source note.
- **Privacy-first.** The product handles protected health information, so it is built around encryption in transit and at rest, least-privilege access, and a complete audit trail of every agent action and every human approval.
- **Demo uses synthetic data only.** No real patient data is used for the hackathon build or video; live payer-portal and EHR integration and real-PHI handling are explicitly post-hackathon, gated on the appropriate agreements. Stating this openly is a strength — it shows command of the domain — and keeps the submission clean.
- **Honest scope in the pitch.** The product is presented as an assistant that produces submission-ready and appeal-ready documents for human approval, not as an autonomous authority over care decisions.

---

## 8. Judging alignment (how the product maps to the five criteria)

- **Technical Implementation** — a genuinely agentic, multi-step, tool-using system built on Strands Agents that determines PA need, matches criteria to evidence, and autonomously drafts appeals; strengthened by a live demo and (if feasible) AgentCore deployment.
- **Design** — a complete experience an office manager could actually use: clear two-gate approval flow and a plain-language criteria-coverage checklist, not a bare proof of concept.
- **Potential Impact** — a specific, credible case grounded in the section 2 numbers, with a measured before/after on time-per-PA and criteria coverage on the demo cases.
- **Creativity & Originality** — the autonomous denial→appeal loop that cites the payer's *own* published criteria, and the "make appeals the default" framing, demonstrating real understanding of the PA problem space.
- **Presentation** — a 5-minute video that walks one synthetic case end to end (note → packet → denial → appeal), opening with the problem, who it's for, and why it matters.
- **Bonus** — a builder.aws blog post on the build journey (up to +0.6).

---

## 9. Risks & mitigations

- **Perceived as "too simple / why doesn't this exist"** → the answer, made explicit in the pitch, is the last mile: payer integrations, PHI/BAAs, and liability are why incumbents chase large health systems; the agentic reasoning over criteria and denials is the new capability.
- **Criteria matching looks shallow** → show per-criterion evidence quotes and a real gap list, not a generic summary; this is the product's core and must be the strongest part of the demo.
- **Hallucinated clinical facts** → enforce the evidence-traceability rule from section 6; the agent quotes the note or asks for the missing detail.
- **Scope creep into an EHR / clearinghouse / billing system** → hold the non-goals in section 10; one specialty and one payer are enough to prove the product.
- **Compliance concerns from judges** → the synthetic-data stance and the human-approval gates are stated up front, framed as deliberate product design.

---

## 10. Explicitly out of scope

- Not an EHR, practice-management system, or billing/clearinghouse.
- Not a coverage or medical decision-maker.
- Not a general healthcare chatbot.
- No live payer/EHR integration or real-PHI handling in the hackathon build.
