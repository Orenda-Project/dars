---
name: feature
description: Plan-first, phase-based workflow for any feature. Plan together, divide into phases, write an onramp file, then execute. Scales from one-session changes to multi-week rebuilds.
trigger: /feature
---

# /feature

**Plan → phases → onramp → execute.** Every feature, regardless of size. The discipline is the same; it scales with the work.

This is not "research before you code." This is "produce a frozen plan, a decision log, and an onramp file that any future Claude can read cold to pick up exactly where you left off." Each feature lives in its own folder under `docs/features/<slug>/` — plan, onramp, decision log, all colocated. Small features get small folders; big rebuilds get bigger ones. The shape is identical.

## Invocation

```
/feature <name-or-description>
```

---

## Sizing the work (first thing to do)

Before producing any plan, eyeball the work's scale. This decides how heavyweight the feature folder is, **not whether to make one**.

| Size | Signal | Feature folder contents |
|---|---|---|
| **S** | one PR, half a day, no schema change | `ONRAMP.md` + `README.md` + `01-decision-log.md` (often near-empty) + one phase doc |
| **M** | 2–3 PRs, a few days, maybe a small schema delta | `ONRAMP.md` + `README.md` + `00-glossary.md` + `01-decision-log.md` + one phase doc per PR |
| **L** | 4+ phases, weeks, schema/data-model changes | full folder: `ONRAMP.md` + `README.md` + `00-glossary.md` + `01-decision-log.md` + `02-data-model.md` + per-phase docs + reference specs |

If you're not sure, ask the user **one focused question** about scope, then size from the answer.

---

## Phase 1 — Plan production (no code)

Goal: a frozen feature folder at `docs/features/<slug>/` containing everything a fresh Claude needs to pick up the work cold. The folder slug is short and stable (e.g. `auto-fork-on-cst-create`, not `2026-05-19-auto-fork-on-cst-create`) — features get renamed less often than dated plans, and you'll be referencing the slug in PRs and beads.

### Files to produce, in this order

1. **`README.md`** — index. Two paragraphs of "what this feature does" + a numbered list linking to all the other docs in this directory.

2. **`00-glossary.md`** *(M and L; for S, only if the feature introduces a new concept)* — every Term-Capitalised-Word used in later docs gets a definition here. Tables, fields, conceptual entities. **Hard rule:** future docs may only use terms defined here. If a new term emerges mid-execution, add it.

3. **`01-decision-log.md`** *(always)* — every architectural decision indexed `D-1`, `D-2`, … with **rationale** and **when decided**. For S features this might be 1–3 entries. For L it grows to dozens. Format per entry:

    ```
    **D-N: <one-line decision>.** *Rationale:* <why>. *Apply:* <where/when>. *Decided:* <PR # or date>.
    ```

4. **`02-data-model.md`** *(M if schema changes; L always)* — final schema. Every table, column, FK, index, migration order. Ground truth for the DB. Migration SQL cites this doc; the doc cites the SQL.

5. **`03-phase-1-*.md`** through **`0N-phase-N-*.md`** *(always; might be just one for S)* — one file per phase. Each contains numbered **features** (F-N.1, F-N.2, …) with **Spec** + **Acceptance** + **Dependencies on earlier features**. Each phase must be **independently shippable to staging**.

6. **`0N-reference-*.md`** *(if integrating external services)* — frozen external API specs. Copy the relevant endpoint shapes verbatim so future agents don't leave the plan to integrate.

### Document precedence (paste into the feature's `README.md`)

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (schema is ground truth, if present)
3. 00-glossary.md             (terminology, if present)
4. phase docs                 (specs derived from above)
5. running code               (last; code may be stale)
```

If two docs disagree, this is the order. Code is **lowest** authority. Surface conflicts; don't silently pick a side.

### Plan-file hard rules

- **Decisions are frozen.** To revise: ask the user, then mark the old as "Superseded by D-N+1 on YYYY-MM-DD"; the new references the supersession. Never overwrite — both stay.
- **Decision log grows.** Don't truncate.
- **Migration SQL is the source of truth for schema state.** If a migration adds a column, `02-data-model.md` reflects it in the same PR.
- **Don't reformat plan files you don't need to change.** Diffs are substantive.

### Output of Phase 1

Write all the files. End with:

> "Feature folder at `docs/features/<slug>/`. Index: `docs/features/<slug>/README.md`. Review the **decision log** first — that's the load-bearing piece. Say **go** to begin execution, or give feedback."

**Stop and wait** for user confirmation.

---

## Phase 2 — Author the onramp

After plan approval, write `ONRAMP.md` **inside the same feature folder** (`docs/features/<slug>/ONRAMP.md`). This is what a future Claude reads first to pick up cold.

Top-level convenience: maintain a `docs/features/README.md` index that lists active and closed feature folders with one-line statuses. Update it in the same PR as the feature's first commit.

### Naming

Always `ONRAMP.md` inside the feature folder. One feature, one onramp, colocated with its plan.

If a feature is a sub-effort of a larger in-flight effort (e.g. a phase of a rebuild), the larger effort's folder owns its own `ONRAMP.md` and the sub-feature is a phase doc inside that folder. Don't create parallel onramps for the same effort.

### Onramp structure (copy this; trim sections that don't apply for S features)

```markdown
# <Onramp name> — for the <feature> work

