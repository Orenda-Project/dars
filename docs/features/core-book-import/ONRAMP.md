# Core Book Import — onramp

You are a Claude agent picking up the **Core Book Import** feature. This file is your
single entry point. Read everything it lists before executing code.

## Step 1 — Read these, in order
1. `dars/CLAUDE.md` (rules 1–15)
2. `docs/features/core-book-import/README.md`
3. `docs/features/core-book-import/00-glossary.md`
4. `docs/features/core-book-import/01-decision-log.md` (D-1…D-8 — canonical)
5. `docs/features/core-book-import/02-data-model.md` (`import_runs` table)
6. `docs/features/core-book-import/03-reference-etl-script.md` (frozen ETL behaviour)
7. The active phase doc (04 backend, then 05 frontend)
8. The proven script being ported: `scripts/import_ncp_english_g1.py` + `scripts/lp_type_classifier.py`

## Step 2 — Document precedence
```
1. 01-decision-log.md   2. 02-data-model.md   3. 00-glossary.md
4. 03-reference-etl-script.md   5. phase docs (04,05)   6. running code
```

## Step 3 — Who you are
- Two phases, one bead each (`feat-core-book-import-phase-1/2`). PRs → `staging`. NEVER main.
- After merge, watch BOTH Railway deploys (server `dars` + webapp).
- Decision log is frozen.

## Step 4 — Conversational style
- Autonomous; no pre-action narration; one design question at a time via AskUserQuestion.
- Commit + push + open PR is one flow. After merge, watch deploys.
- Re-read a file before editing if you edited it earlier this session.

## Step 5 — Current state

**As of 2026-06-04 — Phase 1 in flight.**

| Item | Status |
|---|---|
| Plan written + approved | ✅ |
| F-1.1 `import_runs` migration | ⬜ |
| F-1.2 vendor breakdown prompt + port lp_type classifier (D-4) | ⬜ |
| F-1.3 `GET /admin/core-books` | ⬜ |
| F-1.4 `book_import_service.py` (ported ETL) | ⬜ |
| F-1.5 import endpoints + background job | ⬜ |
| Phase 2 (frontend) | ⬜ |

**Next thing to do:** open bead `feat-core-book-import-phase-1`, branch from `staging`,
implement F-1.1 → F-1.5 in order.

## Step 6 — Supporting context
- Proven ETL: `scripts/import_ncp_english_g1.py`; lp_type: `scripts/lp_type_classifier.py`
- Schema breakdown prompt (to vendor): `/home/hataf/taleemabad/Schema/prompts/english_prompt.txt`
- Core-DB config plumbing: `server/src/dars/config.py` (`effective_core_db_url`)
- Admin auth dep: `server/src/dars/v2_api/deps.py::require_admin`
- Migrations: `server/src/dars/migrations/` (naming `YYYYMMDDHHMMSS_slug.sql`)
- Beads `.beads/status.jsonl` · Memory `~/.claude/projects/-home-hataf-taleemabad-dars/memory/`

## Step 7 — Ask the user before acting
- **Ops (important):** the core-DB env vars (`CORE_DB_URL` or 5× `CORE_STAGING_DB_*`) +
  `ANTHROPIC_API_KEY` must be set on the Dars Railway server for imports to actually run.
  Endpoints return 503 until then (D-7). Do NOT put secrets in git; flag to the user.
- Production deployment (default no) · schema changes beyond `import_runs` · re-seeding.

## Step 8 — Start a phase as a fresh agent
Read onramp → phase doc → open bead → branch from staging → implement F-N.x in order →
update Step 5 in the same PR → watch deploys → close bead when staging green.

## Step 9 — Keep plan files alive (HARD RULE)
Land a feature → update Step 5 same PR. New decision → `D-N`. Schema change → update
02-data-model. New term → 00-glossary. Self-check before closing a bead: Step 5 current,
no stale specs, decisions logged, a fresh agent could resume from this file alone.
