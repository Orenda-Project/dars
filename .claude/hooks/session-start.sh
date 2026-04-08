#!/bin/bash
BEADS_FILE="$(git rev-parse --show-toplevel 2>/dev/null)/.beads/status.jsonl"

if [ ! -f "$BEADS_FILE" ]; then
  exit 0
fi

OPEN=$(grep -E '"status":\s*"(open|in_progress)"' "$BEADS_FILE" 2>/dev/null | tail -10)

if [ -n "$OPEN" ]; then
  echo "=== OPEN BEADS ==="
  echo "$OPEN" | python3 -c "
import json,sys
for line in sys.stdin:
    try:
        d=json.loads(line)
        print(f'  [{d.get(\"priority\",\"?\").upper()}] {d.get(\"id\",\"?\")}: {d.get(\"title\",\"?\")}')
    except: pass
"
  echo "=================="
fi

exit 0
