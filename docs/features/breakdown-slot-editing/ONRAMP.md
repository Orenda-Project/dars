# ONRAMP — for the breakdown-slot-editing work

You are a Claude agent picking up an in-flight effort. This file is your single entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute any code, open beads, or write files until you have read everything this file lists.

## Step 1 — Read these files, in this exact order

1. `dars/CLAUDE.md` — project rules (critical: rules 1–15). You should already have this loaded by the harness; re-skim for the autonomous-mode + no-narration rules.
2. `docs/features/breakdown-slot-editing/README.md` — index + sizing + document precedence.
3. `docs/features/breakdown-slot-editing/00-glossary.md` — three terms specific to this feature; inherits the v2 rebuild's glossary.
4. `docs/features/breakdown-slot-editing/01-decision-log.md` — frozen design calls (D-1..D-9).
5. `docs/features/breakdown-slot-editing/03-phase-1-slot-editing.md` — the only phase. F1.1..F1.4 in order.
6. `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md` — schema reference for `breakdowns`, `breakdown_chapters`, `breakdown_slots`, `breakdown_slot_topics`. NO schema changes here; just for cross-reference.
7. `webapp/app/dashboard/breakdowns/[breakdown_id]/page.tsx` — the file you'll rewrite the side panel inside.
8. `server/src/dars/v2_api/router_breakdown.py` — read the slot endpoints (`add_slot`, `update_slot`, `delete_slot`, `set_slot_anchor`) once to confirm their bodies match what the client wrappers will send.
9. `server/src/dars/v2_api/lp_types.py` — the constant table you'll port into `webapp/lib/slot-types.ts`.

Skim, don't memorize. The plan exists for you to come back to.

## Step 2 — Document precedence

If two documents disagree, this is the order of authority:

```
1. 01-decision-log.md         (D-N references are canonical)
2. v2 rebuild 02-data-model.md (schema ground truth — no changes here)
3. 00-glossary.md             (terminology)
4. 03-phase-1-slot-editing.md  (specs derived from above)
5. running code                (last; code may be stale)
```

If you find a real conflict, surface it; don't silently pick a side.

## Step 3 — Who you are in this conversation

- Single-phase feature. One bead: `feat-breakdown-slot-editing`. One PR.
- PR targets `staging`. NEVER `main`. NEVER prod.
- After merge, watch BOTH Railway services (server: `dars`; webapp: `truthful-renewal`). Server is unchanged but the webapp deploy must go green before the bead closes.
- Decisions D-1..D-9 are frozen. If you believe one is wrong, raise it with the user before acting.

## Step 4 — Conversational style (verbatim)

- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X").
- One design question at a time via `AskUserQuestion` with 2–4 options + a Recommended.
- Sub-agents for exploration only (>3 search queries). Synthesise yourself.
- Commit + push + open PR is ONE flow.
- After merge, watch deploys without being asked.
- Re-read a file before editing if you edited it earlier this session.
- Say "gg" when something works; "chammaar" when it breaks.

## Step 5 — Current state

**As of 2026-05-20 — ✅ Closed. PR #84 merged 11:16Z, Railway webapp deploy 25aee0b6 SUCCESS on commit eab2ee2.**

| Item | Status |
|---|---|
| Plan written | ✅ |
| Plan reviewed by user | ✅ approved 2026-05-20; D-9 added to capture fork-isolation guarantee |
| Bead `feat-breakdown-slot-editing` | ✅ closed 2026-05-20 |
| F1.1 — dars-api.ts wrappers | ✅ `addSlot`, `patchSlot`, `deleteSlot` on `breakdowns` namespace |
| F1.2 — side-panel editor | ✅ `SlotEditor` component (slot/lp_type combo dropdown, topic dropdown, atomic PATCH save, Delete); `slot-types.ts` lib |
| F1.3 — + Add slot per chapter | ✅ button in chapter header (org draft only); auto-selects new slot |
| Local typecheck | ✅ `tsc --noEmit` clean |
| PR | ✅ #84 merged 2026-05-20 11:16Z |
| Railway webapp deploy | ✅ 25aee0b6 SUCCESS on commit eab2ee2 |
| F1.4 — staging UI smoke | 🟡 hand-off: page returns HTTP 200; manual click-through pending user session |

