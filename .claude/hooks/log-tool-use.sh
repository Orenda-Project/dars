#!/bin/bash
# Append each tool call to .claude/sessions/<session_id>.jsonl for /retrospect analysis.
# Reads the PostToolUse JSON payload from stdin, summarizes it, and writes one JSON line per call.

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
SESSIONS_DIR="$ROOT/.claude/sessions"
mkdir -p "$SESSIONS_DIR" 2>/dev/null

# Capture stdin into an env var so the heredoc'd python script can use stdin freely.
HOOK_PAYLOAD="$(cat)"
export HOOK_PAYLOAD SESSIONS_DIR

python3 <<'PY' 2>/dev/null
import json, os, sys
from datetime import datetime, timezone

sessions_dir = os.environ.get("SESSIONS_DIR", "")
raw = os.environ.get("HOOK_PAYLOAD", "")
if not sessions_dir or not raw:
    sys.exit(0)

try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)

session_id = data.get("session_id") or "unknown"
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {}) or {}
tool_response = data.get("tool_response", {}) or {}

# Summarize input compactly — never log full file contents.
summary = {}
if tool_name in ("Read", "Edit", "Write"):
    summary["file_path"] = tool_input.get("file_path")
    if tool_name == "Read":
        summary["offset"] = tool_input.get("offset")
        summary["limit"] = tool_input.get("limit")
elif tool_name == "Bash":
    cmd = tool_input.get("command", "")
    summary["command"] = cmd[:200]
elif tool_name in ("Glob", "Grep"):
    summary["pattern"] = tool_input.get("pattern")
    summary["path"] = tool_input.get("path")
elif tool_name == "Agent":
    summary["description"] = tool_input.get("description")
    summary["subagent_type"] = tool_input.get("subagent_type")
else:
    summary["keys"] = list(tool_input.keys())[:6]

is_error = False
if isinstance(tool_response, dict):
    if tool_response.get("is_error") or tool_response.get("error"):
        is_error = True

entry = {
    "ts": datetime.now(timezone.utc).isoformat(),
    "tool": tool_name,
    "summary": summary,
    "error": is_error,
}

out = os.path.join(sessions_dir, f"{session_id}.jsonl")
with open(out, "a") as f:
    f.write(json.dumps(entry) + "\n")
PY

exit 0
