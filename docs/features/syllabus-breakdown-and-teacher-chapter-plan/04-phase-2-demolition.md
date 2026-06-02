# Phase 2 — Demolition: remove admin slots, fork, auto-build, realize

Tear out everything the new model doesn't need (D-2, D-3, D-5, D-6). Salvage the pure
planners (D-12). Drop dead tables/columns. This leaves the Syllabus Breakdown
(chapter→date-range, global only) as the sole admin artifact. One PR → staging.

**Bead:** `feat-syllabus-breakdown-phase-2-demolition`
**Depends on:** Phase 1 merged.

> **Build-from-ground-up mandate (2026-06-02):** remove unused/dead code, don't leave it
> dangling. After this phase there should be no orphaned slot/fork/realize code paths,
> imports, schemas, API methods, or UI. Data bank (SLOs, books, etc.) is NOT touched.

---

## F2.1 — Salvage planners into a teacher-side service (do FIRST, before deleting auto-build)

**Spec.** Move `allocate_chapter_days`, `plan_chapter_slots`, `pick_lp_type` usage, and the
`PlannedSlot`/`ChapterDayAllocation` dataclasses out of `auto_build_service.py` into a new
`server/src/dars/breakdown/chapter_plan_service.py` (pure, no DB). Keep their unit tests
(re-point imports). These are reused by Phase 3.

**Acceptance.** `chapter_plan_service.py` exports the planners; `test_auto_build*` (planner portions) pass against the new module. No behavior change to the functions.

## F2.2 — Delete realization

**Spec.** Delete `realize_service.py`. Remove the publish-triggered realize call in
`router_breakdown.py:publish_breakdown`. Class-scope publish no longer exists anyway (D-3).

**Acceptance.** `realize_service.py` gone; no imports reference it; publish endpoint no longer realizes.

## F2.3 — Delete fork chain

**Spec.** Delete `fork_service.py`, the `fork-org` and `fork-class` endpoints, their schemas
(`ForkOrgBody`, `ForkClassBody`, `ForkResponse`), and the dashboard "Fork to org" UI on the
Curriculum page + any fork buttons.

**Acceptance.** No fork endpoints, no fork service, no fork UI. `grep -ri fork server/src/dars/v2_api webapp/app` returns nothing functional.

## F2.4 — Delete admin slot authoring (API + UI)

**Spec.** Remove slot endpoints (`add_slot`, `update_slot`, `delete_slot`, `set_slot_anchor`,
`seed_chapter`) and the `auto-build` endpoint from `router_breakdown.py`. Remove
`BreakdownSlot*` + `AutoBuild*` + `SeedChapter*` schemas. Delete the remaining
`auto_build_service.py` orchestration (planners already salvaged in F2.1). Remove the slot
editor (`SlotEditor`, `SlotList`, slot handlers, page-range inputs) from
`dashboard/breakdowns/[breakdown_id]/page.tsx` — leaving only the chapter date-range editor.
Remove slot/fork/auto-build methods from `dars-api.ts`.

**Acceptance.** Dashboard breakdown detail shows ONLY chapter date-range editing (the Syllabus Breakdown). No slot UI, no seed button. API has no slot/auto-build/seed endpoints. tsc + eslint clean.

## F2.5 — Rename tables to syllabus_*, drop slots, re-seed globals (D-7)

**Spec.** Migration `20260604000000_syllabus_rename_drop_slots.sql` per `02-data-model.md`:
drop `breakdown_slot_topics`, `breakdown_slots`, `breakdown_chapters`, `breakdowns`;
create `syllabus_breakdowns` + `syllabus_chapters` (syllabus naming, global-only, no
`teaching_days`); drop `class_*_slots.breakdown_slot_id`; add `page_start`/`page_end` to
both class slot tables (D-15). Rename `schemas_breakdown.py`→`schemas_syllabus.py` and
`router_breakdown.py`→`router_syllabus.py` with `Syllabus*` symbols and
`/syllabus-breakdowns/...` paths. **Re-seed** the 2 global Syllabus Breakdowns (Dars +
NCP G1 English) into the new tables via a direct insert (chapters + date ranges only — no
slots; build date ranges by distributing the academic year across chapters, or leave dates
null for the admin to set). Rename dashboard route `breakdowns`→`syllabus-breakdowns` and
`dars-api.ts` `breakdowns`→`syllabusBreakdowns`.

**Acceptance.** Migration present. `syllabus_breakdowns`/`syllabus_chapters` exist; old breakdown tables gone. 2 published global Syllabus Breakdowns present in the new tables. Dashboard route is `/dashboard/syllabus-breakdowns`, shows chapter date-range editing only. Class slot tables have page_start/page_end, no breakdown_slot_id. Non-DB suite green; webapp tsc+eslint clean.

## F2.6 — Enforce global-only scope

**Spec.** `POST /breakdowns` (and any scope handling) rejects non-global scope (D-3).
Remove org/class scope branches. List/get endpoints assume global.

**Acceptance.** Creating a non-global breakdown returns 422. Existing global Syllabus Breakdowns load fine.

---

## Notes from execution
_(append during implementation; don't alter specs)_
