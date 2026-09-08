"""Decompose a published payer policy into discrete, checkable criteria.

This is the automated path from a policy PDF to a draft pack. Its output is a **draft for human
review**, never a shipped pack. `ingest_policy` deliberately writes nothing: every pack under
`policies/packs/` is reviewed by a person before it can be cited in an appeal.

That restraint is the point. A mis-decomposed criterion does not fail loudly — it silently changes
what the agent checks a patient's note against, and the resulting packet argues the wrong thing at
the payer. The one place a human must stay in the loop on the policy side is here.
"""

from __future__ import annotations

from pydantic import Field
from strands import Agent

from attest.cache import cached_structured
from attest.llm import build_model, with_retry
from attest.models import Base, Criterion, Polarity

SYSTEM_PROMPT = """\
You convert published health-insurer medical policies into a list of discrete, individually
checkable criteria.

Rules:
- One criterion per requirement. If the policy states four conditions joined by "and", that is
  four criteria, not one.
- Keep a compound "ANY ONE of the following" alternative as a SINGLE criterion. Splitting it
  would turn alternatives into requirements and wrongly fail patients who satisfy one branch.
- Quote the policy's own wording in `text`. Do not paraphrase, simplify, or modernise it. The
  text is quoted back to the payer in appeals, so it must match their document.
- `source_section` must locate the criterion in the policy as precisely as the document allows.
- `polarity` is "absent" for contraindications and exclusions - things that must NOT be present
  for the service to be covered - and "present" for everything else.
- `category` is a short lowercase label, e.g. eligibility, diagnosis, treatment_resistance,
  psychotherapy, contraindication, device, treatment_plan, provider_qualification.
- Ignore administrative boilerplate: effective dates, approval bodies, disclaimers, revision
  history, references.
"""


class DraftCriteria(Base):
    criteria: list[Criterion] = Field(
        min_length=1, description="Every distinct checkable criterion found in the policy."
    )


def ingest_policy(text: str, *, pack_hint: str = "draft") -> list[Criterion]:
    """Extract draft criteria from raw policy text.

    Returns criteria only. It writes no files by design — see the module docstring.
    """
    prompt = (
        "Extract every distinct medical-necessity criterion from this payer policy.\n\n"
        f"{text}"
    )

    def produce() -> DraftCriteria:
        agent = Agent(model=build_model("reasoning"), system_prompt=SYSTEM_PROMPT)
        return with_retry(
            lambda: agent(prompt, structured_output_model=DraftCriteria)
        ).structured_output

    return cached_structured(
        "ingest", "reasoning", SYSTEM_PROMPT + prompt, DraftCriteria, produce
    ).criteria
