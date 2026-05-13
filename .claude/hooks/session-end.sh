#!/bin/bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
BEADS_FILE="$ROOT/.beads/status.jsonl"

WARNINGS=""

# Check for open beads
if [ -f "$BEADS_FILE" ]; then
  OPEN_COUNT=$(python3 -c "
import json
seen = {}
with open('$BEADS_FILE') as f:
    for line in f:
        try:
            d = json.loads(line)
            if 'id' in d: seen[d['id']] = d
        except: pass
print(sum(1 for d in seen.values() if d.get('status') in ('open','in_progress')))
" 2>/dev/null || echo 0)
  if [ "$OPEN_COUNT" -gt 0 ]; then
    WARNINGS="$WARNINGS\n- $OPEN_COUNT open bead(s) — update status if work is done"
  fi
fi

# Check for unstaged changes
UNSTAGED=$(git -C "$ROOT" diff --stat 2>/dev/null | tail -1)
if [ -n "$UNSTAGED" ]; then
  WARNINGS="$WARNINGS\n- Unstaged changes exist — commit or stash before closing"
fi

echo "=== SESSION END ==="
if [ -n "$WARNINGS" ]; then
  echo -e "$WARNINGS"
fi
echo "- Run /retrospect to log harness improvement suggestions for this session"
echo "==================="

exit 0
