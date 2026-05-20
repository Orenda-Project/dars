---
name: retrospect
description: Analyzes the current session and suggests harness improvements to reduce prompts, tokens, and errors.
trigger: /retrospect
---

# /retrospect

Analyzes what happened this session and produces concrete harness improvement suggestions.

## Inputs

1. **Conversation transcript** — what the user said, what you replied, what you decided.
2. **Tool-use log** — `.claude/sessions/<session_id>.jsonl`, written by `.claude/hooks/log-tool-use.sh` on every `PostToolUse`. Each line: `{ts, tool, summary, error}`.

Find the current session's log by sorting `.claude/sessions/*.jsonl` by mtime and taking the newest. If no log exists, note that and skip the tool-use sections below.

## Step 1 — Compute tool-use stats

Run a quick aggregation over the JSONL log. Report:

- **Total calls** and **breakdown by tool** (top 5).
- **Re-reads:** files in `Read` entries that appear ≥2× with overlapping ranges. Each repeat is a likely waste.
- **Parallelism gaps:** consecutive runs of the same tool (e.g. 3+ `Bash` calls in a row without an intervening tool) that had no inter-dependency — these should have been a single parallel batch.
- **Error rate:** count of entries with `error: true`.
- **Bash patterns:** count of `cat`/`head`/`tail`/`sed`/`awk` invocations — these should be `Read`/`Edit`. Count `ls`/`find`/`grep` invocations when `graphify-out/` exists — these should be graphify queries.

Print the stats as a compact table at the top of the output. Keep it under 15 lines.

## Step 2 — Detect anti-patterns from the log

For each pattern below, if it triggers, emit an `ISSUE` block (see format in Step 4):

| Pattern | Trigger | Likely fix |
|---------|---------|------------|
| Re-read same file | Same `file_path` Read ≥2× with no Edit between | Cache state in memory; re-read only after Edit/Write |
| Sequential Bash | ≥3 consecutive Bash calls with no cross-dependency | Batch into one parallel message |
| Read-without-Edit cluster | ≥5 Reads with no Edit/Write in window | Exploration scope creep — narrow the task or use Explore agent |
| Raw `cat`/`sed`/`awk` | Bash command starts with these | Use Read/Edit instead |
| Grep/find when graphify exists | `Grep`/`Glob`/`find` calls and `graphify-out/` exists | Use `graphify query` for cross-module questions |
| Bash error spike | `error: true` rate > 20% on Bash | Likely missing context or wrong assumption upstream |

## Step 3 — Reflect on conversation against five priorities

Evaluate against these (in order). Tool-use data feeds priorities 2 and 3 directly.

1. **Prompt count** — could anything have been done with fewer back-and-forth turns? Did Claude ask questions that should have been answerable from existing docs? Did the user need to correct or redirect Claude?
2. **Token efficiency** — were files re-read unnecessarily? Was output verbose where it could be terse? Were parallel reads not used when they could have been? (Cross-check against the tool-use stats from Step 1.)
3. **Correctness** — were there bugs, wrong assumptions, or work that had to be redone?
4. **Architectural drift** — did the session involve rebuilding something that already existed? Did a new module duplicate an existing one? Did the user have to decompose a feature into steps that Claude should have caught? If yes, these are high-priority harness issues — the `/feature` skill's research phase should have caught them.
5. **Workflow gaps** — read `.claude/skills/feature/SKILL.md` Phase 3 steps. For each step, verify it was executed this session. Flag any step that was skipped or only partially done — even if it didn't cause a visible failure. Also check: was Railway deployment verified? Was the bead closed before or after deployment confirmed? Were e2e tests run or explicitly noted as skipped?

## Step 4 — For each issue found

Produce a concrete suggestion in this format:

```
ISSUE: <one-line description of what went wrong>
ROOT CAUSE: <why it happened — missing context, wrong instruction, no hook, etc.>
EVIDENCE: <optional: cite tool-log row count, file path re-read N times, etc.>
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

1. Print the tool-use stats table (Step 1) followed by the ISSUE blocks (Step 4) to the conversation.
2. Append to `.claude/improvements.md`:

```markdown
---
## <YYYY-MM-DD> Session retrospect

### Tool-use stats
<paste the compact table>

### Issues & suggestions
<paste the ISSUE/ROOT CAUSE/EVIDENCE/FIX blocks>
```

## Token rules

- Do not summarize the whole session — only surface issues and the stats table.
- If the session was clean (no corrections, no re-reads, no confusion, low tool-call count), say so in one sentence and stop.
- The tool-use log can be large — process it with a single Bash + python aggregation, don't Read the raw JSONL.
