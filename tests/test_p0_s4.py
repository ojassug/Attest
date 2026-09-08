"""Gate for P0-S4 — the model provider actually works.

Marked `live`: these call the real API, so `--offline` skips them and says the result is not a
valid gate pass. The structured-output test is the load-bearing one — every later phase produces
typed verdicts through `structured_output_model`, so if that path is broken nothing downstream
can work, and the failure would surface as bad matching rather than as a broken provider.
"""

import pytest
from pydantic import BaseModel, Field

from attest.llm import (
    DEFAULT_MODELS,
    build_model,
    have_credentials,
    is_retryable,
    model_id,
    with_retry,
)

pytestmark = [pytest.mark.p0_s4, pytest.mark.live]

needs_key = pytest.mark.skipif(
    not have_credentials(), reason="no GOOGLE_API_KEY - see P0-S1"
)


class MedTrial(BaseModel):
    """Deliberately shaped like the real work: pull a drug, a dose and a duration out of prose."""

    drug: str = Field(description="Medication name")
    dose_mg: int = Field(description="Daily dose in milligrams")
    weeks: int = Field(description="Duration of the trial in weeks")


@needs_key
def test_model_tool_roundtrip():
    from strands import Agent, tool

    calls: list[tuple[str, str]] = []

    @tool
    def letter_counter(word: str, letter: str) -> int:
        """Count occurrences of a specific letter in a word."""
        calls.append((word, letter))
        return word.lower().count(letter.lower())

    agent = Agent(model=build_model("fast"), tools=[letter_counter])
    result = with_retry(lambda: agent("How many times does 'r' appear in 'strawberry'? Use the tool."))

    assert str(result).strip(), "model returned an empty response"
    assert calls, "the tool was never invoked - tool calling is not working"


@needs_key
def test_structured_output_roundtrip():
    """Typed extraction is the mechanism every later phase depends on."""
    from strands import Agent

    agent = Agent(model=build_model("reasoning"))
    result = with_retry(
        lambda: agent(
            "Extract the trial: 'Sertraline 200 mg daily, 2024-12-02 to 2025-03-14 (14 weeks).'",
            structured_output_model=MedTrial,
        )
    )

    out = result.structured_output
    assert isinstance(out, MedTrial)
    assert out.dose_mg == 200
    assert out.weeks == 14
    assert "sertraline" in out.drug.lower()


def test_retry_recovers_from_transient_failure():
    """No API call - proves the retry wrapper itself works."""
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("503 UNAVAILABLE: high demand")
        return "ok"

    assert with_retry(flaky, base_delay=0.01) == "ok"
    assert attempts["n"] == 3


def test_permanent_errors_are_not_retried():
    """A bad key must fail fast, not burn four attempts and a minute of backoff."""
    attempts = {"n": 0}

    def bad_key():
        attempts["n"] += 1
        raise RuntimeError("401 API key not valid")

    with pytest.raises(RuntimeError, match="API key not valid"):
        with_retry(bad_key, base_delay=0.01)
    assert attempts["n"] == 1


def test_models_are_pinned_not_aliases():
    """Aliases like gemini-flash-latest shift under us and would silently change demo behaviour
    between the recorded video and the judges' run."""
    for tier, mid in DEFAULT_MODELS.items():
        assert not mid.endswith("-latest"), f"{tier} points at a moving alias: {mid}"
        assert model_id(tier) == mid


def test_retryable_classification():
    assert is_retryable(RuntimeError("503 Service Unavailable"))
    assert is_retryable(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert not is_retryable(RuntimeError("404 model not found"))
