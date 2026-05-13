---
type: usage-patterns
description: Observed behavioral patterns across retrospect sessions. Each pattern has a count and date log. Harness changes are only suggested once a pattern hits threshold (3+ occurrences).
---

# Usage Patterns

Patterns are updated by `/retrospect` at end of each session.
Format: pattern description | **count** | dates seen | status

---

## Workflow patterns

| Pattern | Count | Dates | Status |
|---------|-------|-------|--------|
| User says "merged" without asking for Railway check — expects it automatically | 3 | 2026-05-13, 2026-05-13, 2026-05-13 | ⚠️ at threshold — CLAUDE.md rule added but not firing reflexively |
| User goes straight to plan doc + "ye" / "continue" — never invokes `/feature` research phase | 2 | 2026-05-13, 2026-05-13 | tracking |
| User says short affirmatives ("ye", "ok continue", "yeah") to proceed — never writes long confirmations | 2 | 2026-05-13, 2026-05-13 | tracking |
| User works step-by-step: implement → merge → confirm Railway → next step | 2 | 2026-05-13, 2026-05-13 | tracking |
| User does not manually test UI — relies on Claude to report frontend correctness | 2 | 2026-05-13, 2026-05-13 | tracking |

## Friction patterns (things that caused extra turns)

| Pattern | Count | Dates | Status |
|---------|-------|-------|--------|
| Claude narrates intent before acting ("I'll now X") — user interrupted or had to read noise | 2 | 2026-05-13, 2026-05-13 | rule added to CLAUDE.md |
| Claude paused mid-task to confirm understanding — user had to say "just do it" | 2 | 2026-05-13, 2026-05-13 | rule added (autonomous mode) |
| Stale feature branch reused from a previous session — caused diagnosis overhead | 1 | 2026-05-13 | tracking |
| Claude said "I can't access X" without checking deferred tools | 2 | 2026-05-13, 2026-05-13 | rule added to CLAUDE.md |
| User scared that plan docs were lost — actually just in docs/plans/ | 1 | 2026-05-13 | tracking |

## Agent/build patterns

| Pattern | Count | Dates | Status |
|---------|-------|-------|--------|
| Build agent takes 12–15 min per step — user doesn't complain but waits | 2 | 2026-05-13, 2026-05-13 | tracking |
| Full `make test` run (~2 min) done by agent even when only a few files changed | 2 | 2026-05-13, 2026-05-13 | tracking |
| User spawns agent with "continue" — expects Claude to know current step from beads/plans | 2 | 2026-05-13, 2026-05-13 | tracking |

## Positive patterns (things that work well — don't break these)

| Pattern | Count | Dates |
|---------|-------|-------|
| User reviews PR on GitHub before merging — never merges without looking | 2 | 2026-05-13, 2026-05-13 |
| User runs `/retrospect` at end of most sessions | 3 | 2026-05-13 x3 |
| Plan docs written once, referenced many sessions later without confusion | 2 | 2026-05-13, 2026-05-13 |
| Short terse responses preferred — user never asks for more explanation | 3 | 2026-05-13 x3 |

---

## Threshold log (patterns that crossed 3+ and triggered a harness change)

| Pattern | Count when actioned | Change made |
|---------|--------------------|----|
| User says "merged" → expects Railway check | 3 | Added rule 13 to CLAUDE.md + Step 14 to /feature SKILL.md |
| Claude narrates intent before acting | 3 | Added "no pre-action narration" rule to CLAUDE.md |
| Claude claims capability unavailable without checking deferred tools | 3 | Added rule 9 to CLAUDE.md |