**Status:** shipped to staging. Server was SKIPPED (no watched files changed); webapp deploy green. UI walkthrough by the user on `https://dars-fe-stage.up.railway.app/dashboard/breakdowns/<draft-org-id>` is the only remaining verification.

## Step 6 — Where to find supporting context

| If you need… | Look here |
|---|---|
| Backend slot endpoints | `server/src/dars/v2_api/router_breakdown.py:683-887` (add_slot → set_slot_anchor) |
| Slot schemas | `server/src/dars/v2_api/schemas_breakdown.py:108-128` (BreakdownSlot{Create,Update}) |
| Allowed slot_type / lp_type | `server/src/dars/v2_api/lp_types.py` |
| Existing webapp client | `webapp/lib/dars-api.ts` — search `patchSlotAnchor` for the URL prefix pattern |
| Topic endpoint (for the dropdown) | `server/src/dars/v2_api/router_book.py:178` (`GET /api/v2/topics?book_chapter_id=...`); client wrapper at `dars-api.ts:752` |
| Fork semantics (D-9 background) | `server/src/dars/breakdown/fork_service.py` (flat copy at fork-time) |
| Active beads | `.beads/status.jsonl` |
| User preferences and journal | `~/.claude/projects/-home-hataf-taleemabad-dars/memory/` |

## Step 7 — Things to ask the user about before acting

- Anything that requires touching the schema (you shouldn't — but if you find you do, ask).
- Anything that propagates org edits into existing class breakdowns (D-9 forbids this in this PR).
- Anything that enables editing of published breakdowns (D-8 defers it).
- A new external dependency on the webapp (DnD library, etc — out of scope per the per-slot-only sizing).

For everything else: act autonomously and report results.

## Step 8 — How to start the phase

1. Read this file end to end (re-skim if it's been a while).
2. Read the phase doc end to end.
3. Append a bead entry to `.beads/status.jsonl`:
   ```json
   {"id": "feat-breakdown-slot-editing", "title": "Webapp: per-slot editing in the org breakdown editor (slot_type, lp_type, topic_id, add/delete)", "status": "in_progress", "priority": "medium", "created": "2026-05-20", "updated": "2026-05-20", "category": "feature", "resolution": null, "blocked_by": null, "owner": "hataf"}
   ```
4. Branch from `staging`: `git fetch origin staging && git checkout -b feat/breakdown-slot-editing origin/staging`.
5. Implement F1.1 → F1.2 → F1.3 in order. Each one compiles before the next.
6. Local typecheck (webapp): `pnpm --filter webapp tsc --noEmit` (or whatever the repo's convention is — check `webapp/package.json`).
7. Commit, push, open PR against `staging`. Wait for the user's "merge it" / "ship it".
8. After merge: poll Railway (server unchanged but webapp must go green). Run F1.4. Update Step 5 above. Close the bead.

## Step 9 — Keep the plan files alive (HARD RULE)

- When F1.1, F1.2, or F1.3 lands on staging, mark it ✅ in Step 5 of this file **in the same PR as the work**, not as a follow-up.
- If a new design decision emerges mid-implementation, add it as D-10 in `01-decision-log.md` with rationale + when + who decided.
- If a new term emerges, add it to `00-glossary.md`.
- If scope changes inside a feature, append a "Scope change YYYY-MM-DD" note inline in the phase doc — do not rewrite the original spec.
- Never reformat plan files you don't need to change.

### Self-check before closing the bead

- [ ] Step 5 Current State reflects all features ✅
- [ ] No stale specs in the phase doc (scope changes noted inline)
- [ ] Any new D-N entries are in the decision log
- [ ] Any new terms in the glossary
- [ ] Both Railway deploys (or just webapp if server unchanged) showed SUCCESS on the merge commit
- [ ] F1.4 acceptance items all pass on staging
