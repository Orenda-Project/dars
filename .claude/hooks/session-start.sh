#!/bin/bash
BEADS_FILE="$(git rev-parse --show-toplevel 2>/dev/null)/.beads/status.jsonl"

if [ ! -f "$BEADS_FILE" ]; then
  exit 0
fi

OPEN=$(python3 -c "
import json, sys
seen = {}
with open('$BEADS_FILE') as f:
    for line in f:
        try:
            d = json.loads(line)
            if 'id' in d:
                seen[d['id']] = d
        except: pass
for d in seen.values():
    if d.get('status') in ('open', 'in_progress'):
        print(f'  [{d.get(\"priority\",\"?\").upper()}] {d.get(\"id\",\"?\")}: {d.get(\"title\",\"?\")}')
" 2>/dev/null)

if [ -n "$OPEN" ]; then
  echo "=== OPEN BEADS ==="
  echo "$OPEN"
  echo "=================="
fi

exit 0
