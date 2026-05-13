# Harness Improvements

---
## 2026-05-07 Session retrospect

Session was clean — no work performed beyond `/retrospect` itself. Nothing to flag.

---
## 2026-05-12 Session retrospect

### Issues & suggestions

```
ISSUE: Webapp architecture intent not captured anywhere in harness
ROOT CAUSE: No doc or memory entry describes the webapp's two-part purpose. User had to explain the full vision mid-session.
FIX: Add webapp architecture intent to CLAUDE.md under a "Webapp Architecture" section.
PRIORITY: high
```

```
ISSUE: Teacher app vision discussed but not persisted
ROOT CAUSE: Product decisions (/teacher-app route, scope, purpose) happened in conversation but nothing captured them.
FIX: Write to docs/context/ or CLAUDE.md so next session starts with this knowledge.
PRIORITY: high
```

```
ISSUE: Auto-memory writes outside the dars git repo (~/.claude/projects/...)
ROOT CAUSE: The global auto-memory harness stores project context in a user-level directory, not in the repo. This means it's unversioned, not shared, and violates the principle that all harness lives inside the project.
FIX: Add rule to CLAUDE.md — "Never write project context to ~/.claude/. All memory, notes, and context go inside the repo (docs/, .claude/, .beads/)." Disable or ignore auto-memory for this project.
PRIORITY: high
```

```
ISSUE: Spawned Explore agent for a product-intent question that didn't need file reads
ROOT CAUSE: "Is the webapp aligned with X?" was a product question answerable from conversation context. Agent was overkill.
FIX: Add heuristic to CLAUDE.md — for alignment/intent questions, answer from known context first; only read files if the answer depends on implementation details not already described.
PRIORITY: medium
```

---
## 2026-05-13 Session retrospect

### Issues & suggestions

```
ISSUE: User had to explicitly ask to break the single plan into 8 separate step plans
ROOT CAUSE: /feature skill writes one plan file. For a large re-architecture with sequential steps, one file is wrong — each step should be independently implementable.
FIX: Add to /feature skill SKILL.md Phase 2 instructions: "For re-architectures or multi-step features with 4+ sequential steps, write one plan file per step in docs/plans/ rather than one monolithic plan."
PRIORITY: high
```

```
ISSUE: Plan mode auto-exited mid-session while still writing plan files
ROOT CAUSE: ExitPlanMode was not called — plan mode exited when user message came in during file writing. Caused confusion about planning vs executing state.
FIX: Add to CLAUDE.md: "When writing multiple plan files during plan mode, batch all writes in one turn then call ExitPlanMode. Never let plan mode exit implicitly mid-work."
PRIORITY: medium
```

```
ISSUE: 3 parallel Explore agents for codebase audit produced very verbose output, bloating context
ROOT CAUSE: Agent prompts did not constrain output verbosity.
FIX: Add standing rule to Explore agent prompts in /feature skill: "Be terse — one line per model field, one line per endpoint. No prose explanations."
PRIORITY: medium
```

```
ISSUE: Plan mode working file goes to ~/.claude/plans/ (outside repo) — no rule explaining this
ROOT CAUSE: Plan mode tooling hardcodes the working file path. Claude had no guidance on this.
FIX: Add to CLAUDE.md: "Plan mode writes its working scratch file to ~/.claude/plans/ — this is system-controlled and fine. All real plan artifacts go in docs/plans/."
PRIORITY: low
```

```
ISSUE: Supabase migration path baked into 7 plan files, required mass sed replacement
ROOT CAUSE: docs/conventions.md still had supabase/migrations/ when plans were written. User had to point it out.
FIX: Already corrected in conventions.md. No further action needed.
PRIORITY: low (resolved)
```

---
## 2026-05-13 Session retrospect (3)

### Issues & suggestions

```
ISSUE: Claude was about to move to Step 2 without completing the frontend changes for Step 1
ROOT CAUSE: /feature skill Phase 3 steps do not explicitly require frontend changes to be done before closing the bead or moving on. Agent completed backend + tests and closed the bead; Claude treated Step 1 as done.
FIX: Add to /feature SKILL.md Phase 3, after step 5 (Write/update tests):
  "5a. If the plan includes a Frontend section — implement all frontend changes now. Do not close the bead or announce completion until the Frontend section is fully done."
PRIORITY: high
```

```
ISSUE: Claude said "I can't access Railway directly" before checking deferred tools (carried over — fix applied this session)
ROOT CAUSE: Already resolved — CLAUDE.md rule 8 added.
FIX: Already applied. Monitor next session.
PRIORITY: resolved
```

---
## 2026-05-13 Session retrospect (2)

### Issues & suggestions

```
ISSUE: Claude told user "I can't access Railway directly" despite Railway MCP being configured and available
ROOT CAUSE: Claude did not check the deferred tools list before claiming a capability was unavailable.
  Railway MCP tools appear in the system-reminder deferred tools list but require ToolSearch to load
  their schema before use. Claude skipped this check and defaulted to "I don't have access."
FIX: Add to CLAUDE.md under "Critical Rules":
  "Before telling the user you cannot do something (access a service, read a variable, etc.),
  check the deferred tools list in the system-reminder. If a relevant MCP tool exists there,
  use ToolSearch to load it and proceed. Never claim a capability is unavailable without checking."
PRIORITY: high
```

---
## 2026-05-13 Session retrospect (4)

### Issues & suggestions

