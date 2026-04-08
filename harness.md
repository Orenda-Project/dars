Context Engineering Harness Bootstrap
For: Any Taleemabad team member setting up Claude Code on their repo
Time: 2–4 hours for a full build, 30 min for a minimal starter
What you get: A self-reinforcing AI development environment that enforces quality, loads context intelligently, tracks work, and improves itself over time.

What you're building and why
A harness is two things working together:

Guides (feedforward): CLAUDE.md files, agents, skills — they steer Claude before it acts
Sensors (feedback): Hooks, tests, validators — they observe after Claude acts and correct mistakes
Without both, you have a style guide that nobody enforces. The CEO OS and Rumi repos work because violations are caught mechanically, not by asking Claude to be disciplined.

The other thing to understand: context is a depletable resource. Every token you load degrades the tokens already there (Stanford's "lost in the middle" finding). The L1→L2→L3 system below is about loading the minimum high-signal context needed for each task — not stuffing everything in upfront.

Before you start — give Claude this entire file
Paste this file into a new Claude Code session in your repo root. Then say:

"Read this file completely. Then audit my repo and build the harness described in it, phase by phase. Ask me before completing each phase."

Claude will follow the phases below and build your harness. You review each phase before it moves on.

Phase 1: Audit (Claude does this first)
Before building anything, Claude should understand what exists. Run:

1. List every file in the repo root
2. List all directories (1 level deep)
3. Find any existing CLAUDE.md files
4. Find any existing .claude/ directories
5. Find any existing README.md files
6. Identify what kind of repo this is (code / docs / mixed)
7. Identify the primary language(s) and frameworks
8. Identify if there's a deployment target (Railway, Vercel, etc.)
Produce a one-page audit summary before touching anything.

Phase 2: Build the CLAUDE.md Hierarchy (L1 → L2 → L3)
This is the progressive disclosure system. Information is layered so Claude loads only what it needs.

The L1/L2/L3 contract
Level	What lives here	Line limit	When loaded
L1	CLAUDE.md — navigation only, critical rules, pointers	≤150 lines	Always, every session
L2	README.md per folder, SKILL.md per skill	≤100 lines	When a task matches that domain
L3	Actual docs, runbooks, references, plans	≤300 lines per file	Only when blocked without it
L4	Archives, changelogs, full transcripts	Unlimited	On-demand, load by section only
Hard rule: L1 contains zero substantive content. It is a routing table, nothing else.

L1: Root CLAUDE.md template
# [Project Name] — Claude Operating Manual

**Owner:** [Your name]  
**Purpose:** [One sentence]

---

## Quick Navigation

| Looking for... | Go to... |
|----------------|----------|
| How to deploy | `docs/deployment.md` |
| Database schema | `docs/schema.md` |
| API credentials | `.env` + `docs/credentials.md` |
| Active work | `.beads/status.jsonl` |
| Agent list | `.claude/agents/` |

---

## Folder Structure

| Folder | Contents |
|--------|----------|
| `src/` | Application code |
| `docs/` | Reference documentation |
| `.claude/` | Agents, skills, hooks, standards |
| `.beads/` | Work tracking |

---

## Agents

| Agent | Purpose |
|-------|---------|
| `docs-updater` | Update docs after code changes |
| `debugger` | Investigate errors from logs |

---

## Skills

| Skill | Invoke | Purpose |
|-------|--------|---------|
| `deploy` | `/deploy` | Deployment operations |
| `debug` | `/debug` | Log analysis and tracing |

---

## Critical Rules

1. **Never deploy with `railway up`** — use `git push` only (auto-deploy is wired)
2. **Never hardcode credentials** — read from `.env`; put path in `docs/credentials.md`  
3. **Every task gets a bead** — open a bead before starting, close it when done
4. **CLAUDE.md stays under 150 lines** — route detail to L2/L3, never dump it here
5. **Verify don't assume** — after deploy, hit the health endpoint; don't say "should work"

---

## Development Cycle (mandatory for all code work)

INVESTIGATE → Read all code in the execution path. Write findings.
PLAN → List files to change, edge cases, what NOT to touch.
RED TEAM → What could go wrong? Race conditions? Schema deps?
PRE-DEPLOY → Apply DB migrations, set env vars BEFORE pushing code.
TEST → Write test → confirm FAIL → implement → confirm PASS.
DEPLOY → git push. Wait for health endpoint to reset.
VERIFY → Health check + logs + functional test. Not assumed state.
CLOSE OUT → Update bead, update docs, log failures if any.

L2: Folder README template
Each major folder gets a README.md that routes to L3 docs:

# [Folder Name]

**Purpose:** One sentence.

## Key Documents

| Document | What it answers |
|----------|----------------|
| [deployment.md](deployment.md) | How to deploy to each environment |
| [schema.md](schema.md) | Database tables and relationships |
| [credentials.md](credentials.md) | Where credentials live, how to rotate |

## Active Work

See `.beads/status.jsonl` for open tasks in this area.
L3: Document types and frontmatter
Every L3 doc (and every L2 README) must have YAML frontmatter at the very top. This is what the validate-after-write.sh hook enforces. Without it, Claude has no way to know what a document is, how fresh it is, or when to load it.

Minimum required frontmatter:

---
type: router | runbook | reference | investigation | plan | changelog
last_verified: YYYY-MM-DD
owner: your-name
---
Full frontmatter (use these fields when relevant):

---
type: reference
last_verified: 2026-04-03
owner: sabeena
status: active
related_beads: ["bd-012", "bd-015"]
parent: docs/README.md
---
Field	Required	Purpose
type	✓	Controls line limits and load behavior (see table below)
last_verified	✓	Date the content was last checked for accuracy
owner	✓	Person or agent responsible for keeping it fresh
status	—	active | archived — for investigations and plans only
related_beads	—	Bead IDs this doc was created to support
parent	—	The L2 router that links to this doc
Document types in detail
Each type has a job and a line limit. The limits are not arbitrary — they exist because Claude's performance degrades as context grows. A 600-line reference doc loaded alongside 3 others fills the working context before the task is done.

router — Navigation only. Contains links, one-line descriptions, and nothing else. No content. Think of it as a table of contents file. - Line limit: 100 - Load behavior: Always safe to load (it's small and contains no stale facts) - Examples: CLAUDE.md, all README.md files, docs/index.md - What NOT to put in it: procedures, credentials, code snippets, explanations longer than one sentence

---
type: router
last_verified: 2026-04-03
owner: haroon
---

# Docs

| Document | What it answers |
|----------|----------------|
| [deployment.md](deployment.md) | How to deploy to each environment |
| [schema.md](schema.md) | Database tables and column types |
| [credentials.md](credentials.md) | Where credentials live, how to rotate |
runbook — Step-by-step procedures. Each step is an action, not a description. Someone should be able to execute a runbook without reading anything else. - Line limit: 200 - Load behavior: Load when executing that specific procedure - Examples: deployment.md, db-migration.md, rollback-procedure.md - What NOT to put in it: background context, design rationale, architecture explanations (those go in reference)

```markdown
type: runbook last_verified: 2026-04-03

owner: sabeena
Deploy to Staging
Prerequisites
[ ] Smoke tests passing: bash .claude/scripts/smoke-test.sh
[ ] Open bead for this deploy: bd-XXX
Steps
Push to staging branch: bash git push origin staging

Wait for health endpoint to reset (~2 min): bash watch -n 15 "curl -s https://your-app-staging.up.railway.app/health | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get(\"uptime\"))'"

Verify logs clean: bash railway logs --lines 30

Close deploy bead with commit hash as resolution. ```

reference — Stable lookup information. Doesn't change often. Loaded when Claude needs to know something factual about the system (schema, credentials location, API endpoints, environment variables). - Line limit: 300 - Load behavior: Load when the domain is active this session - Examples: schema.md, credentials.md, environment-variables.md, api-endpoints.md - What NOT to put in it: procedures, history, current investigations

---
type: reference
last_verified: 2026-04-03
owner: haroon
---

# Database Schema

## evaluations

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | UUID | No | Primary key, auto-generated |
| agent_id | VARCHAR | No | Which agent submitted |
| session_id | VARCHAR | No | Coaching session being evaluated |
| overall_score | FLOAT | Yes | 0–100, null until evaluated |
| compliance_tier | VARCHAR | Yes | pass \| partial \| fail |

## standard_results

Foreign key: `evaluation_id → evaluations.id` (cascades on delete)

| Column | Type | Notes |
|--------|------|-------|
| standard_id | VARCHAR | e.g. "T3", "P1" |
| compliance_status | VARCHAR | met \| partial \| not_met \| not_evaluated |
| score | FLOAT | 0–100 |
investigation — Active analysis with findings. Created when debugging a problem or doing a deep dive. Has a clear start, findings section, and conclusion. Time-bound — investigations become archived once the problem is resolved. - Line limit: 300 (split if longer; rarely needed) - Load behavior: Load when actively working on that specific problem - status field is mandatory: active while open, archived when resolved - Examples: reports/active/INVESTIGATION.md, reports/active/rca-email-failure.md

---
type: investigation
last_verified: 2026-04-03
owner: claude
status: active
related_beads: ["bd-023"]
---

# Investigation: T2 Latency Check False Failures

## Problem
Submissions with 7-minute processing times are failing the T2 SLA check (≤10 min).

## Hypothesis
The `processing_time_minutes` field in the submission is recording wall-clock time
including the Kie.ai polling loop, not just the coaching session processing time.

## Findings
- Checked 5 failing submissions: all had processing_time between 9.8–10.4 min
- The extra 0.4 min is the Kie.ai API polling overhead (5 × 10s polls)
- SLA spec says "processing time for observation analysis", not total round-trip

## Resolution
[pending — update when fix is deployed]
plan — Proposed approach with decisions. Created before starting a non-trivial implementation. Contains the design, trade-offs considered, and open questions. Unlike investigations, plans are forward-looking. - Line limit: None (plans need room to think) - Load behavior: Load when planning or reviewing a design - status field: active while being executed, archived when done

---
type: plan
last_verified: 2026-04-03
owner: sabeena
status: active
related_beads: ["bd-031"]
---

# Plan: Lesson Plans Evaluator (V1)

## Goal
Copy the Digital Coach evaluator pattern and adapt it for Lesson Plans standards.

## Files to create
- `01-our-data-intelligence-system/evaluator/` (copy evaluator/ folder)
- Change standards.py to LP standards subset from the Google Sheet
- Add LP-specific check functions in evaluator.py

## Standards to implement (LP column from framework)
- P5 ● (required), P2 ● (required), P3 ● (required), P1 ● (required)
- T10 ● T2 ● X1 ● P4 ● T1 ● T8 ● T6 ● T9 ● X5 ● X3 ● X8 ● X2 ● X4 ● X10 ● X7 ●

## What NOT to change
- models.py — schema is service-agnostic, reuse as-is
- Hook configuration — no changes needed
- requirements.txt — same dependencies

## Open questions
- Should LP evaluator share a database with Digital Coach, or separate db files?
  Current lean: separate files per service, merge if reporting needs it
changelog — Version history. Append-only. Load by version section only — never load the full file. - Line limit: None (it grows forever) - Load behavior: Load only the specific version section needed - Examples: docs/changelog.md, CHANGELOG.md

---
type: changelog
last_verified: 2026-04-03
owner: claude
---

# Changelog

## v1.1.0 — 2026-04-03
- Added P2 (Prerequisite Sequencing) check to Digital Coach evaluator
- Fixed T2 threshold to measure processing time only (not total wall-clock)
- Deployed: commit 91a3bc2

## v1.0.0 — 2026-04-03
- Initial Digital Coach evaluator with 10 standard checks
- FastAPI app, SQLite storage, example submission
- Deployed: commit acb0556
Splitting documents that exceed limits
When a document hits its limit, split it — don't expand it.

Pattern:

docs/schema.md          ← original, now a router
docs/schema-tables.md   ← tables and columns (reference, 300 lines)
docs/schema-indexes.md  ← indexes and constraints (reference, 100 lines)
The router (schema.md) becomes:

---
type: router
last_verified: 2026-04-03
owner: sabeena
---

# Schema

| Document | Contents |
|----------|---------|
| [schema-tables.md](schema-tables.md) | All tables, columns, types, nullability |
| [schema-indexes.md](schema-indexes.md) | Indexes, constraints, foreign keys |
Never have a 600-line reference doc. Split first, route through an index.

Phase 3: Set up Agents and Skills
Agents and skills are not the same thing.

Agents (.claude/agents/[name].md)
Autonomous, multi-step orchestrators. An agent can run for an hour, manage a complex task end to end, track its own state, and update beads. Use agents when a task requires judgment, multiple tools, and sequential steps.

Every agent file must include: 1. What it does — one paragraph 2. When to invoke it — trigger conditions (explicit / proactive / scheduled) 3. What it reads — which L2/L3 docs to load 4. What it produces — outputs, side effects 5. Session End Protocol — what to do before stopping (close beads, update docs) 6. Self-Improvement Log — learnings recorded mid-stream (dated entries)

---
name: docs-updater
description: Updates documentation after code changes. Invoke after any deploy or bug fix.
trigger: reactive
cost: low
---

# docs-updater

Updates all documentation impacted by the current code change.

## When to invoke
- After any feature deployment
- After any bug fix
- When user says "update the docs"

## What to read
1. Check which files were changed this session (git diff)
2. Load the relevant L2/L3 docs for those areas
3. Load `.claude/standards/DOC_TYPE_SYSTEM.md`

## What to produce
- Updated L3 docs (never update CLAUDE.md with content — only pointer updates)
- New investigation doc if debugging session produced findings
- Changelog entry in `docs/changelog.md`

## Session End Protocol
1. Close any beads opened this session
2. Verify updated docs are under line limits
3. Commit changes with descriptive message

## Self-Improvement Log
<!-- Append dated learnings here as you discover them -->
Skills (.claude/skills/[name]/SKILL.md)
Static knowledge libraries. A skill is loaded when domain knowledge is needed — API patterns, credentials, tool syntax, workflow steps. Skills don't take autonomous actions; they inform Claude how to perform specific operations.

Every skill file must include: 1. What domain it covers — one sentence 2. Authentication — exactly how to authenticate (credentials location, scopes) 3. Core patterns — the 3-5 most-used operations with working code 4. Known issues — gotchas, version incompatibilities, errors you've hit 5. Learnings log — session-end hook updates this automatically

```markdown
name: deploy

description: Deployment operations for Railway. Invoke with /deploy.
Deploy Skill
Handles all deployment operations to Railway environments.

Authentication
Railway token: .env → RAILWAY_TOKEN Project ID: .env → RAILWAY_PROJECT_ID

Core Patterns
Deploy to staging
git push origin staging
# Railway auto-deploys. Wait for health endpoint to reset (~2-3 min).
Check deployment status
railway status --service [service-name]
Verify deploy succeeded
curl -s https://[your-app].up.railway.app/health | python3 -c "import json,sys; d=json.load(sys.stdin); print('uptime:', d.get('uptime'))"
Known Issues
Never use railway up — bypasses branch→service mapping, can deploy staging to prod
Health endpoint may take 90s to reset after deploy — poll every 15s, don't assume
Learnings Log
<!-- Updated by session-end hook -->
```

Invocation modes
Mode	Behavior
auto	Claude loads this without being asked (e.g., every session)
manual	Only loaded when user explicitly invokes /skill-name
suggest	Claude mentions it but doesn't load unless user confirms
Set mode in the agent or skill frontmatter: trigger: auto | manual | suggest

Phase 4: Wire up Hooks
This is what makes the harness mechanical. Hooks enforce rules so Claude doesn't have to be disciplined — violations are blocked automatically.

Hook fundamentals
Hooks fire at lifecycle events and communicate through exit codes: - Exit 0: Allow the action (silent success) - Exit 2: Block the action. Stderr is shown to Claude as an error. Claude must fix the problem before retrying.

Key rule: hooks should be silent on success, loud on failure. Every message a passing hook sends pollutes the context window.

Create .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/block-bad-commands.sh\"",
            "timeout": 3000
          }
        ]
      },
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/guard-file-writes.sh\"",
            "timeout": 3000
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/validate-after-write.sh\"",
            "timeout": 5000
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh\"",
            "timeout": 5000
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/session-end.sh\"",
            "timeout": 30000
          }
        ]
      }
    ]
  }
}
Hook 1: Block bad commands (PreToolUse / Bash)
.claude/hooks/block-bad-commands.sh:

