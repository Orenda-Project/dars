---
name: feature
description: Research → Plan → Implement workflow for a new feature. Enforces deep understanding before any code is written.
trigger: /feature
---

# /feature

Structured 3-phase workflow: **Research → Plan → Implement**.

## Invocation

```
/feature <feature-name-or-description>
```

## Phase 1 — Research

Goal: build a complete mental model before proposing anything. No code written here.

**Read in this order:**
1. `docs/ROADMAP.md` — locate the feature, understand priority and context
2. `docs/conventions.md` — code patterns, gotchas, migration rules
3. `docs/commands.md` — how to run, test, migrate
4. `graphify-out/GRAPH_REPORT.md` if it exists — god nodes and community structure
5. All modules in `server/src/dars/` that the feature will touch — read fully, not excerpts
6. Existing tests in `server/tests/` relevant to the area
7. Any open beads in `.beads/status.jsonl` that overlap with this feature
8. Relevant spec in `docs/specs/` if one exists

**Research output (internal, not shown to user):**
- List of all files that will change
- List of all files read and understood
- Any ambiguities or blockers found
- Confirmation: "I have read X, Y, Z and understand the full context"

**Before proposing any new model, table, or module:** grep the codebase for similar concepts. If a table or module doing the same job already exists under a different name, flag it and propose consolidation instead of addition. Check `docs/ROADMAP.md` — "Constraints & decisions" section — for architectural decisions that constrain this feature.

**If the feature touches more than 4 files or has multiple distinct user-facing flows:** pause after research and present a step breakdown for user approval before writing any plan files. Do not jump straight to writing plans.

If a blocker is found (missing spec, unclear requirement), surface ONE focused question, then stop and wait.

## Phase 2 — Plan

Goal: produce a written plan the user can verify before any implementation begins. No code written here.

**Single feature:** Write one file — `docs/plans/YYYY-MM-DD-<slug>.md`.

**Re-architecture or multi-step feature (4+ sequential steps):** Write one file per step — `docs/plans/YYYY-MM-DD-<slug>-step1-<name>.md`, `...-step2-<name>.md`, etc. Each step must be independently implementable and shippable. Do not put everything in one file — the user will implement steps one at a time and needs each plan to stand alone.

Follow `docs/WRITING_DOCS.md` conventions (frontmatter with `type: plan`, `last_verified`, `owner: hataf`). Structure:

```markdown
# Plan: <feature name>

## What this does
One paragraph. What the feature does from a user/API perspective.

## Why
Why this is being built (from roadmap/context).

## What changes

### Backend
- File: `server/src/dars/models.py` — [what changes and why]
- File: `server/src/dars/service.py` — [what changes and why]
- ...

### Frontend
- File: `webapp/...` — [what changes and why]

### DB
- Migration: `server/src/dars/migrations/YYYYMMDDHHMMSS_description.sql`
  - [exact SQL or description]

### Tests
- File: `server/tests/test_*.py` — [what scenarios are covered]

## Bead
- ID: `feat-<slug>`
- Title: <title>
- Category: feature

## Risks & constraints
- [any gotchas, ordering dependencies, edge cases]

## E2E test scenarios
- [list of user-facing flows to verify via Chrome MCP]
```

After writing the plan, output a short summary:
> "Plan written to `docs/plans/<filename>`. Review it and say **go** to implement, or give feedback."

Then **stop and wait** for user confirmation.

## Phase 3 — Implement

Triggered when user says **go** (or any affirmative after the plan).

**Steps:**
1. Open bead — append to `.beads/status.jsonl` with `status: "in_progress"`
2. Create git branch — `git checkout -b feat/<slug>`
3. Implement all backend changes per the plan
3a. Before writing new tests, grep `server/tests/` for any test that hits the changed endpoints. Read those tests and update them if the API contract changed. Do not run `make test` cold with stale tests.
4. Write migration if needed — follow naming conventions
5. Write/update tests — run `make test`, fix until green
5a. **If the plan has a Frontend section — implement all frontend changes now.** Do not close the bead or announce completion until every frontend item in the plan is done.
6. Run `make dev` (or equivalent) to start the server
7. **E2E with Playwright MCP** — execute every scenario listed in the plan's "E2E test scenarios" section:
   - Use the Playwright MCP tools (available in the tool list) to drive the browser
   - Navigate, interact, assert visible state
   - Screenshot on failure
8. Update `docs/conventions.md` if new gotchas were discovered
9. Append to `.beads/failures.jsonl` if any failure was encountered and resolved
10. Close bead — append closed row with resolution
11. Update `docs/plans/README.md` to add the new plan
12. Commit — descriptive message on the feature branch
13. Remove item from roadmap "Up next" if fully done
14. **Railway deployment check** (after PR is merged to staging):
    - Use ToolSearch to load Railway MCP tools (`mcp__Railway__list-deployments`, `mcp__Railway__get-logs`)
    - Find the latest deployment for the staging service
    - Poll until status is SUCCESS or FAILED (check every ~60s)
    - On SUCCESS: fetch logs and confirm the migration SQL file ran (grep for the migration filename in logs)
    - On FAILED: fetch logs, report the error — do not close the bead until deployment succeeds
    - Never skip this step — Railway is prod-equivalent and migration failures must be caught immediately

## Rules

- Never write code before Phase 1 is complete
- Never start Phase 3 before user approves the plan
- Never commit with failing tests
- Always run e2e tests via Chrome MCP before closing the bead
- If Playwright MCP is unavailable, note it explicitly and do not claim e2e was verified

## Token efficiency rules

- Read files once, extract what's needed, do not re-read
- Batch independent reads in parallel tool calls
- Do not narrate file contents back — summarize findings in one sentence per file
- Do not re-explain the plan when starting implementation — just execute
