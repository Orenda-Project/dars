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

# Nudge (non-blocking) when symbol-search bash patterns run with graphify present.
# Triggers on: `grep -rl/-rn/-r ... <symbol>`, `find ... -name "*.py" -exec grep`,
# `find ... | xargs grep`, or a bare `grep -r` across the tree.
# Suppress while inside a non-dars tree (graphify-out/ check below handles that).
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -n "$ROOT" ] && [ -f "$ROOT/graphify-out/graph.json" ]; then
  if echo "$COMMAND" | grep -qE '(^|[; |&])grep[[:space:]]+-[A-Za-z]*r[A-Za-z]*[[:space:]]'; then
    NUDGE=1
  elif echo "$COMMAND" | grep -qE 'find[[:space:]].*-(name|iname)[[:space:]].*-exec[[:space:]]+grep'; then
    NUDGE=1
  elif echo "$COMMAND" | grep -qE 'find[[:space:]].*\|[[:space:]]*xargs[[:space:]]+grep'; then
    NUDGE=1
  fi
  if [ "${NUDGE:-0}" = "1" ]; then
    echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"graphify: this command looks like a symbol/cross-file search. Prefer `graphify query \"where is <symbol> defined\"` or `graphify path \"<A>\" \"<B>\"` — they traverse EXTRACTED+INFERRED edges instead of scanning files. Keep grep/find only for literal text in known paths."}}'
  fi
fi

exit 0
