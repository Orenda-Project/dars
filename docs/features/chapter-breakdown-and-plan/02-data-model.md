# Data Model — Chapter Breakdown & Chapter Plan

Two additive schema deltas. No drops, no renames. Ground truth for this feature's DB state; the v2 rebuild `02-data-model.md` (Section 4) remains the base. Migration SQL cites this doc; this doc cites the SQL.

Migrations are **append-only** and run automatically on Railway deploy. Never run DDL manually (CLAUDE.md rule 7). Use `sqlalchemy.types.Uuid` in models, never the PG dialect type (rule 6).

---

## Delta 1 — `breakdown_chapters` gains a date range (Phase 1)

Migration: `server/src/dars/migrations/20260602000000_breakdown_chapters_date_range.sql`

| Column | Type | Notes |
|---|---|---|
| `start_date` | DATE NULL | First calendar day allocated to this chapter. Per D-2 this is the primary editing surface. Nullable so existing rows + un-dated chapters remain valid. |
| `end_date` | DATE NULL | Last calendar day (inclusive). |

- `teaching_days` (existing) is **retained** but per D-2 becomes derived/display once a range is set, not authored. Not dropped — kept for backward-compat and as a fallback when no range is present.
- No new index required for the prototype (chapters per breakdown are few; lookups are by `breakdown_id`).
- Validation (gaps/overlaps/zero-teaching-day ranges) is **advisory** per D-5 — enforced in the service/UI layer, not by DB constraints.

## Delta 2 — `breakdown_slots` gains a page range (Phase 2) — ✅ applied

Migration: `server/src/dars/migrations/20260603000000_breakdown_slots_page_range.sql`

| Column | Type | Notes |
|---|---|---|
| `page_start` | INT NULL | First book page this slot covers (D-4). Nullable — not every slot maps to pages (e.g. revision). |
| `page_end` | INT NULL | Last book page (inclusive). |

- No constraint requiring `page_end >= page_start` at the DB layer for the prototype; validated advisory in the service/UI.
- No new index.

---

## Schema-touching code to update in lockstep

| Layer | File | Change |
|---|---|---|
| ORM model | `server/src/dars/v2_api/models_*` (breakdown models) | add the four nullable columns |
| Read schema | `server/src/dars/v2_api/schemas_breakdown.py` → `BreakdownChapterRead`, `BreakdownSlotRead` | expose new fields |
| Write schema | same file → `BreakdownChapterCreate/Update`, `BreakdownSlotCreate/Update` | accept new fields |

Find exact model file via `graphify query "where is breakdown_chapters model defined"` at implementation time.
