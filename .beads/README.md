---
type: reference
last_verified: 2026-04-08
owner: hataf
---

# Beads — Work Tracking

Append-only JSONL issue tracker. Three files:

| File | Purpose |
|------|---------|
| [status.jsonl](status.jsonl) | All tasks (open, in_progress, closed, blocked) |
| [decisions.jsonl](decisions.jsonl) | Architectural decisions and rationale |
| [failures.jsonl](failures.jsonl) | Production incidents and lessons learned |

## Rules

- **Append only** — never edit a previous line
- **Open a bead before touching code**, close it after verifying the fix
- Resolution field must answer: what was done and how to verify it

## Lifecycle

`open` → `in_progress` → `closed` (or `blocked`)

## Querying

```bash
# All open work
grep '"status":"open"' .beads/status.jsonl | python3 -c "
import json,sys
for line in sys.stdin:
    try:
        d=json.loads(line)
        print(f'[{d[\"priority\"].upper()}] {d[\"id\"]}: {d[\"title\"]}')
    except: pass
"

# All bugs
grep '"category":"bug"' .beads/status.jsonl

# Blocked items
grep '"status":"blocked"' .beads/status.jsonl
```

## Why this exists

Claude Code has no persistent memory across context resets. The session-start hook reads open beads and injects them into every session — this is how in-flight work survives a context window fill.