```
ISSUE: User had to say "do it one by one" after asking for steps 2, 3, 4 in one message
ROOT CAUSE: No rule in /feature skill or CLAUDE.md preventing batching of multiple sequential re-architecture steps into a single implementation run.
FIX: Add to /feature SKILL.md Phase 1 rules: "If the user asks to implement multiple numbered steps (e.g. 'steps 2, 3, 4'), confirm you will do them sequentially one at a time. Never batch sequential re-architecture steps — each step must be complete and deployed before the next begins."
PRIORITY: medium
```

```
ISSUE: /feature research phase re-read all source modules even though a complete plan already existed in docs/plans/
ROOT CAUSE: Phase 1 instructions say "read all modules the feature will touch" without first checking for an existing plan. When a plan already exists, most of the module reading is redundant.
FIX: Add to /feature SKILL.md Phase 1 as step 0: "Before reading source files, check docs/plans/ for an existing plan matching this feature slug. If a complete plan exists, read it first — skip module reads that are already covered by the plan, only read files needed to validate correctness."
PRIORITY: medium
```

```
ISSUE: Migration filename in pre-written Step 2 plan was stale (000002, already taken by init_clean.sql)
ROOT CAUSE: Plan files are written at a point in time; migration sequence numbers get taken by later migrations, making plan filenames stale.
FIX: Add to /feature SKILL.md Phase 1: "If a plan file already exists, verify its migration filename against ls server/src/dars/migrations/ — the number may have been taken since the plan was written. Update the plan before implementing."
PRIORITY: low
```

```
ISSUE: Test helper _admin_headers() mutated api_key_hash, breaking the original key and requiring a full test rewrite
ROOT CAUSE: No convention documenting that _admin_headers() invalidates the fixture's raw key.
FIX: Add to docs/conventions.md: "Test gotcha: _admin_headers() replaces api_key_hash on the client object, invalidating the original raw key. Tests that need both admin writes and client reads must use two separate client objects — one admin writer, one reader — rather than reusing the same fixture client."
PRIORITY: low
```

---
## 2026-05-13 Session retrospect (5)

### Issues & suggestions

```
ISSUE: Railway deployment verification was not automatic — user had to ask for it explicitly
ROOT CAUSE: /feature SKILL.md Phase 3 had no step for checking Railway after merge. Claude finished the commit and PR, declared "done", and waited. User had to prompt for Railway check.
FIX: Added Step 14 to /feature SKILL.md Phase 3: after PR is merged to staging, use Railway MCP to poll until deployment SUCCESS, confirm migration ran in logs. Do not close bead until deployment succeeds.
PRIORITY: high
```

```
ISSUE: Claude paused twice to "make sure I understand correctly" despite user having set no-clarifying-questions mode
ROOT CAUSE: No standing rule in CLAUDE.md for autonomous execution on this project — the system-reminder directive only applies when active.
FIX: Add to dars/CLAUDE.md Critical Rules: "Default execution mode: autonomous. Never pause to confirm understanding before proceeding — just proceed. The only exception is a genuine blocker (missing spec, missing credential)."
PRIORITY: high
```

```
ISSUE: 11 user interrupts mid-response — Claude was narrating intent before taking action
ROOT CAUSE: Claude writes "I'll now X" or "Let me Y" before tool calls, forcing the user to read narration before anything happens.
FIX: Add to dars/CLAUDE.md: "Never write 'I'll now X' before doing X — just do X. State results after tool calls complete, not intent before them."
PRIORITY: high
```

```
ISSUE: Four test failures on first make test run because existing tests weren't updated when endpoint contracts changed
ROOT CAUSE: Phase 3 has no step to grep for existing tests that exercise the changed endpoints before writing new tests.
FIX: Add to /feature SKILL.md Phase 3 after step 3: "3a. Before writing new tests, grep server/tests/ for tests hitting changed endpoints. Read and update them if the API contract changed. Do not run make test cold with stale tests."
PRIORITY: high
```

```
ISSUE: /retrospect did not catch the Railway verification gap — user had to point it out explicitly
ROOT CAUSE: /retrospect SKILL.md has no criterion for "mandatory workflow steps that were skipped." Railway check is a workflow step, not a bug or correctness issue.
FIX: Add a fifth criterion to /retrospect SKILL.md: "5. Workflow gaps — were any mandatory post-implementation steps skipped? Check: Railway deployment check, bead closed before deployment verified, migration confirmed in logs, e2e tests skipped. Flag each skipped step even if it didn't cause a visible failure."
PRIORITY: high
```

```
ISSUE: Retrospect doesn't cross-check /feature Phase 3 steps against what was actually executed
ROOT CAUSE: Retrospect analyzes conversation output but doesn't compare it against the /feature SKILL.md step list.
FIX: Add to /retrospect SKILL.md: "Read /feature SKILL.md Phase 3 steps. For each step, verify it was executed this session. Flag any step that was skipped or partially done."
PRIORITY: medium
```

```
ISSUE: Duplicate IF NOT EXISTS clause from editing an already-modified file without re-reading it
ROOT CAUSE: Claude applied an edit assuming the file state matched what was written earlier in the session.
FIX: Add to dars/CLAUDE.md: "Before editing a file modified earlier in the same session, re-read it first. Never assume file state matches your earlier write."
PRIORITY: medium
```

```
ISSUE: Railway MCP was never invoked automatically — user manually provided deployment ID and re-sent the ScheduleWakeup prompt
ROOT CAUSE: No instruction says "after PR merge, poll Railway automatically." User had to manage this entirely.
FIX: Covered by Step 14 added to /feature SKILL.md. Additionally add to dars/CLAUDE.md: "After any PR merge this session — if Railway MCP is in deferred tools — immediately list-deployments and begin polling. Do not wait for user to ask."
PRIORITY: high (Step 14 covers implementation; CLAUDE.md covers the default reflex)
```
