# Phase 1 — Backend: auto-seed + read-only syllabus; delete mutation endpoints

Make the teacher path mirror the org breakdown and remove the teacher's ability to edit it. Independently shippable: after this, the syllabus GET returns an org-sourced read-only path and the four mutation endpoints are gone (the webapp still calls them until Phase 2 — so Phase 2 must follow before the teacher app is consistent; until then the removed calls 404, which is acceptable on staging between stacked PRs).

Bead: `feat-teacher-readonly-syllabus-phase-1-backend`.

## F1.1 — Auto-seed service (D-2)

**Spec:** Add `seed_class_chapters_from_breakdown(conn, cst_id)` to `breakdown/class_chapter_service.py`, per the copy rule in **02-data-model.md**. Resolve the published breakdown via `resolve_cst_syllabus_context`; if none, no-op. Read `syllabus_chapters` (book_chapter_id, position, start_date, end_date, ordered by position); insert into `class_chapters` with `org_id` from the CST. Idempotent. **Seed only when the CST has zero `class_chapters` rows** (clean rule — see 02-data-model Note); if it has any, leave as-is and log a warning. Structured logging (entry/exit with counts, per CLAUDE.md rule 11). All inserts stamp `org_id`/`cst_id` (tenancy).
**Acceptance:** For a CST whose triple has a published breakdown with K dated chapters and an empty path, calling the helper creates K `class_chapters` rows matching the breakdown's chapters/positions/dates. Calling it again inserts nothing. A CST with no published breakdown → no rows, no error.

## F1.2 — Wire auto-seed into the syllabus GET (D-2)

**Spec:** In `get_cst_syllabus` (`router_class_actions.py`, `GET /api/v2/csts/{cst_id}/syllabus`), call `seed_class_chapters_from_breakdown` before assembling the response, so the first read materialises the path. Keep the rest of the response assembly (chapters with status/slot_count/is_generated).
**Acceptance:** A fresh CST (no path) that GETs its syllabus comes back with the full org-sourced dated path on the first call. Tenancy enforced (CST must belong to the caller's org).

## F1.3 — Drop `recommended_next` from the response (D-5)

**Spec:** Remove `recommended_next` from `SyllabusForCstResponse` (`schemas_class_actions.py`) and stop computing it in `get_cst_syllabus`. If `recommended_next_chapter()` in `class_chapter_service.py` has no other caller after this (grep to confirm), remove it too.
**Acceptance:** The syllabus GET response no longer contains `recommended_next`. No dead reference to `recommended_next_chapter`. Suite green.

## F1.4 — Delete the 4 mutation endpoints + service functions (D-4)

**Spec:** Remove from `router_class_actions.py`: `pick_class_chapter` (`POST …/chapters`), `set_class_chapter_dates` (`PATCH …/chapters/{book_chapter_id}`), `reorder_class_chapters` (`PUT …/chapters/order`), `remove_class_chapter` (`DELETE …/chapters/{book_chapter_id}`). Remove their now-unused service functions in `class_chapter_service.py` (`pick_chapter`, reorder, remove, date-set) and any request schemas in `schemas_class_actions.py` used only by them. **Keep** `resolve_cst_syllabus_context`, status derivation, `chapter_slot_count`, and the break-it-down endpoint/`generate_chapter_plan` (untouched). Confirm `onboard` and the slot/timeline GETs still compile.
**Acceptance:** The four routes 404 (gone from OpenAPI). `break_down_chapter` + `get_cst_syllabus` remain. Server boots; `uv run pytest` green.

## F1.5 — Rewrite tests for the new model (D-4, D-2)

**Spec:** `test_class_chapter_service.py` exercises pick/reorder/remove — remove those cases. Add tests for `seed_class_chapters_from_breakdown` (F1.1 acceptance: seeds K chapters from a published breakdown, idempotent, no-op without a breakdown, no-op when path non-empty). `test_syllabus_api.py`: update for the auto-seed-on-GET behaviour and the dropped `recommended_next`. New DB-backed tests follow the existing DB-gating pattern (skip without Postgres, run in CI) if they need real FKs/RETURNING.
**Acceptance:** `cd server && uv run pytest` green; no test references the deleted endpoints/functions; auto-seed has coverage.

## Notes from execution

- **Position-collision rule (chosen):** clean-install — `seed_class_chapters_from_breakdown(conn, cst_id) -> int` seeds ONLY when the CST has zero `class_chapters` rows. Any pre-existing path (legacy partial teacher-built path with arbitrary positions) is left untouched and logged at WARNING; this dodges the `(cst_id, position)` unique collision and makes the helper idempotent (a re-call finds rows present → inserts 0). Inserts use `ON CONFLICT DO NOTHING` as a belt-and-braces guard on both unique constraints. `org_id` is resolved from `class_subject_teachers` and stamped on every row (tenancy).
- **Wiring:** called at the top of `get_cst_syllabus` (`GET /api/v2/csts/{cst_id}/syllabus`) after the tenancy check, before response assembly — first read materialises the path.
- **`recommended_next_chapter`:** REMOVED (no remaining caller after the GET stopped computing it). Also dropped `recommended_next` field + `RecommendedNextChapter` schema from `SyllabusForCstResponse` (D-5).
- **Deleted (F1.4):** endpoints `pick_class_chapter` (POST …/chapters), `set_class_chapter_dates` (PATCH …/chapters/{id}), `reorder_class_chapters` (PUT …/chapters/order), `remove_class_chapter` (DELETE …/chapters/{id}); service fns `pick_chapter`, `set_chapter_dates`, `remove_chapter`, `reorder_path`, plus the pure `validate_reorder` helper (only used by `reorder_path`); request schemas `PickChapterBody`, `SetChapterDatesBody`, `ReorderChaptersBody`. **Kept:** `resolve_cst_syllabus_context`, `chapter_slot_count`, `derive_chapter_status`, `list_class_path`, `get_cst_syllabus`, `break_down_chapter`/`generate_chapter_plan`, `onboard`, slot/timeline GETs. Verified `onboarding_service.py` does NOT touch `class_chapters` (writes `cst_state`).
- **DB-gating:** auto-seed coverage is in `test_class_chapter_service.py::TestSeedClassChaptersAgainstDB` (seeds K / idempotent / no-op-without-breakdown / no-op-when-path-non-empty), gated on `DATABASE_URL` like `test_chapter_plan_service.py`. Pure status-derivation tests stay non-gated. `test_syllabus_api.py::TestCstSyllabusReadOnly` asserts the GET drops `recommended_next` + the mutation routes are gone (also DB-gated; skips if no CST seeded).
- **No migration** (D-6) — the copy is between existing tables.
