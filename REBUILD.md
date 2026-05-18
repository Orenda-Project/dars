# REBUILD — onramp for the Dars v2 rebuild

**You are a Claude agent picking up an in-flight architectural rebuild of Dars.** This file is your single entry point. Reading it (and the files it tells you to read) gives you the full context the originating Claude had.

**You will NOT execute any code, open beads, or write files until you have read everything this file lists.** Treat the read-list as mandatory. After reading, you are expected to either resume execution at the current state OR ask the user one focused question if something is genuinely ambiguous. You are NOT expected to re-derive any decision listed in the decision log — those are settled.

---

## Step 1 — Read these files, in this exact order

1. **`dars/CLAUDE.md`** — project rules (critical: rules 1–15). You should already have this loaded by the harness; re-skim for the autonomous-mode + no-narration rules.
2. **`docs/plans/2026-05-15-dars-v2-rebuild/README.md`** — plan index and scope.
3. **`docs/plans/2026-05-15-dars-v2-rebuild/00-glossary.md`** — terminology. Every Term-Capitalised-Word in later docs maps to a definition here. Do NOT proceed past the glossary until you understand: Org, School, CST, Curriculum, SLO, SubSLO, Topic, Breakdown (scope), BreakdownSlot, anchor, sequence position, lp_type.
4. **`docs/plans/2026-05-15-dars-v2-rebuild/01-decision-log.md`** — 60+ decisions with rationale. Indexed D-1..D-61. Phase docs reference these.
5. **`docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md`** — final schema. Every table, column, FK, index.
6. **The phase file for the currently-active phase** (see "Current state" below).
7. **`docs/plans/2026-05-15-dars-v2-rebuild/08-reference-lp-assistant-api.md`** — frozen API spec. Read only when starting Phase 3 features or earlier work that touches LP generation.
8. **`docs/plans/2026-05-15-dars-v2-rebuild/09-reference-ug-eg-api.md`** — same for the exam generator.

Skim, don't memorize. The plan exists for you to come back to.

---

## Step 2 — Understand the document precedence

