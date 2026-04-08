#!/bin/bash
COMMAND=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))" 2>/dev/null)

# Block committing .env files
if echo "$COMMAND" | grep -qE "git add.*\.env|git commit.*\.env"; then
  echo "ERROR: Attempting to commit .env file. Credentials must never be committed." >&2
  exit 2
fi

# Block force push to main
if echo "$COMMAND" | grep -qE "git push.*--force.*main|git push.*-f.*main"; then
  echo "ERROR: Force push to main is blocked." >&2
  exit 2
fi

# Require tests to pass before push
if echo "$COMMAND" | grep -qE "^git push"; then
  cd "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || true
  if ! make test &>/dev/null; then
    echo "ERROR: Tests are failing. Run 'make test' to see errors before pushing." >&2
    exit 2
  fi
fi

exit 0
