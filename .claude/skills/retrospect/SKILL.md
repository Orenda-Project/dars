---
name: retrospect
description: Analyzes the current session and suggests harness improvements to reduce prompts, tokens, and errors.
trigger: /retrospect
---

# /retrospect

Analyzes what happened this session and produces concrete harness improvement suggestions.

## What to analyze

Reflect on the full conversation this session and evaluate against these five priorities (in order):

1. **Prompt count** — could anything have been done with fewer back-and-forth turns? Did Claude ask questions that should have been answerable from existing docs? Did the user need to correct or redirect Claude?
2. **Token efficiency** — were files re-read unnecessarily? Was output verbose where it could be terse? Were parallel reads not used when they could have been?
3. **Correctness** — were there bugs, wrong assumptions, or work that had to be redone?
4. **Architectural drift** — did the session involve rebuilding something that already existed? Did a new module duplicate an existing one? Did the user have to decompose a feature into steps that Claude should have caught? If yes, these are high-priority harness issues — the `/feature` skill's research phase should have caught them.
5. **Workflow gaps** — read `.claude/skills/feature/SKILL.md` Phase 3 steps. For each step, verify it was executed this session. Flag any step that was skipped or only partially done — even if it didn't cause a visible failure. Also check: was Railway deployment verified? Was the bead closed before or after deployment confirmed? Were e2e tests run or explicitly noted as skipped?

## For each issue found

Produce a concrete suggestion in this format:

```
ISSUE: <one-line description of what went wrong>
ROOT CAUSE: <why it happened — missing context, wrong instruction, no hook, etc.>
FIX: <exact change — new skill instruction, hook script, CLAUDE.md line, agent rule, etc.>
PRIORITY: high | medium | low
```

## What to improve

Consider all harness mechanisms:
- **Skills** — new skill, or clarify/tighten instructions in existing skill
- **Hooks** — PreToolUse, PostToolUse, SessionStart, Stop — something that should be automatic
- **CLAUDE.md** — missing rule, wrong rule, or rule that's too vague
- **docs/conventions.md** — missing gotcha that caused a wrong assumption
- **docs/ROADMAP.md** — missing architectural constraint that should have been recorded
- **agents** — subagent definition that would isolate context better
- **.beads/** — workflow gap

**Always check for the rebuild pattern:** if the session ended with a clean-slate rewrite or significant rework, ask: what harness rule, research step, or constraint document would have prevented this? That answer is the highest-priority fix.

Do NOT suggest vague improvements like "be more thorough". Every suggestion must be actionable: a file to edit, a line to add, a hook to write.

## Output

1. Print the suggestions to the conversation
2. Append to `.claude/improvements.md`:

```markdown
---
## <YYYY-MM-DD> Session retrospect

### Issues & suggestions
<paste the ISSUE/ROOT CAUSE/FIX blocks>
```

## Token rules

- Do not summarize the whole session — only surface issues
- If the session was clean (no corrections, no re-reads, no confusion), say so in one sentence and stop
