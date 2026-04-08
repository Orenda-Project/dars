#!/bin/bash
FILEPATH=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null)

# Syntax check Python files
if echo "$FILEPATH" | grep -qE "\.py$"; then
  if ! python3 -m py_compile "$FILEPATH" 2>/tmp/dars-syntax-error; then
    echo "ERROR: Python syntax error in $FILEPATH:" >&2
    cat /tmp/dars-syntax-error >&2
    exit 2
  fi
fi

exit 0
