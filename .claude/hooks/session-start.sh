#!/bin/bash
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
BEADS_FILE="$ROOT/.beads/status.jsonl"

# Open beads
if [ -f "$BEADS_FILE" ]; then
  OPEN=$(python3 -c "
import json
seen = {}
with open('$BEADS_FILE') as f:
    for line in f:
        try:
            d = json.loads(line)
            if 'id' in d: seen[d['id']] = d
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
fi

# Graphify index
GRAPH="$ROOT/graphify-out/GRAPH_REPORT.md"
if [ -f "$GRAPH" ]; then
  echo "=== GRAPH ==="
  echo "graphify-out/GRAPH_REPORT.md available — read it before answering architecture questions"
  echo "============="
fi

exit 0