You are a Claude agent picking up an in-flight effort. This file is your
single entry point. Reading it (and the files it lists) gives you the
full context.

You will NOT execute any code, open beads, or write files until you
have read everything this file lists.

## Step 1 — Read these files, in this exact order
1. project CLAUDE.md
2. docs/features/<slug>/README.md
3. docs/features/<slug>/00-glossary.md (if present)
4. docs/features/<slug>/01-decision-log.md
5. docs/features/<slug>/02-data-model.md (if present)
6. The phase file for the currently-active phase (see Current state)
7. Reference files for the phase's external integrations

## Step 2 — Document precedence
[paste the precedence block from Phase 1]

## Step 3 — Who you are in this conversation
- Implement phases sequentially. One bead per phase.
- PRs target the user's staging branch. NEVER main.
- After every merge, watch BOTH deploys (server + webapp if relevant).
- Treat the decision log as frozen.

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X").
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Use sub-agents for exploration (>3 search queries); synthesise yourself.
- Commit + push + open PR is ONE flow.
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state
[table of phases with ✅/🟡/⬜ status, PR history, plus a
"Next thing to do" line — future agents READ THIS FIRST]

## Step 6 — Where to find supporting context
[sibling repos, beads file, memory location, graph report]

## Step 7 — Things to ask the user before acting
- Production deployment (default no)
- Schema changes not in 02-data-model.md
- New external dependency
- Re-seeding

## Step 8 — How to start a phase as a fresh agent
[6-step recipe: read onramp, read phase file, open bead, branch from
staging, implement features in order, update Current State + close bead]

## Step 9 — Keep the plan files alive (HARD RULE)
[when to update what; failure mode to avoid; self-check before
closing a bead]
```

### The two load-bearing parts

- **Step 5 Current state table** — what's done, what's in flight, what's next. If stale, the next session walks blind. **Update it in the same PR as the feature**, not as a follow-up.
- **Step 9 plan-alive discipline** — the rule that prevents drift. Decisions get logged, glossary updated, data model in sync. Without this, the plan becomes fiction.

For S features that ship in one session, Step 5 might just be "in flight; will be ✅ after PR #N merges". That's fine — it's the *habit* of writing it that matters.

### When a feature ships

After the close-out PR merges and the deploys are green, edit `docs/features/<slug>/ONRAMP.md` to mark the feature ✅ Closed, and update `docs/features/README.md` to move the entry to the Closed section. The folder stays as-is — it's the historical record of what was decided and how.

---

## Phase 3 — Execute, one phase per bead

Now code can be written.

### For each phase

1. **Open the phase's bead.** `feat-<slug>-phase-N-<phase-slug>`. Append to `.beads/status.jsonl` with `status: "in_progress"`. For S features, a single bead is fine.
2. **Branch from staging.** `git fetch origin <staging-branch> && git checkout -b feat/<slug>-phase-N-<phase> origin/<staging-branch>`. **Never main.**
3. **Implement features in numbered order.** F-N.1, F-N.2, … Acceptance criteria in the phase doc.
4. **PRs target staging.** The user's parking branch (`staging`, or a feature integration branch — check). Never main, never production.
5. **After every PR merges, watch BOTH deploys.** Server + webapp if both changed. Don't claim a feature done until Railway shows SUCCESS on the new commit. Use ToolSearch to load `mcp__Railway__list-deployments` if needed.
6. **Update Step 5 Current state in the onramp file in the same PR.** Non-negotiable.
7. **When the phase's last feature lands and staging is green:**
   - Mark the phase ✅ in the onramp's Step 5
   - Close the phase's bead
   - If follow-ups or known limitations, append to the phase doc under a `## Notes from execution` section (don't alter the original spec)
   - Open the next phase's bead if proceeding

### Inside a phase — the small disciplines

