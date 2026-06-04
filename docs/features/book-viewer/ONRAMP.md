# Book Viewer — onramp

You are a Claude agent picking up the **Book Viewer** feature. This file is your single
entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute any code, open beads, or write files until you have read everything
this file lists.

## Step 1 — Read these files, in this exact order
1. `dars/CLAUDE.md` (project rules 1–15)
2. `docs/features/book-viewer/README.md`
3. `docs/features/book-viewer/01-decision-log.md` (D-1…D-6 — canonical)
4. `docs/features/book-viewer/02-data-model.md` (no schema change; response shape)
5. `docs/features/book-viewer/03-phase-1-book-viewer.md` (the one phase)

## Step 2 — Document precedence
```
1. 01-decision-log.md   (D-N references are canonical)
2. 02-data-model.md     (response shape is ground truth)
3. phase docs           (specs derived from above)
4. running code         (last; code may be stale)
```

## Step 3 — Who you are in this conversation
- One phase, one bead (`feat-book-viewer-phase-1`), one PR target `staging`. NEVER main.
- After merge, watch BOTH Railway deploys (server `dars` + webapp) since both change.
- Treat the decision log as frozen.

## Step 4 — Conversational style (verbatim)
- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X").
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended.
- Commit + push + open PR is ONE flow.
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state

**As of 2026-06-04 — Phase 1 in flight (single PR).**

| Feature | Status |
|---|---|
| Plan written + approved | ✅ |
| F-1.1 backend `GET /books/{id}/tree` | ⬜ |
| F-1.2 frontend types + `getBookTree()` | ⬜ |
| F-1.3 rendered view enrichment | ⬜ |
| F-1.4 raw JSON collapsible | ⬜ |

**Next thing to do:** open bead `feat-book-viewer-phase-1`, branch from `staging`,
implement F-1.1 → F-1.4 in order, single PR. The seed G1 English book is the only real
book to test against (id in `server/src/dars/seeds/book_dars_english_g1.py`).

## Step 6 — Where to find supporting context
- Book API today: `server/src/dars/v2_api/router_book.py` + `schemas_book.py`
- Book page today: `webapp/app/dashboard/curriculum/books/[book_id]/page.tsx`
- API client: `webapp/lib/dars-api.ts` (`books` section ~L793)
- Seed book: `server/src/dars/seeds/book_dars_english_g1.py`
- Beads: `.beads/status.jsonl` · Memory: `~/.claude/projects/-home-hataf-taleemabad-dars/memory/`

## Step 7 — Things to ask the user before acting
- Production deployment (default no)
- Any schema change (this feature has none — flag if one becomes necessary)
- Re-seeding

## Step 8 — How to start as a fresh agent
1. Read this onramp + the Step 1 files.
2. Read `03-phase-1-book-viewer.md` end to end.
3. Open bead `feat-book-viewer-phase-1`.
4. `git fetch origin staging && git checkout -b feat/book-viewer origin/staging`.
5. Implement F-1.1 → F-1.4 in order.
6. Update Step 5 here + close bead when staging is green on both services.

## Step 9 — Keep the plan files alive (HARD RULE)
- Land a feature → update Step 5 in the SAME PR.
- New decision the plan didn't anticipate → add `D-N` to the decision log.
- Response shape changes → update `02-data-model.md`.
- Self-check before closing the bead: Step 5 current, no stale specs, decisions logged,
  a fresh agent could resume from this file alone.
