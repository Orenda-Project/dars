# Phase 2 — Chapter Plan: manual builder + page ranges

Make breaking a single chapter into typed slots a **manual-first** action on the dashboard, with explicit page ranges. Auto-build demoted to an optional seed. One PR, targets `staging`.

**Bead:** `feat-chapter-breakdown-and-plan-phase-2-chapter-plan`
**Depends on:** Phase 1 merged (shared editor surface, chapter context).

---

## F2.1 — Schema delta: slot page range

**Spec.** Add `page_start` / `page_end` (INT NULL) to `breakdown_slots` per Delta 2 in `02-data-model.md`. Migration `20260603000000_breakdown_slots_page_range.sql`. Update ORM model + `BreakdownSlotRead`/`Create`/`Update` to expose and accept both.

**Acceptance.** Migration present. Slot reads return the fields (null for existing); slot create/update accept them. SQLite suite green.

## F2.2 — Manual per-chapter slot builder (backend)

**Spec.** Confirm the existing slot endpoints (`add_slot`, `update_slot`, `delete_slot` in `router_breakdown.py`) support building a chapter's slots one at a time scoped to a single `breakdown_chapter_id`, now including `slot_type`, `lp_type`, `topic_id`, and the new page range. No new endpoint unless a gap is found — reuse the shipped slot-editing endpoints (D-3). If a gap exists, add the minimal endpoint and log a decision (D-N).

**Acceptance.** Adding a lesson slot with `slot_type=lesson`, `lp_type=reading`, `page_start=1`, `page_end=10` to a chapter persists and appears in the breakdown read at the correct `chapter_position`. Adding a `formative_assessment` slot with a page range works identically.

## F2.3 — Auto-build as optional seed

**Spec.** Per D-3, keep `auto_build_service.py` available but reframe it in the UI as "Seed a starting point for this chapter" — runs for the **selected chapter** and produces editable slots, rather than being the implicit whole-breakdown build. If auto-build today only runs whole-breakdown, scope it to a single chapter (or filter its output to the chapter); log the approach as a decision.

**Acceptance.** From a chapter with no slots, clicking "Seed" produces a draft slot sequence for that chapter; the user can then add/edit/delete/reorder and set page ranges. Manual entry works with zero reliance on seed.

## F2.4 — Dashboard Chapter Plan editor (frontend)

**Spec.** In the breakdown editor, selecting a chapter opens its Chapter Plan: an ordered, editable list of slots. Per slot: type selector (lesson / formative_assessment / summative_assessment / revision — reuse `webapp/lib/slot-types.ts`), `lp_type` selector (subject-specific, for lesson slots), topic selector, and **page-start / page-end inputs**. Add-slot, delete-slot, reorder. "Seed a starting point" button (F2.3) as a secondary action. Manual is the primary path (D-3).

**Acceptance.** A user can build a chapter's plan entirely by hand — e.g. "LP1: reading, pages 1–10" then "Day 2: formative assessment, pages 1–10" — and it persists and re-renders in order. Seed remains available as an optional first draft. No teacher-app changes (D-6).

---

## Notes from execution

**2026-06-02 — all features implemented (PR open to staging).**
- F2.1: migration `20260603000000_breakdown_slots_page_range.sql` (`page_start`/`page_end` INT NULL); slot read/create/update schemas + all five slot SQL projections in `router_breakdown.py` updated.
- F2.2: reused existing `add_slot`/`update_slot` endpoints — `update_slot`'s field loop already iterates a tuple, so page fields slotted in cleanly. No new slot endpoint needed.
- F2.3: per-chapter seed is a **new** endpoint `POST /breakdowns/{id}/chapters/{chapter_id}/seed` + `seed_chapter_slots()` in `auto_build_service.py`, reusing `allocate_chapter_days` + `plan_chapter_slots` + `pick_lp_type` (D-9). Day budget defaults to the chapter's derived teaching days (D-2), else topic count. Refuses a non-empty chapter (422).
- F2.4: `SlotEditor` gains page-start/end inputs with advisory "end before start" guard (Save disabled while invalid); `SlotList` shows a "pp N–M" badge on single + expanded rows; chapter header shows a "Seed plan" button only when the chapter has 0 slots.
- New decision D-9 logged. Tests: backend non-DB suite 152 passed (planners already covered); webapp tsc + eslint clean.
