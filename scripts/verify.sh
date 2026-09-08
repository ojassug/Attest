#!/usr/bin/env bash
#
# Gate runner. A step is DONE when its gate exits zero — not when it looks right.
#
#   ./scripts/verify.sh P3-S2       one step, plus every step before it
#   ./scripts/verify.sh P3          a whole phase, plus every phase before it
#   ./scripts/verify.sh ALL         everything
#   ./scripts/verify.sh P3 --offline   skip provider-connectivity tests (still a valid pass)
#
# Gates are cumulative: a later step cannot silently break an earlier one.
# The canonical step order is read from PLAN.md, which is the contract.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PLAN="PLAN.md"
OFFLINE=0
TARGET=""

for arg in "$@"; do
  case "$arg" in
    --offline) OFFLINE=1 ;;
    -*) echo "unknown flag: $arg" >&2; exit 2 ;;
    *)  TARGET="$arg" ;;
  esac
done

if [ -z "$TARGET" ]; then
  echo "usage: ./scripts/verify.sh <STEP_ID|PHASE_ID|ALL> [--offline]" >&2
  exit 2
fi

if [ ! -f "$PLAN" ]; then
  echo "FAIL: $PLAN not found — the step order is defined there." >&2
  exit 2
fi

# Ordered step list, straight from the contract.
STEPS=$(grep -oE '^## P[0-9]+-S[0-9]+' "$PLAN" | sed 's/^## //')
if [ -z "$STEPS" ]; then
  echo "FAIL: no step headings (## P<n>-S<n>) found in $PLAN" >&2
  exit 2
fi

# Resolve the target to the last step it includes.
case "$TARGET" in
  ALL|all)  STOP=$(echo "$STEPS" | tail -1) ;;
  P*-S*)    STOP="$TARGET" ;;
  P*)       STOP=$(echo "$STEPS" | grep "^${TARGET}-S" | tail -1 || true) ;;
  *)        echo "FAIL: '$TARGET' is not a step id, phase id, or ALL" >&2; exit 2 ;;
esac

if [ -z "${STOP:-}" ] || ! echo "$STEPS" | grep -qx "$STOP"; then
  echo "FAIL: '$TARGET' does not match any step or phase in $PLAN" >&2
  exit 2
fi

# Accumulate markers up to and including the stop step.
MARKERS=""
for s in $STEPS; do
  m=$(echo "$s" | tr 'A-Z-' 'a-z_')
  if [ -z "$MARKERS" ]; then MARKERS="$m"; else MARKERS="$MARKERS or $m"; fi
  if [ "$s" = "$STOP" ]; then break; fi
done

EXPR="($MARKERS)"
if [ "$OFFLINE" -eq 1 ]; then
  EXPR="$EXPR and not live"
fi

if [ -x ".venv/bin/pytest" ]; then PYTEST=".venv/bin/pytest"; else PYTEST="pytest"; fi

echo "gate: $TARGET  (through $STOP)"
[ "$OFFLINE" -eq 1 ] && echo "mode: OFFLINE — provider-connectivity tests excluded; model logic replays from cassettes"

set +e
"$PYTEST" -m "$EXPR" -q
CODE=$?
set -e

# pytest exits 5 when nothing was collected. No tests is not a passing gate.
if [ "$CODE" -eq 5 ]; then
  echo ""
  echo "FAIL: no tests matched '$TARGET'. A step with no test cannot be marked DONE."
  exit 1
fi

if [ "$CODE" -ne 0 ]; then
  echo ""
  echo "GATE FAILED: $TARGET"
  exit "$CODE"
fi

echo ""
if [ "$OFFLINE" -eq 1 ]; then
  echo "OFFLINE PASS: $TARGET"
  echo "Model-backed logic was replayed from cassettes; only provider-connectivity tests were"
  echo "skipped. This is a valid gate pass. Re-run without --offline after changing the provider."
else
  echo "GATE PASSED: $TARGET"
  echo "Record the commit SHA in STATUS.md."
fi