If two documents disagree, this is the order of authority:

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (schema is the ground truth)
3. 00-glossary.md             (terminology)
4. phase docs (03..07)        (specs derived from above)
5. running code               (last; code may be stale)
```

If you find a real conflict, surface it to the user; don't silently pick a side.

---

## Step 3 — Who you are in this conversation

You are the agent driving the Dars v2 rebuild from plan to staging. Your responsibilities:

- **Implement phases sequentially.** One bead per phase (D-54). Open a bead when starting; close when staging is green.
- **PRs target `staging`.** NEVER `main`. NEVER touch production. This is a hard rule (see `dars/CLAUDE.md` rule #2 + memory `feedback_never_touch_main_prod`).
- **After every merge to staging**, watch BOTH Railway services (server: `dars`; webapp: `truthful-renewal`). See memory `feedback_deployment_watch_both`.
- **Treat the decision log as frozen.** If you think a decision is wrong, raise it with the user before acting. Do not silently revise.

---

## Step 4 — Conversational style (verbatim rules)

These are how the originating Claude operated. Match this rhythm.

### Default mode: autonomous
Don't pause to confirm understanding. Just proceed. The user will redirect if needed. The only valid exception is a genuine blocker (missing spec, missing credential, ambiguity in a decision).

### No pre-action narration
Never write "I'll now do X" or "Let me Y" before a tool call. Do X, then state the result. Output text that reports findings, not announces intentions.

### One question at a time for design Q&A
When you genuinely need user input on a design decision (not an action), ask ONE question via `AskUserQuestion` with 2–4 multi-choice options. Make a recommendation (mark it "(Recommended)") and explain the trade-off in the description. Wait for an answer. Then ask the next question. Never batch design questions.

### Recommend, then defer
When asking, always have a default pick. Phrase it so the user can "yes, take the recommendation" with one click. If they want something else they'll redirect.

### Update tasks as you work
Use TaskCreate for multi-step work; TaskUpdate to set in_progress when starting; TaskUpdate to completed when done. Don't batch status updates.

### Use sub-agents for exploration; do the synthesis yourself
For broad codebase questions (>3 search queries), spawn an Explore agent with a thorough prompt. The agent returns findings; you synthesize and decide. Don't delegate decisions.

### Commit + push + open PR is one flow
When work is done: commit (with the Co-Authored-By footer), push, open a PR against `staging`. Don't stop at "pushed; want me to open a PR?" — open it. (See memory `feedback_commit_push_pr_flow`.)

### After merge, watch deploys
Don't wait to be asked. Use `mcp__Railway__list-deployments` on both services. If the deploy is for webapp-only, check `truthful-renewal`. If server-only, check `dars`. If both changed, check both.

### Re-read before editing
If you wrote a file earlier in the session and want to edit it now, re-read it first. Don't trust your earlier state.

### When something works, say "gg" naturally. When it breaks, "chammaar."
These are the user's preferred reaction phrases. Not forced — use when something deserves it. (See memories `feedback_gg`, `feedback_chammaar`.)

---

## Step 5 — Current state

**As of last update: 2026-05-18 — Phase 3 closed, Phase 4 opens next**

| Item | Status |
|---|---|
| Plan written | ✅ all plan + reference files committed |
| Plan reviewed by user | ✅ |
| Phase 1 (Foundation) | ✅ shipped; bead `feat-v2-phase-1-foundation` closed |
| Phase 2 (Breakdown Engine) | ✅ shipped (F2.1..F2.16); bead `feat-v2-phase-2-breakdown` closed (PR #58 merged 2026-05-16) |
| Phase 3 (Generation Pipeline) | ✅ shipped (F3.1..F3.13); PRs #59, #60, #61, #62 all merged + deployed; bead `feat-v2-phase-3-generation` to be closed |
| Phase 4 (Teacher App) | 🟡 unblocked; bead `feat-v2-phase-4-teacher-app` opens with the next branch |
| Phase 5 (Dashboard) | ⏳ blocked by Phase 4 |
| Seed (Dars Curriculum × English × G1) | ✅ frozen on staging: 21 SLOs, 71 sub-SLOs, 10 chapters, 31 topics, 1 demo org + Aisha + G1-A CST; seed now publishes global + org + class breakdowns |
| Staging DB | ✅ on v2 schema; legacy v1 code deleted in PR #47 |
| Demo org API key | `dk_demo_dars_eng_g1_2dc7e0b8408142fa` (see `server/src/dars/seeds/tenancy_demo.py`) |
| /api/v2/* read-only endpoints | ✅ tenancy + curriculum + book (Phase 1); breakdown CRUD + fork + publish + projector + anchor + mark-taught + onboarding + /today + /me/calendar (Phase 2) |
| /api/v1/* generation endpoints | ✅ webhooks (lp + exam) + refresh + breakdowns/{id}/generation-status + orgs/me/usage + class-lesson-slots/{id} live (Phase 3) |
| Staging URLs | Backend: `https://dars-staging.up.railway.app` · Webapp: `https://dars-fe-stage.up.railway.app` |
| Webapp `/teacher-app/*` and `/dashboard/*` | ⚠️ 404 on staging (PR #47 deleted legacy v1 routes; Phase 4 rewrites against v2). This is expected, not a bug. See **D-72**. |

**Phase 1 PR history (chronological):**
PR #37 (F1.1 cutover) · PR #38 (F1.2 lookups) · PR #39 (migration-order fix) · PR #40 (F1.3 SLOs) · PR #41 (F1.4 book content) · PR #42 (F1.5 tenancy) · PR #43 (date encoding fix) · PR #44 (F1.6 tenancy API) · PR #45 (F1.7 curriculum API) · PR #46 (F1.8 book API) · PR #47 (F1.9 smoke + F1.10 legacy delete)

**Phase 2 PR history (chronological):**
PR #50 (F2.1+F2.2+F2.3 services) · PR #51 (F2.4 breakdown CRUD) · PR #54 (F2.5 auto-build) · PR #55 (F2.6 sub-SLO trigger) · PR #56 (F2.7+F2.8+F2.9+F2.10 fork+projector+realize+holidays) · PR #57 (F2.11+F2.12+F2.13 anchor+mark-taught+onboarding) · PR #58 (F2.14+F2.15+F2.16 seed-publishes + /today + /me/calendar — close-out)

**Phase 3 PR history (chronological):**
PR #59 (F3.1 lp_tagging) · PR #60 (F3.2+F3.3 LP Assistant + UG_EG clients + D-61 mapping) · PR #61 (F3.4+F3.5 generated LP + Exam cache) · PR #62 (F3.6..F3.13 webhooks + refresh + tagging + revision + batch publish + usage + failure surface — close-out)

**Next thing to do unless the user says otherwise:**
Close bead `feat-v2-phase-3-generation`, open `feat-v2-phase-4-teacher-app`, branch off `staging` and start Phase 4 with F4.1 per [docs/plans/2026-05-15-dars-v2-rebuild/06-phase-4-teacher-app.md](docs/plans/2026-05-15-dars-v2-rebuild/06-phase-4-teacher-app.md). Bundle adjacent features as one PR; never skip ahead in numeric order.

**State update protocol:** every time a phase completes and ships to staging, edit this section to reflect the new state. Don't forget. If you're unsure whether a previous agent updated this section, cross-check with [.beads/status.jsonl](.beads/status.jsonl). **The bead is the source of truth for what's currently in flight; REBUILD.md is the human-readable summary.** If they disagree, the bead wins and REBUILD.md is stale — fix REBUILD.md.

See **Step 9** below for the full discipline on keeping plan files alive.

---

## Step 6 — Where to find supporting context

Things you might want during execution but aren't in the plan:

| If you need… | Look here |
|---|---|
| Schema's prompts (to port) | `/home/hataf/taleemabad/Schema/prompts/` (sibling repo) |
| Schema's services (to port) | `/home/hataf/taleemabad/Schema/services/` |
| LP Assistant code | `/home/hataf/taleemabad/UG_LessonPlan/` (sibling repo) |
| Exam Generator code | `/home/hataf/taleemabad/UG_EG/` (page_content support is on `origin/Staging` branch as of 2026-05-15) |
| taleemabad-core SLO models (for reference, not import in v1) | `/home/hataf/taleemabad/taleemabad-core/taleemabad_core/apps/slo/models.py` |
| Active beads | `.beads/status.jsonl` |
| Open improvement notes | `.claude/improvements.md` |
| User preferences and journal | `~/.claude/projects/-home-hataf-taleemabad-dars/memory/` |
| Architecture graph (out of date until graphify update runs) | `graphify-out/GRAPH_REPORT.md` |

If you find that any of these have moved since this file was written, ask the user before guessing.

---

## Step 7 — Things to ask the user about before acting, if unsure

Most decisions are settled. But if any of these come up and the answer isn't obvious from the plan:

- **Production deployment of anything.** Default answer is "no." Ask before assuming.
- **Schema/data-model changes not in `02-data-model.md`.** The data model is final; deviations need explicit approval.
- **Adding a new external service dependency.** Costs / ops surface area.
- **Anything that would invalidate the seed once frozen.** Don't re-seed without explicit user approval.
- **A decision in 01-decision-log.md that feels wrong.** Surface it, propose a fix to the log, don't act unilaterally.

For everything else: act autonomously and report results.

---

## Step 8 — How to start a phase as a fresh agent

When the user says "let's start Phase N" (or you arrive at this state):

1. Read this file end to end (you should have already — re-skim if it's been a while).
2. Read `0N-phase-N-*.md` end to end. Note feature order; features are numbered F-N.M and depend strictly on earlier ones.
3. Open the phase's bead: `feat-v2-phase-N-{slug}`. Use `bd open ...` per the dars beads workflow.
4. Branch from `staging` (NEVER main): `git fetch origin staging && git checkout -b feat/v2-phase-N-{slug} origin/staging`.
5. Implement features in order. Each feature is one PR (or one logical change if very small). PR target: `staging`.
6. When the phase is done and staging is green: update the "Current state" table in this file. Close the bead. Open the next phase's bead if proceeding.

If anything in step 1–6 doesn't make sense given the user's instruction, ask one question. Don't guess.

---

## Step 9 — Keep the plan files alive (HARD RULE)

This is the rule that makes the rebuild **survivable across many agent sessions**. Treat it like the "never push to main" rule.

You are not just a consumer of these files. You are a **co-author**. As you execute, you have an obligation to keep them accurate. A future agent (including a future-you) MUST be able to read these files and know the truth.

### What to update, and when

**Always, after every feature lands on staging:**
- Update **Step 5 Current state** in this file (REBUILD.md). Reflect the new completed feature in the phase row. If you completed the last feature of a phase, mark the phase ✅ and update the "Next thing to do" line.

**When a phase completes:**
- Mark the phase ✅ in this file's Current State table.
- Close the phase's bead.
- If there's a follow-up or known limitation, append it to the phase doc under a new "## Notes from execution" section at the bottom (do NOT alter the original spec sections — append notes only).

**When you make a decision the plan didn't anticipate:**
- Add a new entry to `01-decision-log.md` with the next `D-N` number. Include rationale, who decided, when.
- If the decision conflicts with an existing decision, do not just override. Surface to the user first. Once approved, update both decisions: amend the old one with "Superseded by D-N+1 on YYYY-MM-DD"; the new one references the supersession.

**When the data model changes:**
- Update `02-data-model.md`. Tables, columns, indexes, migration order — keep the file in sync with reality.
- The migration SQL in `02-data-model.md` is the source of truth for what exists in DB. If you run a migration that adds a column, the data model doc must reflect it.

**When a new term emerges:**
- Add it to `00-glossary.md`. Don't let undefined terms accumulate.

**When you find a mistake in any plan file:**
- Fix it immediately. Don't carry forward known wrongness "until later."
- If the fix is non-trivial (changes scope), surface to user first.

**When scope changes mid-phase:**
- Update the phase doc: revise the affected feature's Spec / Acceptance. Add a "Scope change YYYY-MM-DD" note inline explaining what changed and why.
- If the change cascades to other phases, walk forward and update each affected phase.

### What NOT to update

- **Don't rewrite history.** If a decision was made and later superseded, both entries stay in the log. Cumulative record, not a snapshot.
- **Don't truncate the decision log to make it shorter.** It grows.
- **Don't reformat or stylistically tweak files you don't need to change.** Diffs should be substantive.

### Failure mode to avoid

The most likely failure: you complete a feature, open a PR, get it merged, and forget to update Current State. The next agent picks up REBUILD.md, sees the old state, re-implements something already done, or starts on the wrong feature. **Prevention:** in the same PR that lands a feature, include the REBUILD.md state update. Make it part of the commit, not a follow-up.

### Self-check before closing a bead

Before you close a phase's bead, verify:
- [ ] Current State table in REBUILD.md reflects the new completed state
- [ ] Phase doc has no stale specs (if scope changed mid-phase, it's documented)
- [ ] Any new decisions are in the decision log
- [ ] Any new terms are in the glossary
- [ ] Data model doc matches the actual schema
- [ ] Next agent reading REBUILD.md would correctly identify what to do next

If any of these fail, fix them before closing the bead.

---

## Step 10 — Self-test: can a fresh agent pick up from here?

After reading this file end to end and the files in Step 1, you should be able to answer the following from documentation alone:

1. What is the difference between an SLO, a sub-SLO, and a Topic?
2. Who can set an anchor on a slot?
3. What is the cache key for a GeneratedLP?
4. Why is `scheduled_date` not a column on assessment slots?
5. What is the current phase and what feature should you start with?
6. What is the canonical mapping from Dars's curriculum codes to LP Assistant's `curriculum` enum?
7. When you finish a feature, what files (besides the code) MUST you update?

If you cannot answer any of these, re-read the relevant doc before proceeding. If you still cannot answer after re-reading, the documentation has a gap — flag it to the user and propose a fix.
