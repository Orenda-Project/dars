#!/bin/bash
FILEPATH=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null)

# Warn on .env writes
if echo "$FILEPATH" | grep -qE "^\.env$|/\.env$"; then
  echo "WARNING: Writing to .env — verify you are not overwriting existing credentials." >&2
fi

# Enforce CLAUDE.md line limit
if echo "$FILEPATH" | grep -qE "CLAUDE\.md$"; then
  if [ -f "$FILEPATH" ]; then
    LINES=$(wc -l < "$FILEPATH")
    if [ "$LINES" -gt 150 ]; then
      echo "ERROR: CLAUDE.md has $LINES lines (limit: 150). Move content to L3 docs first." >&2
      exit 2
    fi
  fi
fi

exit 0
