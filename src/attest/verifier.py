"""Deterministic proof that a quoted span really appears in the source note.

Nothing here calls a model. That is the point: `Attest-PRODUCT.md` §6 makes evidence
traceability non-negotiable, and a prompt instruction is a hope where a verifier is a guarantee.
Every clinical claim in every generated document has to survive this module first.

**What counts as verbatim.** Runs of whitespace are equivalent — a model quoting an honest
sentence will flatten the note's line wrapping and its double spaces after a full stop, and
rejecting that would reject true evidence. Nothing else is forgiven. Case differences, changed
numbers, substituted words and paraphrase all fail. A verifier that starts forgiving case is one
step from forgiving a dose.

**Offsets index the original note**, not the normalised copy, so a reviewer opening the note can
land on the exact characters that were matched. That mapping is the only real subtlety in the
module: normalisation changes lengths, so each surviving character carries its source index.
"""

from __future__ import annotations

from pydantic import Field

from attest.models import Base, CriteriaCoverage, EvidenceSpan


def _normalise(text: str) -> str:
    """Collapse every run of whitespace to a single space, and strip the ends."""
    return " ".join(text.split())


def _normalise_with_offsets(note: str) -> tuple[str, list[int]]:
    """Normalise `note`, and record where each surviving character came from.

    Returns the normalised text plus a list the same length, where entry `i` is the index in
    the original `note` of the character at position `i`. A collapsed whitespace run is
    represented by its first character's index, so a match that begins or ends on one still
    brackets real note text.
    """
    chars: list[str] = []
    origin: list[int] = []
    in_whitespace = True  # leading whitespace is dropped, matching str.split()

    for i, ch in enumerate(note):
        if ch.isspace():
            if not in_whitespace:
                chars.append(" ")
                origin.append(i)
                in_whitespace = True
        else:
            chars.append(ch)
            origin.append(i)
            in_whitespace = False

    if chars and chars[-1] == " ":  # trailing whitespace run
        chars.pop()
        origin.pop()

    return "".join(chars), origin


class SpanVerification(Base):
    """The verdict on one quoted span.

    `quote` is carried even on a rejection: P3-S4 logs the offending text, and a rejection you
    cannot read is not an audit trail.
    """

    span_id: str
    quote: str
    verified: bool
    start: int | None = None
    end: int | None = None
    matched_text: str | None = Field(
        default=None, description="The exact run of note text matched. None when rejected."
    )
    reason: str = Field(default="", description="Why it was rejected. Empty when verified.")


class VerificationReport(Base):
    """Every span in one case's coverage, checked."""

    case_id: str
    results: list[SpanVerification] = Field(default_factory=list)

    @property
    def rejected(self) -> list[SpanVerification]:
        return [r for r in self.results if not r.verified]

    @property
    def verified_ids(self) -> set[str]:
        """The ids a downstream document is allowed to cite. Used by P4-S1."""
        return {r.span_id for r in self.results if r.verified}

    @property
    def all_verified(self) -> bool:
        """True when nothing was rejected — vacuously true for a coverage with no spans."""
        return not self.rejected


def verify_span(span: EvidenceSpan, note: str) -> SpanVerification:
    """Locate `span.quote` in `note` verbatim, up to whitespace.

    Returns character offsets into `note` itself, such that `note[start:end]` is the matched
    text. A quote that cannot be found is rejected with a reason; it is never repaired,
    softened, or fuzzily matched.
    """
    quote = _normalise(span.quote)
    if not quote:
        return SpanVerification(
            span_id=span.span_id,
            quote=span.quote,
            verified=False,
            reason="quote is empty once whitespace is normalised",
        )

    haystack, origin = _normalise_with_offsets(note)
    at = haystack.find(quote)

    if at == -1:
        return SpanVerification(
            span_id=span.span_id,
            quote=span.quote,
            verified=False,
            reason="quote does not appear verbatim in the note",
        )

    start = origin[at]
    end = origin[at + len(quote) - 1] + 1

    return SpanVerification(
        span_id=span.span_id,
        quote=span.quote,
        verified=True,
        start=start,
        end=end,
        matched_text=note[start:end],
    )


def verify_coverage(coverage: CriteriaCoverage, note: str) -> VerificationReport:
    """Check every span across every verdict in a coverage, in order."""
    return VerificationReport(
        case_id=coverage.case_id,
        results=[
            verify_span(span, note) for verdict in coverage.verdicts for span in verdict.spans
        ],
    )
