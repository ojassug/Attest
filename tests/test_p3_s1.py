"""Gate for P3-S1 — policy ingestion.

Graded by *topic recovery* rather than string equality: two correct decompositions of the same
policy will word and split things differently, so demanding an exact match would test phrasing
instead of comprehension. Each expected topic is identified by distinctive terms that any correct
reading of that requirement must contain.

The second test is the one that matters long term. Ingestion output is a draft for human review,
and nothing it produces may reach `policies/packs/` automatically — a mis-decomposed criterion
fails silently, changing what the agent checks a note against and arguing the wrong thing at the
payer.
"""

from pathlib import Path

import pytest

from attest.criteria.ingest import ingest_policy
from attest.models import Polarity
from attest.policies.loader import PACKS_DIR
from conftest import needs_model

pytestmark = pytest.mark.p3_s1

POLICY = Path(__file__).resolve().parents[1] / "data" / "policies" / "raw" / "highmark-hho-de-mp-1147.txt"

# Topic -> terms a correct reading of that requirement must mention.
EXPECTED_TOPICS: dict[str, tuple[str, ...]] = {
    "age": ("18",),
    "diagnosis": ("major depressive",),
    "treatment_resistance": ("four", "psychopharmacologic"),
    "psychotherapy": ("psychotherapy",),
    "seizure": ("seizure",),
    "psychosis": ("psychotic",),
    "neurologic": ("neurologic",),
    "implant": ("implant",),
    "device": ("fda",),
    "course_limit": ("six", "week"),
}
RECOVERY_THRESHOLD = 0.70


@pytest.fixture(scope="module")
def drafted():
    return ingest_policy(POLICY.read_text())


def test_policy_source_text_is_committed():
    """The ingestion test must be reproducible by a judge, so the source text lives in the repo."""
    assert POLICY.exists()
    assert "HHO-DE-MP-1147" in POLICY.read_text()


@needs_model
def test_ingest_recovers_known_criteria(drafted):
    blob = " ".join(f"{c.text} {c.category}" for c in drafted).lower()

    found = {
        topic for topic, terms in EXPECTED_TOPICS.items() if all(t in blob for t in terms)
    }
    missed = sorted(set(EXPECTED_TOPICS) - found)
    rate = len(found) / len(EXPECTED_TOPICS)

    assert rate >= RECOVERY_THRESHOLD, (
        f"recovered {rate:.0%} of known criteria (threshold {RECOVERY_THRESHOLD:.0%}); "
        f"missed {missed}"
    )


@needs_model
def test_ingest_marks_contraindications_absent(drafted):
    """Polarity must survive decomposition. If a contraindication comes back as `present`, the
    matcher reports every healthy patient as failing it."""
    contraindications = [
        c for c in drafted if "seizure" in c.text.lower() or "implant" in c.text.lower()
    ]
    assert contraindications, "no contraindication criteria were recovered at all"
    assert any(c.polarity is Polarity.ABSENT for c in contraindications)


@needs_model
def test_ingest_keeps_alternatives_as_one_criterion(drafted):
    """Highmark's treatment-resistance rule is 'ANY ONE of' four alternatives. Splitting it into
    four criteria would turn alternatives into requirements and wrongly fail real patients."""
    combined = [c for c in drafted if "any one" in c.text.lower()]
    assert combined, (
        "the 'ANY ONE of the following' alternative was not preserved as a single criterion"
    )


@needs_model
def test_ingest_quotes_rather_than_paraphrases(drafted):
    """Criteria are quoted back at the payer, so wording must come from their document."""
    source = POLICY.read_text().lower()
    anchored = [
        c for c in drafted
        if any(term in source for term in c.text.lower().split()[:6] if len(term) > 5)
    ]
    assert len(anchored) >= len(drafted) * 0.8


@needs_model
def test_every_drafted_criterion_is_locatable(drafted):
    for c in drafted:
        assert c.id.strip()
        assert c.text.strip()
        assert c.source_section.strip(), f"criterion {c.id!r} cannot be located in the policy"


def test_ingest_output_is_not_auto_shipped():
    """Ingestion must never write a pack. Human review is the gate between a drafted criterion
    and one the agent will argue from."""
    import inspect

    import attest.criteria.ingest as mod

    source = inspect.getsource(mod)
    for forbidden in ("write_text", "open(", "PACKS_DIR", "yaml.dump", "safe_dump"):
        assert forbidden not in source, (
            f"ingest.py references {forbidden!r} - it must not be able to write a pack"
        )


def test_no_pack_was_written_by_ingestion():
    """Belt and braces: the shipped packs are exactly the two reviewed ones."""
    assert sorted(p.stem for p in PACKS_DIR.glob("*.yaml")) == [
        "highmark-hho-de-mp-1147",
        "pacificsource-commercial-tms",
    ]