- **One question at a time.** When a design question emerges, use `AskUserQuestion` with 2–4 options + a Recommended. Wait. Then the next.
- **Spawn sub-agents for exploration.** >3 search queries → Explore agent. Synthesise yourself; don't delegate decisions.
- **Spawn sub-agents in parallel for independent work.** If two features don't touch overlapping files, run two background Agent tasks. Audit conflicts before merging.
- **Use worktrees for parallel agents.** `isolation: "worktree"` on the Agent tool. Auto-cleans if the agent makes no changes.
- **Migration files are append-only.** Never edit a merged migration. Write a new one that fixes the broken state.
- **Re-seed when the seed shape changes.** A one-shot SQL migration that soft-deletes existing demo data; next deploy's seed rebuilds.
- **Auto-derive when there's a chain.** If your feature creates derived state (template → instance, global → org → class), build the auto-derivation on create. Don't make the user click through three pages for a usable state.

---

## Phase 4 — Plan-alive discipline (HARD RULE during execution)

The plan files are **living documents**. This is what makes the work survive across sessions.

### Update triggers

| When you… | Update… |
|---|---|
| Land a feature on staging | onramp Step 5 (same PR) |
| Complete a phase | Mark ✅ in onramp; close bead; append `## Notes from execution` if needed |
| Make a decision the plan didn't anticipate | Add `D-N` to `01-decision-log.md` (rationale + when + who) |
| Supersede an old decision | Amend old: "Superseded by D-N+1 on YYYY-MM-DD"; new references the supersession. **Both stay.** |
| Change the data model | Update `02-data-model.md` in the same PR as the migration SQL |
| Introduce a new term | Add to `00-glossary.md` |
| Find a mistake in any plan file | Fix immediately (don't carry forward) |
| Change scope mid-phase | Revise the feature's Spec + Acceptance in the phase doc; add inline "Scope change YYYY-MM-DD" note |

### What NOT to do

- Don't rewrite history. Superseded decisions stay.
- Don't truncate the decision log to keep it short. It grows.
- Don't reformat plan files you don't need to change.

### Self-check before closing any phase's bead

- [ ] Current State in the onramp reflects the new completed state
- [ ] Phase doc has no stale specs (scope changes documented inline)
- [ ] Any new decisions are in the decision log
- [ ] Any new terms are in the glossary
- [ ] `02-data-model.md` (if present) matches the actual schema
- [ ] A fresh agent reading the onramp would correctly identify what to do next

If any check fails, fix before closing.

---

## Phase 5 — Cross-session handoff

The superpower: **any session can pick up the work.**

### Fresh session opening

The agent reads the onramp end to end. Reads the files Step 1 lists. Skims the active phase doc. Cross-checks `.beads/status.jsonl` against the onramp's Current State; the bead wins (onramp is the human-readable summary, bead is the truth for what's in flight).

Then either resumes where the previous session left off, OR asks ONE focused question if something is genuinely ambiguous. Does NOT re-derive decisions in the log — those are settled.

### Session close

- Updated onramp Step 5 to reflect any feature shipped or any blocker hit
- Any new decision logged
- Any new term in the glossary
- Any data model change reflected in `02-data-model.md`
- Any partial work documented in `.beads/status.jsonl` (don't leave silent half-done state)

If a session ends mid-feature, leave a one-paragraph "where I am" note appended to the active phase doc under `## In flight (cleanup on resume)`.

---

## Rules

- **Never start Phase 3 (code) before the user approves the plan files.**
- **Never edit a frozen decision without an explicit user OK + a "Superseded by" entry.**
- **Never push to main.** Features live on a staging branch.
- **Never close a phase's bead before staging is green on both services.**
- **Never claim a feature done without watching the Railway deploys.** Use `mcp__Railway__list-deployments` after merge.
- **Always update the onramp's Current State in the same PR as the feature.** Not as a follow-up.
- **One question at a time** via AskUserQuestion when a design call is needed.
- **Default mode: autonomous.** User redirects if needed.

---

## Token efficiency

- Read files once. Extract what's needed. Don't re-read.
- Batch independent reads in parallel tool calls.
- Don't narrate file contents back. Summarise findings in one sentence per file.
- Don't re-explain the plan when starting implementation — just execute.
- Don't ask the user to re-confirm decisions already in the log.

---

## When this skill applies

**Always.** Every feature, every fix that touches more than one file, every change with a non-obvious decision. The size dial scales the plan and onramp, but the discipline is the same.

If you genuinely need to make a one-line change and ship it immediately (typo fix, copy tweak), you can skip Phase 1's plan production — but still open a bead and run the rest. The plan-alive discipline applies even there: if you discover something while typing, log it.