#!/bin/bash
# Reads the bash command from stdin (JSON)
COMMAND=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))" 2>/dev/null)

# Block railway up — use git push instead
if echo "$COMMAND" | grep -qE "railway\s+up\b"; then
  echo "ERROR: 'railway up' is blocked. Use 'git push origin [branch]' instead." >&2
  echo "Railway auto-deploys from git push. 'railway up' bypasses branch→service mapping." >&2
  exit 2
fi

# Block force push to main without warning
if echo "$COMMAND" | grep -qE "git push.*--force.*main|git push.*-f.*main"; then
  echo "ERROR: Force push to main is blocked. Use a PR or ask the repo owner." >&2
  exit 2
fi

# Block committing .env files
if echo "$COMMAND" | grep -qE "git add.*\.env|git commit.*\.env"; then
  echo "ERROR: Attempting to commit .env file. Credentials must never be committed." >&2
  exit 2
fi

exit 0
Hook 2: Guard file writes (PreToolUse / Write|Edit)
.claude/hooks/guard-file-writes.sh:

#!/bin/bash
FILEPATH=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null)

# Block writing to .env directly (read from it, don't overwrite it carelessly)
if echo "$FILEPATH" | grep -qE "^\.env$|/\.env$"; then
  echo "WARNING: Writing to .env. Verify you are not overwriting existing credentials." >&2
  # Don't block (exit 0) but warn — this is a soft guard
fi

# Check CLAUDE.md line count if being edited
if echo "$FILEPATH" | grep -qE "CLAUDE\.md$"; then
  if [ -f "$FILEPATH" ]; then
    LINES=$(wc -l < "$FILEPATH")
    if [ "$LINES" -gt 195 ]; then
      echo "ERROR: CLAUDE.md has $LINES lines (limit: 150). Move content to L2/L3 docs first." >&2
      exit 2
    fi
  fi
fi

exit 0
Hook 3: Validate after write (PostToolUse / Write|Edit)
.claude/hooks/validate-after-write.sh:

