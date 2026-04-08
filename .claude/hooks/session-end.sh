#!/bin/bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
BEADS_FILE="$ROOT/.beads/status.jsonl"

WARNINGS=""

# Check for open beads
if [ -f "$BEADS_FILE" ]; then
  OPEN_COUNT=$(grep -cE '"status":\s*"(open|in_progress)"' "$BEADS_FILE" 2>/dev/null || echo 0)
  if [ "$OPEN_COUNT" -gt 0 ]; then
    WARNINGS="$WARNINGS\n- $OPEN_COUNT open bead(s) — update status if work is done"
  fi
fi

# Check for unstaged changes
UNSTAGED=$(git -C "$ROOT" diff --stat 2>/dev/null | tail -1)
if [ -n "$UNSTAGED" ]; then
  WARNINGS="$WARNINGS\n- Unstaged changes exist — commit or stash before closing"
fi

if [ -n "$WARNINGS" ]; then
  echo "=== SESSION END ==="
  echo -e "$WARNINGS"
  echo "==================="
fi

exit 0