#!/bin/bash
FILEPATH=$(echo "$CLAUDE_TOOL_OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null)

# Syntax check Python files
if echo "$FILEPATH" | grep -qE "\.py$"; then
  if ! python3 -m py_compile "$FILEPATH" 2>/tmp/syntax-error; then
    echo "ERROR: Python syntax error in $FILEPATH:" >&2
    cat /tmp/syntax-error >&2
    exit 2
  fi
fi

# Check for missing doc headers on markdown files
if echo "$FILEPATH" | grep -qE "\.md$" && ! echo "$FILEPATH" | grep -qE "CLAUDE\.md$"; then
  if ! head -5 "$FILEPATH" | grep -q "^---"; then
    echo "WARNING: $FILEPATH is missing YAML frontmatter (type, last_verified, owner)." >&2
  fi
fi

exit 0
Hook 4: Session start (SessionStart)
.claude/hooks/session-start.sh:

#!/bin/bash
# Inject useful context at the start of every session

echo "=== SESSION START ==="

# Show open beads (active work)
if [ -f ".beads/status.jsonl" ]; then
  OPEN=$(grep '"status":"open"' .beads/status.jsonl 2>/dev/null | tail -10)
  if [ -n "$OPEN" ]; then
    echo "OPEN BEADS (active work):"
    echo "$OPEN" | python3 -c "
import json,sys
for line in sys.stdin:
    try:
        d = json.loads(line)
        print(f\"  [{d.get('priority','?')}] {d.get('id','?')}: {d.get('title','?')}\")
    except: pass
"
  else
    echo "No open beads."
  fi
fi

# Check for stale CLAUDE.md
if [ -f "CLAUDE.md" ]; then
  LINES=$(wc -l < CLAUDE.md)
  if [ "$LINES" -gt 150 ]; then
    echo "WARNING: CLAUDE.md has $LINES lines (target: <150). Consider trimming."
  fi
fi

echo "====================="
exit 0
Hook 5: Session end (Stop)
.claude/hooks/session-end.sh:

#!/bin/bash
echo "=== SESSION END CHECK ==="

# Check for unclosed beads
if [ -f ".beads/status.jsonl" ]; then
  OPEN_COUNT=$(grep -c '"status":"open"' .beads/status.jsonl 2>/dev/null || echo 0)
  if [ "$OPEN_COUNT" -gt 0 ]; then
    echo "REMINDER: $OPEN_COUNT open bead(s). Update status before closing if work is done."
  fi
fi

# Check for unstaged changes
UNSTAGED=$(git diff --stat 2>/dev/null | tail -1)
if [ -n "$UNSTAGED" ]; then
  echo "REMINDER: Unstaged changes exist. Commit or stash before closing."
fi

# Check for bloated CLAUDE.md
if [ -f "CLAUDE.md" ]; then
  LINES=$(wc -l < CLAUDE.md)
  if [ "$LINES" -gt 150 ]; then
    echo "WARNING: CLAUDE.md is $LINES lines. Trim it before next session."
  fi
fi

echo "========================"
exit 0
Phase 5: Beads (work tracking)
Beads are your issue tracker, baked into the repo as append-only JSONL files. They exist for one reason: Claude Code sessions have no persistent memory across context resets. If you're midway through a bug fix and the context window fills up, the next session has no idea what you were doing. Beads are what survives.

The session-start hook injects open beads at the top of every session. Claude reads them, understands what's in flight, and continues without you repeating yourself.

The three bead files
.beads/
├── status.jsonl     — all tasks: open, in_progress, closed
├── decisions.jsonl  — architectural decisions and their rationale
├── failures.jsonl   — production incidents, bugs, lessons
└── README.md        — how beads work (for humans and Claude)
All three are append-only. Never edit a previous line — add a new one. This is deliberate: the history is the value.

.beads/status.jsonl — full schema
Every line (after the schema line) is a bead. Fields:

Field	Type	Required	Values
id	string	✓	bd-001, bd-002, ... (sequential, never reuse)
title	string	✓	Short imperative: "Fix T2 threshold bug"
status	string	✓	open | in_progress | closed | blocked
priority	string	✓	critical | high | medium | low
created	string	✓	ISO date: "2026-04-03"
updated	string	✓	ISO date of last change
category	string	✓	bug | feature | docs | infrastructure | agent | refactor
resolution	string|null	✓	null when open; commit hash or description when closed
blocked_by	string|null	—	"bd-012" if blocked by another bead
owner	string	—	"claude" or a person's name
related_files	array	—	["src/evaluator.py", "main.py"]
Bootstrap file — create this first:

{"schema": "v1", "fields": ["id","title","status","priority","created","updated","category","resolution","blocked_by","owner"]}
{"id": "bd-001", "title": "Bootstrap repo harness", "status": "in_progress", "priority": "high", "created": "2026-04-03", "updated": "2026-04-03", "category": "infrastructure", "resolution": null, "blocked_by": null, "owner": "claude"}
The bead lifecycle
Every piece of work follows this lifecycle — no exceptions:

Task identified
      ↓
Open bead (status: "open")     ← do this BEFORE touching any code
      ↓
Start work
      ↓
Update to in_progress           ← when you actually start
      ↓
Hit a blocker?
  YES → set status: "blocked", blocked_by: "bd-XXX" or describe in title
  NO  → continue
      ↓
Work complete
      ↓
Close bead (status: "closed", resolution: "commit abc123 / what was done")
When to open a bead: - Discovering a bug → open a bead immediately, before investigating - Starting a feature → open a bead, then plan - Writing documentation → open a bead - Setting up the harness → bd-001 is already there

When NOT to open a bead: - One-line fixes that are trivially reversible (change a config value, update a comment) - Read-only work (research, reading logs) - Anything that takes under 5 minutes and has no side effects

Closing a bead — the resolution field is critical:

{"id": "bd-001", "title": "Bootstrap repo harness", "status": "closed", "priority": "high", "created": "2026-04-03", "updated": "2026-04-03", "category": "infrastructure", "resolution": "Completed harness build: CLAUDE.md hierarchy, 5 hooks, standards docs, beads. Commit 862fab3.", "blocked_by": null, "owner": "claude"}
The resolution should answer: what was done, and how would someone verify it?

Querying beads (Claude does this, but you can too)
Because beads are JSONL, they're trivially queryable:

# Show all open beads
grep '"status":"open"' .beads/status.jsonl | python3 -c "
import json, sys
for line in sys.stdin:
    d = json.loads(line)
    print(f\"[{d['priority'].upper()}] {d['id']}: {d['title']}\")
"

# Show blocked beads
grep '"status":"blocked"' .beads/status.jsonl

# Show all bugs
grep '"category":"bug"' .beads/status.jsonl | grep '"status":"open"'

# Count open by priority
grep '"status":"open"' .beads/status.jsonl | python3 -c "
import json, sys, collections
counts = collections.Counter()
for line in sys.stdin:
    try: counts[json.loads(line)['priority']] += 1
    except: pass
for p, n in counts.most_common(): print(f'{p}: {n}')
"
The session-start hook runs a version of the first query and injects the results into every session. That's the memory that survives context resets.

Quarterly archive
Every three months, move closed beads older than 90 days to history:

# Run this manually or add to a scheduled agent
python3 -c "
import json
from datetime import date, timedelta

cutoff = (date.today() - timedelta(days=90)).isoformat()
active, archive = [], []

with open('.beads/status.jsonl') as f:
    for line in f:
        try:
            d = json.loads(line)
            if d.get('status') == 'closed' and d.get('updated', '') < cutoff:
                archive.append(line)
            else:
                active.append(line)
        except:
            active.append(line)  # keep schema line and malformed lines

with open('.beads/status.jsonl', 'w') as f:
    f.writelines(active)

with open('.beads/history.jsonl', 'a') as f:
    f.writelines(archive)

print(f'Archived {len(archive)} beads.')
"
.beads/decisions.jsonl — architectural decisions
Every non-obvious technical decision gets recorded here. Not "I chose Python over Bash for a script" — that's obvious. Yes to "I chose SQLite over Postgres for V1 because the evaluator has no concurrent writes and we don't want Railway infrastructure yet."

The test: could a new engineer (or Claude next month) reconstruct the reasoning from this entry alone?

Full schema:

Field	Purpose
date	When the decision was made
decision	One-sentence summary of what was decided
rationale	Why — the constraint, deadline, or trade-off that drove it
alternatives	What else was considered and why rejected
revisit_when	Optional: conditions under which to revisit (e.g., "when we have >1 concurrent user")
{"date": "2026-04-03", "decision": "SQLite for V1 evaluator storage", "rationale": "Zero infrastructure overhead; evaluations.db lives next to the app. ORM (SQLAlchemy) is database-agnostic so swap to Postgres is a config change.", "alternatives": ["Postgres on Railway — overkill for V1, adds infra to manage", "Flat JSON files — no query capability, no relationships"], "revisit_when": "When evaluator needs multi-user concurrent writes or remote access"}
{"date": "2026-04-03", "decision": "FastAPI over Flask for evaluator API", "rationale": "Auto-generated /docs (Swagger UI) means Sabeena can test without writing curl commands. Critical for learning.", "alternatives": ["Flask — less boilerplate but no auto-docs", "Django — overkill, we don't need ORM bundled in the web layer"], "revisit_when": "Never — this is a permanent choice for internal tools"}
.beads/failures.jsonl — production incidents and lessons
This is the most valuable file in the system. Every bug that caused an incident, every assumption that turned out wrong, every deployment that broke something — goes here, immediately after the fix.

The Rumi repo has entries like em-125 (hallucinated meeting notes) and em-126 (quadruple emails) that became the reason for specific rules in the development methodology. Those rules exist because the failures are documented.

Full schema:

Field	Purpose
date	When it happened
incident	What the user/system experienced
root_cause	The actual technical cause (not the symptom)
fix	What was done to resolve it
lesson	The rule or pattern change that prevents recurrence
related_bead	The bead ID for this fix, if one was opened
{"date": "2026-04-03", "incident": "Kie.ai slide generation silently failed — all 6 slides returned no output", "root_cause": "Payload used 'prompt' key at top level. Correct format wraps in 'input': {'prompt': ...}. API returned 422 with 'input cannot be null' but error was not surfaced in the polling loop.", "fix": "Rewrapped payload in 'input' object. Added response logging to create_task().", "lesson": "Always log the raw API response on task creation, not just the task_id. Silent 422s are worse than loud 500s.", "related_bead": null}
{"date": "2026-04-03", "incident": "Google Doc creation failed with 403 'caller does not have permission'", "root_cause": "Service account used 'spreadsheets' scope for Docs API. DWD in hellorumi.ai workspace only authorizes 'drive' scope, which covers Docs/Sheets/Slides. Individual API scopes fail.", "fix": "Changed SCOPES to ['https://www.googleapis.com/auth/drive']. All GWS APIs work through Drive scope.", "lesson": "DWD authorization is per-scope, not per-API. Check the workspace admin's DWD scope list before writing code. Drive scope is the master key for GWS.", "related_bead": null}
.beads/README.md — for humans and Claude
Create this so anyone who opens the folder understands what they're looking at:

---
type: reference
last_verified: 2026-04-03
owner: you
---

# Beads — Work Tracking

Append-only JSONL issue tracker. Three files:

| File | Purpose |
|------|---------|
| `status.jsonl` | All tasks (open, in_progress, closed, blocked) |
| `decisions.jsonl` | Architectural decisions and rationale |
| `failures.jsonl` | Production incidents and lessons |
| `history.jsonl` | Archived closed beads (>90 days old) |

## Rules

- Append only — never edit a previous line
- Open a bead before touching code, close it after verifying the fix
- Resolution field must answer: what was done and how to verify it
- Archive quarterly (see HARNESS_BOOTSTRAP.md Phase 5 for script)

## Querying

All files are JSONL — query with grep or python3:

    grep '"status":"open"' status.jsonl          # all open work
    grep '"category":"bug"' status.jsonl          # all bugs ever
    grep '"priority":"critical"' status.jsonl     # critical items

## Why this exists

Claude Code has no persistent memory across context resets.
The session-start hook reads the last 10 open beads and injects them
into every session. This is how work-in-progress survives a context window fill.
Phase 6: Standards documents
Create four policy documents in .claude/standards/. These are the governance layer — they tell Claude how to behave across all sessions.

.claude/standards/DOC_TYPE_SYSTEM.md
---
type: reference
last_verified: [DATE]
---

# Document Type System

Every document in this repo belongs to one type. Type determines line limits and load behavior.

| Type | Purpose | Line limit | Load behavior |
|------|---------|-----------|---------------|
| router | Navigation only — links, no content | 100 | Always safe to load |
| runbook | Step-by-step procedures | 200 | Load when executing that procedure |
| reference | Stable lookup information | 300 | Load when that domain is active |
| investigation | Active analysis, time-bound | 300 | Load when debugging |
| plan | Proposed approach, decisions | Unlimited | Load when planning |
| changelog | Version history | Unlimited | Load by section only |

**Enforcement:** Every markdown file must have YAML frontmatter with `type:` and `last_verified:`.
.claude/standards/INVOCATION_POLICY.md
---
type: reference
last_verified: [DATE]
---

# Invocation Policy

Defines when each agent and skill is loaded.

## Agents

| Agent | Trigger | Invocation |
|-------|---------|-----------|
| docs-updater | After any code change | Reactive (user or post-deploy) |
| debugger | When errors appear in logs | Proactive |

## Skills

| Skill | Command | When |
|-------|---------|------|
| deploy | /deploy | Before any push to staging/main |
| debug | /debug | When investigating errors |

## Cost tiers
- **Low:** Fast, routine work — haiku model preferred
- **Medium:** Standard complexity — sonnet model
- **High:** Deep analysis — opus model, use sparingly
.claude/standards/RETRIEVAL_POLICY.md
---
type: reference
last_verified: [DATE]
---

# Retrieval Policy

What gets loaded when. Follow this to avoid context pollution.

## L1 (always, every session)
- CLAUDE.md
- Open beads from `.beads/status.jsonl` (last 10)

## L2 (load one, based on task type)
- Code work → `src/README.md`
- Deployment → `docs/deployment.md`
- Debugging → `docs/troubleshooting.md`
- Database → `docs/schema.md`

## L3 (load only when blocked)
- Load the specific doc that unblocks the task
- Max 2-3 L3 docs per session
- Never load full changelog — find the relevant version section

## Never auto-load
- Archives
- Full changelogs
- Completed investigations
- Historical reports
.claude/standards/METADATA_CONTRACT.md
```markdown
type: reference

last_verified: [DATE]
Metadata Contract
Every markdown file (except CLAUDE.md) must have this frontmatter:

---
type: router|runbook|reference|investigation|plan|changelog
last_verified: YYYY-MM-DD
owner: your-name
---
Freshness SLOs
Doc type	Max staleness
CLAUDE.md	2 weeks
Routers (README.md)	1 month
Core reference docs	2 months
Agent/skill files	2 months
Changelogs	No SLO (append-only)
When last_verified exceeds SLO, add it to a bead. ```

Phase 7: QA enforcement
Your hooks are the foundation. Now layer in actual quality checks.

Minimum viable QA setup
Syntax check on every Python/JS write — already in hook 3 above
One smoke test script that Claude can run before pushing:
# .claude/scripts/smoke-test.sh
#!/bin/bash
echo "Running smoke tests..."

# 1. Import check (Python)
if ls src/*.py &>/dev/null; then
  for f in src/*.py; do
    python3 -m py_compile "$f" || { echo "FAIL: $f has syntax errors"; exit 1; }
  done
  echo "✓ Python syntax OK"
fi

# 2. Critical file check
for f in CLAUDE.md .env; do
  [ -f "$f" ] || { echo "FAIL: Missing $f"; exit 1; }
done
echo "✓ Critical files present"

# 3. CLAUDE.md line count
LINES=$(wc -l < CLAUDE.md)
[ "$LINES" -le 150 ] || { echo "FAIL: CLAUDE.md has $LINES lines (max 150)"; exit 1; }
echo "✓ CLAUDE.md line count OK ($LINES)"

echo "All smoke tests passed."
exit 0
Add pre-push QA hook that requires smoke tests to pass:
# Add to block-bad-commands.sh
if echo "$COMMAND" | grep -qE "git push"; then
  if ! bash "$CLAUDE_PROJECT_DIR/.claude/scripts/smoke-test.sh" &>/dev/null; then
    echo "ERROR: Smoke tests failed. Run '.claude/scripts/smoke-test.sh' to see errors." >&2
    exit 2
  fi
fi
Phase 8: Verify the harness works
After all phases are complete, Claude should run this checklist:

□ CLAUDE.md exists at repo root and is under 150 lines
□ CLAUDE.md contains only routing tables and critical rules — no content
□ At least one L2 README.md exists (in a major folder)
□ At least one L3 reference doc exists with YAML frontmatter
□ .claude/settings.json exists with at least PreToolUse and Stop hooks
□ .claude/hooks/ directory has all 5 hook scripts, each chmod +x
□ .beads/status.jsonl exists with schema line
□ .beads/decisions.jsonl exists
□ .beads/failures.jsonl exists
□ .claude/standards/ has all 4 policy docs
□ .claude/agents/ has at least one agent file with Session End Protocol
□ .claude/skills/ has at least one skill file
□ Smoke test script runs and passes: bash .claude/scripts/smoke-test.sh
□ Hook triggers correctly: try editing CLAUDE.md with >150 lines — it should block
Phase 9: Eval Harness — measuring whether your docs actually work
The eval harness is how you know your documentation system is doing its job. It's borrowed directly from the Rumi repo (.claude/evals/EVAL_HARNESS.md).

The core problem it solves: you can write perfect documentation and still have Claude load the wrong file, load too many files, or take 4 hops to find something that should be 1 hop away. Without evals, you only discover this when a session goes wrong. With evals, you catch it before it costs you.

What an eval measures
Each eval is a test case: a user question, the doc Claude should load, the docs it should NOT load, and the maximum number of hops allowed to get there.

Hops = the number of files Claude loads before reaching the answer. The target is ≤2: - Hop 1: CLAUDE.md (L1) → identifies the right L2 router - Hop 2: the L2 router → points to the correct L3 doc

If Claude needs 3+ hops, your routing is broken. Either the L1 doesn't clearly point to the right L2, or the L2 doesn't clearly point to the right L3. Fix the router, not the destination.

Eval task format
Create .claude/evals/tasks/eval-NNN-description.yaml for each test case:

id: eval-001
description: "Find DB credentials"
category: explicit       # explicit | implicit | contextual | negative
input: "Where are the database credentials?"
expected:
  route: "docs/credentials.md"
  must_load: ["credentials.md"]
  must_not_load: ["changelog.md", "schema.md"]
  max_hops: 1
graders:
  - type: deterministic
    check: route_matches       # did agent load the expected route?
  - type: deterministic
    check: no_forbidden_loads  # did agent avoid the must_not_load list?
  - type: llm_judge
    rubric: "Does the response provide actual database connection details from the canonical credential source, not a pointer to find them elsewhere?"
    threshold: 4               # 1-5 scale; 4 means "good, minor gaps allowed"
quality_gate: PASS             # PASS | CONCERNS | REWORK | FAIL
Category types: | Category | What it tests | |----------|--------------| | explicit | User names the thing they want ("how do I deploy?") | | implicit | User describes a symptom ("the bot is stuck") — Claude must infer the domain | | contextual | Task requires combining two docs ("prepare staging→prod deploy") | | negative | Tests that Claude doesn't load things it shouldn't (forbidden loads) |

A good eval suite has all four. Explicit tests are easy to pass. Implicit and contextual tests are where routing actually breaks.

Three grader tiers
Tier 1: Deterministic (free, instant) — run on every session, no LLM needed

# .claude/evals/graders/run-tier1.sh
# Checks structural health: do all referenced paths exist? Are docs within size limits?
# Are cross-references valid? Are freshness SLOs met?
bash .claude/evals/graders/run-tier1.sh
What it checks: - All route paths in eval tasks actually exist as files - Every doc referenced in must_load lists exists - All markdown docs are within their type's line limit - All docs have YAML frontmatter with type and last_verified - last_verified is within the freshness SLO for that doc type - Cross-references (links between docs) resolve

Tier 2: LLM-as-judge (~$0.02/eval, run before pushing to main) — Claude scores each answer 1–5 against the rubric

The rubric in each eval is deliberately specific. Not "is this a good answer?" but "does this answer include the specific Railway deployment steps including environment checks and staging→main merge?" Generic rubrics produce meaningless scores.

Scoring scale: | Score | Meaning | |-------|---------| | 5 | Perfect — exactly the right doc, exact right answer, no waste | | 4 | Good — right doc, minor gaps or small amount of unnecessary context | | 3 | Acceptable — partially right, would still help the user | | 2 | Poor — wrong route or missing critical info | | 1 | Fail — blocked, wrong answer, or critical doc missing |

Threshold is per-eval: simple explicit tasks should score 4+. Implicit and contextual tasks can have threshold 3 if the domain is genuinely ambiguous.

Tier 3: Quality gate (manual, before major changes) — review the scores and decide

Gate	Definition	Action
PASS	Correct doc(s) loaded, answer accurate, no waste	None
CONCERNS	Right answer but unnecessary docs loaded, or minor gaps	Log and monitor
REWORK	Wrong route, retrieval waste, or partial answer	Fix the router or doc
FAIL	Blocked, wrong answer, or critical doc not found	Immediate fix
Cost tracking per tier
This is the money side. Evals have a cost; track it or you'll run them less often than you should.

Tier	Cost per run	When to run
Tier 1 (deterministic)	$0	Every session (hook can run it automatically)
Tier 2 (LLM judge, 16 tasks, haiku)	~$0.05–0.10	Before any push to main
Tier 2 (LLM judge, 16 tasks, sonnet)	~$0.30–0.50	Weekly or before major doc changes
Tier 3 (manual review)	Your time	Before releasing major structural changes
Budget rule of thumb: Tier 1 is free — wire it into the pre-push hook. Tier 2 on haiku is cheap enough to run on every main branch push (add to CI or pre-push hook at ~$0.10/run). Tier 2 on sonnet is weekly. Tier 3 is quarterly or before big refactors.

Track spend in .beads/decisions.jsonl — record each time you change the eval cadence and why.

The 6 SLOs to track
These come directly from the Rumi eval harness. Measure them after each full Tier 2 run:

Metric	Target	What a breach means
Wrong-route rate	< 5%	L1 or L2 routing is broken — Claude picks wrong folder
Time-to-correct-doc	≤ 2 hops	Router chain is too deep or missing direct pointers
Stale-doc incidence	< 10%	last_verified dates are expiring; doc-health is slipping
Context payload size	< 3000 tokens avg	Too much is being auto-loaded; tighten L3 loading rules
Retrieval precision	> 80%	Loaded docs that weren't used — noise in the context
Unresolved ambiguity	< 15%	Agent asks clarifying questions when docs should answer
Store results in .claude/evals/baselines/ as append-only JSONL:

{"run_date":"2026-04-03","run_type":"baseline","tasks_total":8,"pass":7,"concerns":1,"rework":0,"fail":0,"metrics":{"wrong_route_pct":0,"avg_hops":1.2,"stale_pct":0,"avg_payload_tokens":1850,"precision_pct":88,"ambiguity_pct":12},"cost_usd":0.07}
The cost_usd field is mandatory. It's what makes the cadence decision concrete.

Starter eval set (8 tasks, one per doc type)
Write these first. They cover the most common failure modes:

Eval	Category	Tests
eval-001-credentials.yaml	explicit	Does it go to docs/credentials.md, not schema or changelog?
eval-002-deploy.yaml	explicit	Does it load the runbook, not the architecture doc?
eval-003-schema.yaml	explicit	Does it find the right reference doc in ≤1 hop?
eval-004-bug-symptom.yaml	implicit	Symptom described → does it reach the troubleshooting runbook?
eval-005-blocked.yaml	implicit	"I'm stuck on X" → correct domain or generic answer?
eval-006-two-domain.yaml	contextual	Task spanning 2 docs → does it load both without unnecessary extras?
eval-007-forbidden.yaml	negative	Simple question → does it avoid loading the full changelog?
eval-008-stale-test.yaml	negative	Asks about a recently changed area → does it flag staleness?
Auto-growth
New evals should be created automatically when failures are logged. Add this rule to your agent-improver agent (or docs-updater):

When you log an entry to .beads/failures.jsonl, check whether a matching eval task exists in .claude/evals/tasks/. If none covers that failure mode, create one. The failure is the prompt; the correct resolution is the expected block.

This means your eval suite grows organically from real incidents — which is exactly when you need it to.

These are the most common mistakes when setting up a harness:

1. Putting content in CLAUDE.md
CLAUDE.md is loaded in every session. If you put your database schema there, Claude loads 400 lines of schema when you're just fixing a typo. Route detail to L3 docs.

2. Hooks that talk too much
A hook that prints "✓ Check passed" on every write pollutes context with noise. Hooks should be completely silent on success. Only errors speak.

3. Agents with no Session End Protocol
An agent that doesn't close its own beads or update docs creates cleanup debt. Every agent file needs a ## Session End Protocol section.

4. One giant CLAUDE.md instead of a hierarchy
The Dec 2025 doc refactoring fixed a CLAUDE.md that had grown to 5,679 lines. At that size, the model was reading more context than it could usefully process. The line limit is not a suggestion.

5. Skills that duplicate CLAUDE.md content
If your deployment steps are in CLAUDE.md AND in the deploy skill, they'll drift. Pick one source of truth. CLAUDE.md gets a pointer (See \/deploy` skill`); the skill gets the actual steps.

6. Skipping the failures log
The two most valuable files in the Rumi repo are decisions.jsonl and failures.jsonl. Every incident that caused a production bug is documented. New developers (human or AI) don't repeat those mistakes. If you only set up one extra thing, set up the failures log.

The self-improving loop
A well-built harness gets better over time without manual maintenance:

Agents log learnings — session-end hook appends to the ## Self-Improvement Log in each agent/skill file
Failures log — every incident that slips through gets documented
Hook improvements — when a new class of mistake is identified, add a hook to block it
Bead archaeology — quarterly, scan closed beads for patterns (recurring bugs → missing hook; recurring docs rot → missing SLO)
The goal is a system where Claude Code in this repo is meaningfully smarter in month 3 than it was in month 1 — not because Claude got better, but because the harness accumulated hard-won knowledge.

Quick start (30-minute version)
If you want the minimal harness to get going now:

1. Create CLAUDE.md (use template above, fill in your project specifics)
2. Create .claude/settings.json (copy from Phase 4)
3. Create the 5 hook scripts in .claude/hooks/ (copy from Phase 4, chmod +x them)
4. Create .beads/status.jsonl (one line schema + your first bead)
5. Run the verify checklist from Phase 8
That's it. The full build (agents, skills, standards, QA) can come over the next few sessions as you discover what you actually need.

Built from patterns in Taleemabad's CEO OS and Rumi repos. If you find a better pattern, document it in your failures/decisions logs — and share it so we can update this file.

Last updated: 2026-04-03ontext Engineering Harness Bootstrap
For: Any Taleemabad team member setting up Claude Code on their repo
Time: 2–4 hours for a full build, 30 min for a minimal starter
What you get: A self-reinforcing AI development environment that enforces quality, loads context intelligently, tracks work, and improves itself over time.

What you're building and why
A harness is two things working together:

Guides (feedforward): CLAUDE.md files, agents, skills — they steer Claude before it acts
Sensors (feedback): Hooks, tests, validators — they observe after Claude acts and correct mistakes
Without both, you have a style guide that nobody enforces. The CEO OS and Rumi repos work because violations are caught mechanically, not by asking Claude to be disciplined.

The other thing to understand: context is a depletable resource. Every token you load degrades the tokens already there (Stanford's "lost in the middle" finding). The L1→L2→L3 system below is about loading the minimum high-signal context needed for each task — not stuffing everything in upfront.

Before you start — give Claude this entire file
Paste this file into a new Claude Code session in your repo root. Then say:

"Read this file completely. Then audit my repo and build the harness described in it, phase by phase. Ask me before completing each phase."

Claude will follow the phases below and build your harness. You review each phase before it moves on.

Phase 1: Audit (Claude does this first)
Before building anything, Claude should understand what exists. Run:

1. List every file in the repo root
2. List all directories (1 level deep)
3. Find any existing CLAUDE.md files
4. Find any existing .claude/ directories
5. Find any existing README.md files
6. Identify what kind of repo this is (code / docs / mixed)
7. Identify the primary language(s) and frameworks
8. Identify if there's a deployment target (Railway, Vercel, etc.)
Produce a one-page audit summary before touching anything.

Phase 2: Build the CLAUDE.md Hierarchy (L1 → L2 → L3)
This is the progressive disclosure system. Information is layered so Claude loads only what it needs.

The L1/L2/L3 contract
Level	What lives here	Line limit	When loaded
L1	CLAUDE.md — navigation only, critical rules, pointers	≤150 lines	Always, every session
L2	README.md per folder, SKILL.md per skill	≤100 lines	When a task matches that domain
L3	Actual docs, runbooks, references, plans	≤300 lines per file	Only when blocked without it
L4	Archives, changelogs, full transcripts	Unlimited	On-demand, load by section only
Hard rule: L1 contains zero substantive content. It is a routing table, nothing else.

L1: Root CLAUDE.md template
# [Project Name] — Claude Operating Manual

**Owner:** [Your name]  
**Purpose:** [One sentence]

---

## Quick Navigation

| Looking for... | Go to... |
|----------------|----------|
| How to deploy | `docs/deployment.md` |
| Database schema | `docs/schema.md` |
| API credentials | `.env` + `docs/credentials.md` |
| Active work | `.beads/status.jsonl` |
| Agent list | `.claude/agents/` |

---

## Folder Structure

| Folder | Contents |
|--------|----------|
| `src/` | Application code |
| `docs/` | Reference documentation |
| `.claude/` | Agents, skills, hooks, standards |
| `.beads/` | Work tracking |

---

## Agents

| Agent | Purpose |
|-------|---------|
| `docs-updater` | Update docs after code changes |
| `debugger` | Investigate errors from logs |

---

## Skills

| Skill | Invoke | Purpose |
|-------|--------|---------|
| `deploy` | `/deploy` | Deployment operations |
| `debug` | `/debug` | Log analysis and tracing |

---

## Critical Rules

1. **Never deploy with `railway up`** — use `git push` only (auto-deploy is wired)
2. **Never hardcode credentials** — read from `.env`; put path in `docs/credentials.md`  
3. **Every task gets a bead** — open a bead before starting, close it when done
4. **CLAUDE.md stays under 150 lines** — route detail to L2/L3, never dump it here
5. **Verify don't assume** — after deploy, hit the health endpoint; don't say "should work"

---

## Development Cycle (mandatory for all code work)

INVESTIGATE → Read all code in the execution path. Write findings.
PLAN → List files to change, edge cases, what NOT to touch.
RED TEAM → What could go wrong? Race conditions? Schema deps?
PRE-DEPLOY → Apply DB migrations, set env vars BEFORE pushing code.
TEST → Write test → confirm FAIL → implement → confirm PASS.
DEPLOY → git push. Wait for health endpoint to reset.
VERIFY → Health check + logs + functional test. Not assumed state.
CLOSE OUT → Update bead, update docs, log failures if any.

L2: Folder README template
Each major folder gets a README.md that routes to L3 docs:

# [Folder Name]

**Purpose:** One sentence.

## Key Documents

| Document | What it answers |
|----------|----------------|
| [deployment.md](deployment.md) | How to deploy to each environment |
| [schema.md](schema.md) | Database tables and relationships |
| [credentials.md](credentials.md) | Where credentials live, how to rotate |

## Active Work

See `.beads/status.jsonl` for open tasks in this area.
L3: Document types and frontmatter
Every L3 doc (and every L2 README) must have YAML frontmatter at the very top. This is what the validate-after-write.sh hook enforces. Without it, Claude has no way to know what a document is, how fresh it is, or when to load it.

Minimum required frontmatter:

---
type: router | runbook | reference | investigation | plan | changelog
last_verified: YYYY-MM-DD
owner: your-name
---
Full frontmatter (use these fields when relevant):

---
type: reference
last_verified: 2026-04-03
owner: sabeena
status: active
related_beads: ["bd-012", "bd-015"]
parent: docs/README.md
---
Field	Required	Purpose
type	✓	Controls line limits and load behavior (see table below)
last_verified	✓	Date the content was last checked for accuracy
owner	✓	Person or agent responsible for keeping it fresh
status	—	active | archived — for investigations and plans only
related_beads	—	Bead IDs this doc was created to support
parent	—	The L2 router that links to this doc
Document types in detail
Each type has a job and a line limit. The limits are not arbitrary — they exist because Claude's performance degrades as context grows. A 600-line reference doc loaded alongside 3 others fills the working context before the task is done.

router — Navigation only. Contains links, one-line descriptions, and nothing else. No content. Think of it as a table of contents file. - Line limit: 100 - Load behavior: Always safe to load (it's small and contains no stale facts) - Examples: CLAUDE.md, all README.md files, docs/index.md - What NOT to put in it: procedures, credentials, code snippets, explanations longer than one sentence

---
type: router
last_verified: 2026-04-03
owner: haroon
---

# Docs

| Document | What it answers |
|----------|----------------|
| [deployment.md](deployment.md) | How to deploy to each environment |
| [schema.md](schema.md) | Database tables and column types |
| [credentials.md](credentials.md) | Where credentials live, how to rotate |
runbook — Step-by-step procedures. Each step is an action, not a description. Someone should be able to execute a runbook without reading anything else. - Line limit: 200 - Load behavior: Load when executing that specific procedure - Examples: deployment.md, db-migration.md, rollback-procedure.md - What NOT to put in it: background context, design rationale, architecture explanations (those go in reference)

```markdown
type: runbook last_verified: 2026-04-03

owner: sabeena
Deploy to Staging
Prerequisites
[ ] Smoke tests passing: bash .claude/scripts/smoke-test.sh
[ ] Open bead for this deploy: bd-XXX
Steps
Push to staging branch: bash git push origin staging

Wait for health endpoint to reset (~2 min): bash watch -n 15 "curl -s https://your-app-staging.up.railway.app/health | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get(\"uptime\"))'"

Verify logs clean: bash railway logs --lines 30

Close deploy bead with commit hash as resolution. ```

reference — Stable lookup information. Doesn't change often. Loaded when Claude needs to know something factual about the system (schema, credentials location, API endpoints, environment variables). - Line limit: 300 - Load behavior: Load when the domain is active this session - Examples: schema.md, credentials.md, environment-variables.md, api-endpoints.md - What NOT to put in it: procedures, history, current investigations

---
type: reference
last_verified: 2026-04-03
owner: haroon
---

# Database Schema

## evaluations

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| id | UUID | No | Primary key, auto-generated |
| agent_id | VARCHAR | No | Which agent submitted |
| session_id | VARCHAR | No | Coaching session being evaluated |
| overall_score | FLOAT | Yes | 0–100, null until evaluated |
| compliance_tier | VARCHAR | Yes | pass \| partial \| fail |

## standard_results

Foreign key: `evaluation_id → evaluations.id` (cascades on delete)

| Column | Type | Notes |
|--------|------|-------|
| standard_id | VARCHAR | e.g. "T3", "P1" |
| compliance_status | VARCHAR | met \| partial \| not_met \| not_evaluated |
| score | FLOAT | 0–100 |
investigation — Active analysis with findings. Created when debugging a problem or doing a deep dive. Has a clear start, findings section, and conclusion. Time-bound — investigations become archived once the problem is resolved. - Line limit: 300 (split if longer; rarely needed) - Load behavior: Load when actively working on that specific problem - status field is mandatory: active while open, archived when resolved - Examples: reports/active/INVESTIGATION.md, reports/active/rca-email-failure.md

---
type: investigation
last_verified: 2026-04-03
owner: claude
status: active
related_beads: ["bd-023"]
---

# Investigation: T2 Latency Check False Failures

## Problem
Submissions with 7-minute processing times are failing the T2 SLA check (≤10 min).

## Hypothesis
The `processing_time_minutes` field in the submission is recording wall-clock time
including the Kie.ai polling loop, not just the coaching session processing time.

## Findings
- Checked 5 failing submissions: all had processing_time between 9.8–10.4 min
- The extra 0.4 min is the Kie.ai API polling overhead (5 × 10s polls)
- SLA spec says "processing time for observation analysis", not total round-trip

## Resolution
[pending — update when fix is deployed]
plan — Proposed approach with decisions. Created before starting a non-trivial implementation. Contains the design, trade-offs considered, and open questions. Unlike investigations, plans are forward-looking. - Line limit: None (plans need room to think) - Load behavior: Load when planning or reviewing a design - status field: active while being executed, archived when done

---
type: plan
last_verified: 2026-04-03
owner: sabeena
status: active
related_beads: ["bd-031"]
---

# Plan: Lesson Plans Evaluator (V1)

## Goal
Copy the Digital Coach evaluator pattern and adapt it for Lesson Plans standards.

## Files to create
- `01-our-data-intelligence-system/evaluator/` (copy evaluator/ folder)
- Change standards.py to LP standards subset from the Google Sheet
- Add LP-specific check functions in evaluator.py

## Standards to implement (LP column from framework)
- P5 ● (required), P2 ● (required), P3 ● (required), P1 ● (required)
- T10 ● T2 ● X1 ● P4 ● T1 ● T8 ● T6 ● T9 ● X5 ● X3 ● X8 ● X2 ● X4 ● X10 ● X7 ●

## What NOT to change
- models.py — schema is service-agnostic, reuse as-is
- Hook configuration — no changes needed
- requirements.txt — same dependencies

## Open questions
- Should LP evaluator share a database with Digital Coach, or separate db files?
  Current lean: separate files per service, merge if reporting needs it
changelog — Version history. Append-only. Load by version section only — never load the full file. - Line limit: None (it grows forever) - Load behavior: Load only the specific version section needed - Examples: docs/changelog.md, CHANGELOG.md

---
type: changelog
last_verified: 2026-04-03
owner: claude
---

# Changelog

## v1.1.0 — 2026-04-03
- Added P2 (Prerequisite Sequencing) check to Digital Coach evaluator
- Fixed T2 threshold to measure processing time only (not total wall-clock)
- Deployed: commit 91a3bc2

## v1.0.0 — 2026-04-03
- Initial Digital Coach evaluator with 10 standard checks
- FastAPI app, SQLite storage, example submission
- Deployed: commit acb0556
Splitting documents that exceed limits
When a document hits its limit, split it — don't expand it.

Pattern:

docs/schema.md          ← original, now a router
docs/schema-tables.md   ← tables and columns (reference, 300 lines)
docs/schema-indexes.md  ← indexes and constraints (reference, 100 lines)
The router (schema.md) becomes:

---
type: router
last_verified: 2026-04-03
owner: sabeena
---

# Schema

| Document | Contents |
|----------|---------|
| [schema-tables.md](schema-tables.md) | All tables, columns, types, nullability |
| [schema-indexes.md](schema-indexes.md) | Indexes, constraints, foreign keys |
Never have a 600-line reference doc. Split first, route through an index.

Phase 3: Set up Agents and Skills
Agents and skills are not the same thing.

Agents (.claude/agents/[name].md)
Autonomous, multi-step orchestrators. An agent can run for an hour, manage a complex task end to end, track its own state, and update beads. Use agents when a task requires judgment, multiple tools, and sequential steps.

Every agent file must include: 1. What it does — one paragraph 2. When to invoke it — trigger conditions (explicit / proactive / scheduled) 3. What it reads — which L2/L3 docs to load 4. What it produces — outputs, side effects 5. Session End Protocol — what to do before stopping (close beads, update docs) 6. Self-Improvement Log — learnings recorded mid-stream (dated entries)

---
name: docs-updater
description: Updates documentation after code changes. Invoke after any deploy or bug fix.
trigger: reactive
cost: low
---

# docs-updater

Updates all documentation impacted by the current code change.

## When to invoke
- After any feature deployment
- After any bug fix
- When user says "update the docs"

## What to read
1. Check which files were changed this session (git diff)
2. Load the relevant L2/L3 docs for those areas
3. Load `.claude/standards/DOC_TYPE_SYSTEM.md`

## What to produce
- Updated L3 docs (never update CLAUDE.md with content — only pointer updates)
- New investigation doc if debugging session produced findings
- Changelog entry in `docs/changelog.md`

## Session End Protocol
1. Close any beads opened this session
2. Verify updated docs are under line limits
3. Commit changes with descriptive message

## Self-Improvement Log
<!-- Append dated learnings here as you discover them -->
Skills (.claude/skills/[name]/SKILL.md)
Static knowledge libraries. A skill is loaded when domain knowledge is needed — API patterns, credentials, tool syntax, workflow steps. Skills don't take autonomous actions; they inform Claude how to perform specific operations.

Every skill file must include: 1. What domain it covers — one sentence 2. Authentication — exactly how to authenticate (credentials location, scopes) 3. Core patterns — the 3-5 most-used operations with working code 4. Known issues — gotchas, version incompatibilities, errors you've hit 5. Learnings log — session-end hook updates this automatically

```markdown
name: deploy

description: Deployment operations for Railway. Invoke with /deploy.
Deploy Skill
Handles all deployment operations to Railway environments.

Authentication
Railway token: .env → RAILWAY_TOKEN Project ID: .env → RAILWAY_PROJECT_ID

Core Patterns
Deploy to staging
git push origin staging
# Railway auto-deploys. Wait for health endpoint to reset (~2-3 min).
Check deployment status
railway status --service [service-name]
Verify deploy succeeded
curl -s https://[your-app].up.railway.app/health | python3 -c "import json,sys; d=json.load(sys.stdin); print('uptime:', d.get('uptime'))"
Known Issues
Never use railway up — bypasses branch→service mapping, can deploy staging to prod
Health endpoint may take 90s to reset after deploy — poll every 15s, don't assume
Learnings Log
<!-- Updated by session-end hook -->
```

Invocation modes
Mode	Behavior
auto	Claude loads this without being asked (e.g., every session)
manual	Only loaded when user explicitly invokes /skill-name
suggest	Claude mentions it but doesn't load unless user confirms
Set mode in the agent or skill frontmatter: trigger: auto | manual | suggest

Phase 4: Wire up Hooks
This is what makes the harness mechanical. Hooks enforce rules so Claude doesn't have to be disciplined — violations are blocked automatically.

Hook fundamentals
Hooks fire at lifecycle events and communicate through exit codes: - Exit 0: Allow the action (silent success) - Exit 2: Block the action. Stderr is shown to Claude as an error. Claude must fix the problem before retrying.

Key rule: hooks should be silent on success, loud on failure. Every message a passing hook sends pollutes the context window.

Create .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/block-bad-commands.sh\"",
            "timeout": 3000
          }
        ]
      },
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/guard-file-writes.sh\"",
            "timeout": 3000
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/validate-after-write.sh\"",
            "timeout": 5000
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh\"",
            "timeout": 5000
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR/.claude/hooks/session-end.sh\"",
            "timeout": 30000
          }
        ]
      }
    ]
  }
}
Hook 1: Block bad commands (PreToolUse / Bash)
.claude/hooks/block-bad-commands.sh:

#!/bin/bash
# Reads the bash command from stdin (JSON)
COMMAND=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))" 2>/dev/null)

# Block railway up — use git push instead
if echo "$COMMAND" | grep -qE "railway\s+up\b"; then
  echo "ERROR: 'railway up' is blocked. Use 'git push origin [branch]' instead." >&2
  echo "Railway auto-deploys from git push. 'railway up' bypasses branch→service mapping." >&2
  exit 2
fi

# Block force push to main without warning
if echo "$COMMAND" | grep -qE "git push.*--force.*main|git push.*-f.*main"; then
  echo "ERROR: Force push to main is blocked. Use a PR or ask the repo owner." >&2
  exit 2
fi

# Block committing .env files
if echo "$COMMAND" | grep -qE "git add.*\.env|git commit.*\.env"; then
  echo "ERROR: Attempting to commit .env file. Credentials must never be committed." >&2
  exit 2
fi

exit 0
Hook 2: Guard file writes (PreToolUse / Write|Edit)
.claude/hooks/guard-file-writes.sh:

#!/bin/bash
FILEPATH=$(echo "$CLAUDE_TOOL_INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null)

# Block writing to .env directly (read from it, don't overwrite it carelessly)
if echo "$FILEPATH" | grep -qE "^\.env$|/\.env$"; then
  echo "WARNING: Writing to .env. Verify you are not overwriting existing credentials." >&2
  # Don't block (exit 0) but warn — this is a soft guard
fi

# Check CLAUDE.md line count if being edited
if echo "$FILEPATH" | grep -qE "CLAUDE\.md$"; then
  if [ -f "$FILEPATH" ]; then
    LINES=$(wc -l < "$FILEPATH")
    if [ "$LINES" -gt 195 ]; then
      echo "ERROR: CLAUDE.md has $LINES lines (limit: 150). Move content to L2/L3 docs first." >&2
      exit 2
    fi
  fi
fi

exit 0
Hook 3: Validate after write (PostToolUse / Write|Edit)
.claude/hooks/validate-after-write.sh:

#!/bin/bash
FILEPATH=$(echo "$CLAUDE_TOOL_OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null)

# Syntax check Python files
if echo "$FILEPATH" | grep -qE "\.py$"; then
  if ! python3 -m py_compile "$FILEPATH" 2>/tmp/syntax-error; then
    echo "ERROR: Python syntax error in $FILEPATH:" >&2
    cat /tmp/syntax-error >&2
    exit 2
  fi
fi

# Check for missing doc headers on markdown files
if echo "$FILEPATH" | grep -qE "\.md$" && ! echo "$FILEPATH" | grep -qE "CLAUDE\.md$"; then
  if ! head -5 "$FILEPATH" | grep -q "^---"; then
    echo "WARNING: $FILEPATH is missing YAML frontmatter (type, last_verified, owner)." >&2
  fi
fi

exit 0
Hook 4: Session start (SessionStart)
.claude/hooks/session-start.sh:

#!/bin/bash
# Inject useful context at the start of every session

echo "=== SESSION START ==="

# Show open beads (active work)
if [ -f ".beads/status.jsonl" ]; then
  OPEN=$(grep '"status":"open"' .beads/status.jsonl 2>/dev/null | tail -10)
  if [ -n "$OPEN" ]; then
    echo "OPEN BEADS (active work):"
    echo "$OPEN" | python3 -c "
import json,sys
for line in sys.stdin:
    try:
        d = json.loads(line)
        print(f\"  [{d.get('priority','?')}] {d.get('id','?')}: {d.get('title','?')}\")
    except: pass
"
  else
    echo "No open beads."
  fi
fi

# Check for stale CLAUDE.md
if [ -f "CLAUDE.md" ]; then
  LINES=$(wc -l < CLAUDE.md)
  if [ "$LINES" -gt 150 ]; then
    echo "WARNING: CLAUDE.md has $LINES lines (target: <150). Consider trimming."
  fi
fi

echo "====================="
exit 0
Hook 5: Session end (Stop)
.claude/hooks/session-end.sh:

#!/bin/bash
echo "=== SESSION END CHECK ==="

# Check for unclosed beads
if [ -f ".beads/status.jsonl" ]; then
  OPEN_COUNT=$(grep -c '"status":"open"' .beads/status.jsonl 2>/dev/null || echo 0)
  if [ "$OPEN_COUNT" -gt 0 ]; then
    echo "REMINDER: $OPEN_COUNT open bead(s). Update status before closing if work is done."
  fi
fi

# Check for unstaged changes
UNSTAGED=$(git diff --stat 2>/dev/null | tail -1)
if [ -n "$UNSTAGED" ]; then
  echo "REMINDER: Unstaged changes exist. Commit or stash before closing."
fi

# Check for bloated CLAUDE.md
if [ -f "CLAUDE.md" ]; then
  LINES=$(wc -l < CLAUDE.md)
  if [ "$LINES" -gt 150 ]; then
    echo "WARNING: CLAUDE.md is $LINES lines. Trim it before next session."
  fi
fi

echo "========================"
exit 0
Phase 5: Beads (work tracking)
Beads are your issue tracker, baked into the repo as append-only JSONL files. They exist for one reason: Claude Code sessions have no persistent memory across context resets. If you're midway through a bug fix and the context window fills up, the next session has no idea what you were doing. Beads are what survives.

The session-start hook injects open beads at the top of every session. Claude reads them, understands what's in flight, and continues without you repeating yourself.

The three bead files
.beads/
├── status.jsonl     — all tasks: open, in_progress, closed
├── decisions.jsonl  — architectural decisions and their rationale
├── failures.jsonl   — production incidents, bugs, lessons
└── README.md        — how beads work (for humans and Claude)
All three are append-only. Never edit a previous line — add a new one. This is deliberate: the history is the value.

.beads/status.jsonl — full schema
Every line (after the schema line) is a bead. Fields:

Field	Type	Required	Values
id	string	✓	bd-001, bd-002, ... (sequential, never reuse)
title	string	✓	Short imperative: "Fix T2 threshold bug"
status	string	✓	open | in_progress | closed | blocked
priority	string	✓	critical | high | medium | low
created	string	✓	ISO date: "2026-04-03"
updated	string	✓	ISO date of last change
category	string	✓	bug | feature | docs | infrastructure | agent | refactor
resolution	string|null	✓	null when open; commit hash or description when closed
blocked_by	string|null	—	"bd-012" if blocked by another bead
owner	string	—	"claude" or a person's name
related_files	array	—	["src/evaluator.py", "main.py"]
Bootstrap file — create this first:

{"schema": "v1", "fields": ["id","title","status","priority","created","updated","category","resolution","blocked_by","owner"]}
{"id": "bd-001", "title": "Bootstrap repo harness", "status": "in_progress", "priority": "high", "created": "2026-04-03", "updated": "2026-04-03", "category": "infrastructure", "resolution": null, "blocked_by": null, "owner": "claude"}
The bead lifecycle
Every piece of work follows this lifecycle — no exceptions:

Task identified
      ↓
Open bead (status: "open")     ← do this BEFORE touching any code
      ↓
Start work
      ↓
Update to in_progress           ← when you actually start
      ↓
Hit a blocker?
  YES → set status: "blocked", blocked_by: "bd-XXX" or describe in title
  NO  → continue
      ↓
Work complete
      ↓
Close bead (status: "closed", resolution: "commit abc123 / what was done")
When to open a bead: - Discovering a bug → open a bead immediately, before investigating - Starting a feature → open a bead, then plan - Writing documentation → open a bead - Setting up the harness → bd-001 is already there

When NOT to open a bead: - One-line fixes that are trivially reversible (change a config value, update a comment) - Read-only work (research, reading logs) - Anything that takes under 5 minutes and has no side effects

Closing a bead — the resolution field is critical:

{"id": "bd-001", "title": "Bootstrap repo harness", "status": "closed", "priority": "high", "created": "2026-04-03", "updated": "2026-04-03", "category": "infrastructure", "resolution": "Completed harness build: CLAUDE.md hierarchy, 5 hooks, standards docs, beads. Commit 862fab3.", "blocked_by": null, "owner": "claude"}
The resolution should answer: what was done, and how would someone verify it?

Querying beads (Claude does this, but you can too)
Because beads are JSONL, they're trivially queryable:

# Show all open beads
grep '"status":"open"' .beads/status.jsonl | python3 -c "
import json, sys
for line in sys.stdin:
    d = json.loads(line)
    print(f\"[{d['priority'].upper()}] {d['id']}: {d['title']}\")
"

# Show blocked beads
grep '"status":"blocked"' .beads/status.jsonl

# Show all bugs
grep '"category":"bug"' .beads/status.jsonl | grep '"status":"open"'

# Count open by priority
grep '"status":"open"' .beads/status.jsonl | python3 -c "
import json, sys, collections
counts = collections.Counter()
for line in sys.stdin:
    try: counts[json.loads(line)['priority']] += 1
    except: pass
for p, n in counts.most_common(): print(f'{p}: {n}')
"
The session-start hook runs a version of the first query and injects the results into every session. That's the memory that survives context resets.

Quarterly archive
Every three months, move closed beads older than 90 days to history:

# Run this manually or add to a scheduled agent
python3 -c "
import json
from datetime import date, timedelta

cutoff = (date.today() - timedelta(days=90)).isoformat()
active, archive = [], []

with open('.beads/status.jsonl') as f:
    for line in f:
        try:
            d = json.loads(line)
            if d.get('status') == 'closed' and d.get('updated', '') < cutoff:
                archive.append(line)
            else:
                active.append(line)
        except:
            active.append(line)  # keep schema line and malformed lines

with open('.beads/status.jsonl', 'w') as f:
    f.writelines(active)

with open('.beads/history.jsonl', 'a') as f:
    f.writelines(archive)

print(f'Archived {len(archive)} beads.')
"
.beads/decisions.jsonl — architectural decisions
Every non-obvious technical decision gets recorded here. Not "I chose Python over Bash for a script" — that's obvious. Yes to "I chose SQLite over Postgres for V1 because the evaluator has no concurrent writes and we don't want Railway infrastructure yet."

The test: could a new engineer (or Claude next month) reconstruct the reasoning from this entry alone?

Full schema:

Field	Purpose
date	When the decision was made
decision	One-sentence summary of what was decided
rationale	Why — the constraint, deadline, or trade-off that drove it
alternatives	What else was considered and why rejected
revisit_when	Optional: conditions under which to revisit (e.g., "when we have >1 concurrent user")
{"date": "2026-04-03", "decision": "SQLite for V1 evaluator storage", "rationale": "Zero infrastructure overhead; evaluations.db lives next to the app. ORM (SQLAlchemy) is database-agnostic so swap to Postgres is a config change.", "alternatives": ["Postgres on Railway — overkill for V1, adds infra to manage", "Flat JSON files — no query capability, no relationships"], "revisit_when": "When evaluator needs multi-user concurrent writes or remote access"}
{"date": "2026-04-03", "decision": "FastAPI over Flask for evaluator API", "rationale": "Auto-generated /docs (Swagger UI) means Sabeena can test without writing curl commands. Critical for learning.", "alternatives": ["Flask — less boilerplate but no auto-docs", "Django — overkill, we don't need ORM bundled in the web layer"], "revisit_when": "Never — this is a permanent choice for internal tools"}
.beads/failures.jsonl — production incidents and lessons
This is the most valuable file in the system. Every bug that caused an incident, every assumption that turned out wrong, every deployment that broke something — goes here, immediately after the fix.

The Rumi repo has entries like em-125 (hallucinated meeting notes) and em-126 (quadruple emails) that became the reason for specific rules in the development methodology. Those rules exist because the failures are documented.

Full schema:

Field	Purpose
date	When it happened
incident	What the user/system experienced
root_cause	The actual technical cause (not the symptom)
fix	What was done to resolve it
lesson	The rule or pattern change that prevents recurrence
related_bead	The bead ID for this fix, if one was opened
{"date": "2026-04-03", "incident": "Kie.ai slide generation silently failed — all 6 slides returned no output", "root_cause": "Payload used 'prompt' key at top level. Correct format wraps in 'input': {'prompt': ...}. API returned 422 with 'input cannot be null' but error was not surfaced in the polling loop.", "fix": "Rewrapped payload in 'input' object. Added response logging to create_task().", "lesson": "Always log the raw API response on task creation, not just the task_id. Silent 422s are worse than loud 500s.", "related_bead": null}
{"date": "2026-04-03", "incident": "Google Doc creation failed with 403 'caller does not have permission'", "root_cause": "Service account used 'spreadsheets' scope for Docs API. DWD in hellorumi.ai workspace only authorizes 'drive' scope, which covers Docs/Sheets/Slides. Individual API scopes fail.", "fix": "Changed SCOPES to ['https://www.googleapis.com/auth/drive']. All GWS APIs work through Drive scope.", "lesson": "DWD authorization is per-scope, not per-API. Check the workspace admin's DWD scope list before writing code. Drive scope is the master key for GWS.", "related_bead": null}
.beads/README.md — for humans and Claude
Create this so anyone who opens the folder understands what they're looking at:

---
type: reference
last_verified: 2026-04-03
owner: you
---

# Beads — Work Tracking

Append-only JSONL issue tracker. Three files:

| File | Purpose |
|------|---------|
| `status.jsonl` | All tasks (open, in_progress, closed, blocked) |
| `decisions.jsonl` | Architectural decisions and rationale |
| `failures.jsonl` | Production incidents and lessons |
| `history.jsonl` | Archived closed beads (>90 days old) |

## Rules

- Append only — never edit a previous line
- Open a bead before touching code, close it after verifying the fix
- Resolution field must answer: what was done and how to verify it
- Archive quarterly (see HARNESS_BOOTSTRAP.md Phase 5 for script)

## Querying

All files are JSONL — query with grep or python3:

    grep '"status":"open"' status.jsonl          # all open work
    grep '"category":"bug"' status.jsonl          # all bugs ever
    grep '"priority":"critical"' status.jsonl     # critical items

## Why this exists

Claude Code has no persistent memory across context resets.
The session-start hook reads the last 10 open beads and injects them
into every session. This is how work-in-progress survives a context window fill.
Phase 6: Standards documents
Create four policy documents in .claude/standards/. These are the governance layer — they tell Claude how to behave across all sessions.

.claude/standards/DOC_TYPE_SYSTEM.md
---
type: reference
last_verified: [DATE]
---

# Document Type System

Every document in this repo belongs to one type. Type determines line limits and load behavior.

| Type | Purpose | Line limit | Load behavior |
|------|---------|-----------|---------------|
| router | Navigation only — links, no content | 100 | Always safe to load |
| runbook | Step-by-step procedures | 200 | Load when executing that procedure |
| reference | Stable lookup information | 300 | Load when that domain is active |
| investigation | Active analysis, time-bound | 300 | Load when debugging |
| plan | Proposed approach, decisions | Unlimited | Load when planning |
| changelog | Version history | Unlimited | Load by section only |

**Enforcement:** Every markdown file must have YAML frontmatter with `type:` and `last_verified:`.
.claude/standards/INVOCATION_POLICY.md
---
type: reference
last_verified: [DATE]
---

# Invocation Policy

Defines when each agent and skill is loaded.

## Agents

| Agent | Trigger | Invocation |
|-------|---------|-----------|
| docs-updater | After any code change | Reactive (user or post-deploy) |
| debugger | When errors appear in logs | Proactive |

## Skills

| Skill | Command | When |
|-------|---------|------|
| deploy | /deploy | Before any push to staging/main |
| debug | /debug | When investigating errors |

## Cost tiers
- **Low:** Fast, routine work — haiku model preferred
- **Medium:** Standard complexity — sonnet model
- **High:** Deep analysis — opus model, use sparingly
.claude/standards/RETRIEVAL_POLICY.md
---
type: reference
last_verified: [DATE]
---

# Retrieval Policy

What gets loaded when. Follow this to avoid context pollution.

## L1 (always, every session)
- CLAUDE.md
- Open beads from `.beads/status.jsonl` (last 10)

## L2 (load one, based on task type)
- Code work → `src/README.md`
- Deployment → `docs/deployment.md`
- Debugging → `docs/troubleshooting.md`
- Database → `docs/schema.md`

## L3 (load only when blocked)
- Load the specific doc that unblocks the task
- Max 2-3 L3 docs per session
- Never load full changelog — find the relevant version section

## Never auto-load
- Archives
- Full changelogs
- Completed investigations
- Historical reports
.claude/standards/METADATA_CONTRACT.md
```markdown
type: reference

last_verified: [DATE]
Metadata Contract
Every markdown file (except CLAUDE.md) must have this frontmatter:

---
type: router|runbook|reference|investigation|plan|changelog
last_verified: YYYY-MM-DD
owner: your-name
---
Freshness SLOs
Doc type	Max staleness
CLAUDE.md	2 weeks
Routers (README.md)	1 month
Core reference docs	2 months
Agent/skill files	2 months
Changelogs	No SLO (append-only)
When last_verified exceeds SLO, add it to a bead. ```

Phase 7: QA enforcement
Your hooks are the foundation. Now layer in actual quality checks.

Minimum viable QA setup
Syntax check on every Python/JS write — already in hook 3 above
One smoke test script that Claude can run before pushing:
# .claude/scripts/smoke-test.sh
#!/bin/bash
echo "Running smoke tests..."

# 1. Import check (Python)
if ls src/*.py &>/dev/null; then
  for f in src/*.py; do
    python3 -m py_compile "$f" || { echo "FAIL: $f has syntax errors"; exit 1; }
  done
  echo "✓ Python syntax OK"
fi

# 2. Critical file check
for f in CLAUDE.md .env; do
  [ -f "$f" ] || { echo "FAIL: Missing $f"; exit 1; }
done
echo "✓ Critical files present"

# 3. CLAUDE.md line count
LINES=$(wc -l < CLAUDE.md)
[ "$LINES" -le 150 ] || { echo "FAIL: CLAUDE.md has $LINES lines (max 150)"; exit 1; }
echo "✓ CLAUDE.md line count OK ($LINES)"

echo "All smoke tests passed."
exit 0
Add pre-push QA hook that requires smoke tests to pass:
# Add to block-bad-commands.sh
if echo "$COMMAND" | grep -qE "git push"; then
  if ! bash "$CLAUDE_PROJECT_DIR/.claude/scripts/smoke-test.sh" &>/dev/null; then
    echo "ERROR: Smoke tests failed. Run '.claude/scripts/smoke-test.sh' to see errors." >&2
    exit 2
  fi
fi
Phase 8: Verify the harness works
After all phases are complete, Claude should run this checklist:

□ CLAUDE.md exists at repo root and is under 150 lines
□ CLAUDE.md contains only routing tables and critical rules — no content
□ At least one L2 README.md exists (in a major folder)
□ At least one L3 reference doc exists with YAML frontmatter
□ .claude/settings.json exists with at least PreToolUse and Stop hooks
□ .claude/hooks/ directory has all 5 hook scripts, each chmod +x
□ .beads/status.jsonl exists with schema line
□ .beads/decisions.jsonl exists
□ .beads/failures.jsonl exists
□ .claude/standards/ has all 4 policy docs
□ .claude/agents/ has at least one agent file with Session End Protocol
□ .claude/skills/ has at least one skill file
□ Smoke test script runs and passes: bash .claude/scripts/smoke-test.sh
□ Hook triggers correctly: try editing CLAUDE.md with >150 lines — it should block
Phase 9: Eval Harness — measuring whether your docs actually work
The eval harness is how you know your documentation system is doing its job. It's borrowed directly from the Rumi repo (.claude/evals/EVAL_HARNESS.md).

The core problem it solves: you can write perfect documentation and still have Claude load the wrong file, load too many files, or take 4 hops to find something that should be 1 hop away. Without evals, you only discover this when a session goes wrong. With evals, you catch it before it costs you.

What an eval measures
Each eval is a test case: a user question, the doc Claude should load, the docs it should NOT load, and the maximum number of hops allowed to get there.

Hops = the number of files Claude loads before reaching the answer. The target is ≤2: - Hop 1: CLAUDE.md (L1) → identifies the right L2 router - Hop 2: the L2 router → points to the correct L3 doc

If Claude needs 3+ hops, your routing is broken. Either the L1 doesn't clearly point to the right L2, or the L2 doesn't clearly point to the right L3. Fix the router, not the destination.

Eval task format
Create .claude/evals/tasks/eval-NNN-description.yaml for each test case:

id: eval-001
description: "Find DB credentials"
category: explicit       # explicit | implicit | contextual | negative
input: "Where are the database credentials?"
expected:
  route: "docs/credentials.md"
  must_load: ["credentials.md"]
  must_not_load: ["changelog.md", "schema.md"]
  max_hops: 1
graders:
  - type: deterministic
    check: route_matches       # did agent load the expected route?
  - type: deterministic
    check: no_forbidden_loads  # did agent avoid the must_not_load list?
  - type: llm_judge
    rubric: "Does the response provide actual database connection details from the canonical credential source, not a pointer to find them elsewhere?"
    threshold: 4               # 1-5 scale; 4 means "good, minor gaps allowed"
quality_gate: PASS             # PASS | CONCERNS | REWORK | FAIL
Category types: | Category | What it tests | |----------|--------------| | explicit | User names the thing they want ("how do I deploy?") | | implicit | User describes a symptom ("the bot is stuck") — Claude must infer the domain | | contextual | Task requires combining two docs ("prepare staging→prod deploy") | | negative | Tests that Claude doesn't load things it shouldn't (forbidden loads) |

A good eval suite has all four. Explicit tests are easy to pass. Implicit and contextual tests are where routing actually breaks.

Three grader tiers
Tier 1: Deterministic (free, instant) — run on every session, no LLM needed

# .claude/evals/graders/run-tier1.sh
# Checks structural health: do all referenced paths exist? Are docs within size limits?
# Are cross-references valid? Are freshness SLOs met?
bash .claude/evals/graders/run-tier1.sh
What it checks: - All route paths in eval tasks actually exist as files - Every doc referenced in must_load lists exists - All markdown docs are within their type's line limit - All docs have YAML frontmatter with type and last_verified - last_verified is within the freshness SLO for that doc type - Cross-references (links between docs) resolve

Tier 2: LLM-as-judge (~$0.02/eval, run before pushing to main) — Claude scores each answer 1–5 against the rubric

The rubric in each eval is deliberately specific. Not "is this a good answer?" but "does this answer include the specific Railway deployment steps including environment checks and staging→main merge?" Generic rubrics produce meaningless scores.

Scoring scale: | Score | Meaning | |-------|---------| | 5 | Perfect — exactly the right doc, exact right answer, no waste | | 4 | Good — right doc, minor gaps or small amount of unnecessary context | | 3 | Acceptable — partially right, would still help the user | | 2 | Poor — wrong route or missing critical info | | 1 | Fail — blocked, wrong answer, or critical doc missing |

Threshold is per-eval: simple explicit tasks should score 4+. Implicit and contextual tasks can have threshold 3 if the domain is genuinely ambiguous.

Tier 3: Quality gate (manual, before major changes) — review the scores and decide

Gate	Definition	Action
PASS	Correct doc(s) loaded, answer accurate, no waste	None
CONCERNS	Right answer but unnecessary docs loaded, or minor gaps	Log and monitor
REWORK	Wrong route, retrieval waste, or partial answer	Fix the router or doc
FAIL	Blocked, wrong answer, or critical doc not found	Immediate fix
Cost tracking per tier
This is the money side. Evals have a cost; track it or you'll run them less often than you should.

Tier	Cost per run	When to run
Tier 1 (deterministic)	$0	Every session (hook can run it automatically)
Tier 2 (LLM judge, 16 tasks, haiku)	~$0.05–0.10	Before any push to main
Tier 2 (LLM judge, 16 tasks, sonnet)	~$0.30–0.50	Weekly or before major doc changes
Tier 3 (manual review)	Your time	Before releasing major structural changes
Budget rule of thumb: Tier 1 is free — wire it into the pre-push hook. Tier 2 on haiku is cheap enough to run on every main branch push (add to CI or pre-push hook at ~$0.10/run). Tier 2 on sonnet is weekly. Tier 3 is quarterly or before big refactors.

Track spend in .beads/decisions.jsonl — record each time you change the eval cadence and why.

The 6 SLOs to track
These come directly from the Rumi eval harness. Measure them after each full Tier 2 run:

Metric	Target	What a breach means
Wrong-route rate	< 5%	L1 or L2 routing is broken — Claude picks wrong folder
Time-to-correct-doc	≤ 2 hops	Router chain is too deep or missing direct pointers
Stale-doc incidence	< 10%	last_verified dates are expiring; doc-health is slipping
Context payload size	< 3000 tokens avg	Too much is being auto-loaded; tighten L3 loading rules
Retrieval precision	> 80%	Loaded docs that weren't used — noise in the context
Unresolved ambiguity	< 15%	Agent asks clarifying questions when docs should answer
Store results in .claude/evals/baselines/ as append-only JSONL:

{"run_date":"2026-04-03","run_type":"baseline","tasks_total":8,"pass":7,"concerns":1,"rework":0,"fail":0,"metrics":{"wrong_route_pct":0,"avg_hops":1.2,"stale_pct":0,"avg_payload_tokens":1850,"precision_pct":88,"ambiguity_pct":12},"cost_usd":0.07}
The cost_usd field is mandatory. It's what makes the cadence decision concrete.

Starter eval set (8 tasks, one per doc type)
Write these first. They cover the most common failure modes:

Eval	Category	Tests
eval-001-credentials.yaml	explicit	Does it go to docs/credentials.md, not schema or changelog?
eval-002-deploy.yaml	explicit	Does it load the runbook, not the architecture doc?
eval-003-schema.yaml	explicit	Does it find the right reference doc in ≤1 hop?
eval-004-bug-symptom.yaml	implicit	Symptom described → does it reach the troubleshooting runbook?
eval-005-blocked.yaml	implicit	"I'm stuck on X" → correct domain or generic answer?
eval-006-two-domain.yaml	contextual	Task spanning 2 docs → does it load both without unnecessary extras?
eval-007-forbidden.yaml	negative	Simple question → does it avoid loading the full changelog?
eval-008-stale-test.yaml	negative	Asks about a recently changed area → does it flag staleness?
Auto-growth
New evals should be created automatically when failures are logged. Add this rule to your agent-improver agent (or docs-updater):

When you log an entry to .beads/failures.jsonl, check whether a matching eval task exists in .claude/evals/tasks/. If none covers that failure mode, create one. The failure is the prompt; the correct resolution is the expected block.

This means your eval suite grows organically from real incidents — which is exactly when you need it to.

These are the most common mistakes when setting up a harness:

1. Putting content in CLAUDE.md
CLAUDE.md is loaded in every session. If you put your database schema there, Claude loads 400 lines of schema when you're just fixing a typo. Route detail to L3 docs.

2. Hooks that talk too much
A hook that prints "✓ Check passed" on every write pollutes context with noise. Hooks should be completely silent on success. Only errors speak.

3. Agents with no Session End Protocol
An agent that doesn't close its own beads or update docs creates cleanup debt. Every agent file needs a ## Session End Protocol section.

4. One giant CLAUDE.md instead of a hierarchy
The Dec 2025 doc refactoring fixed a CLAUDE.md that had grown to 5,679 lines. At that size, the model was reading more context than it could usefully process. The line limit is not a suggestion.

5. Skills that duplicate CLAUDE.md content
If your deployment steps are in CLAUDE.md AND in the deploy skill, they'll drift. Pick one source of truth. CLAUDE.md gets a pointer (See \/deploy` skill`); the skill gets the actual steps.

6. Skipping the failures log
The two most valuable files in the Rumi repo are decisions.jsonl and failures.jsonl. Every incident that caused a production bug is documented. New developers (human or AI) don't repeat those mistakes. If you only set up one extra thing, set up the failures log.

The self-improving loop
A well-built harness gets better over time without manual maintenance:

Agents log learnings — session-end hook appends to the ## Self-Improvement Log in each agent/skill file
Failures log — every incident that slips through gets documented
Hook improvements — when a new class of mistake is identified, add a hook to block it
Bead archaeology — quarterly, scan closed beads for patterns (recurring bugs → missing hook; recurring docs rot → missing SLO)
The goal is a system where Claude Code in this repo is meaningfully smarter in month 3 than it was in month 1 — not because Claude got better, but because the harness accumulated hard-won knowledge.

Quick start (30-minute version)
If you want the minimal harness to get going now:

1. Create CLAUDE.md (use template above, fill in your project specifics)
2. Create .claude/settings.json (copy from Phase 4)
3. Create the 5 hook scripts in .claude/hooks/ (copy from Phase 4, chmod +x them)
4. Create .beads/status.jsonl (one line schema + your first bead)
5. Run the verify checklist from Phase 8
That's it. The full build (agents, skills, standards, QA) can come over the next few sessions as you discover what you actually need.

Built from patterns in Taleemabad's CEO OS and Rumi repos. If you find a better pattern, document it in your failures/decisions logs — and share it so we can update this file.

Last updated: 2026-04-03