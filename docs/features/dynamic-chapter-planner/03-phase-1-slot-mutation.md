# Phase 1 — Slot-mutation foundation

The load-bearing piece both Case 1 (lost periods) and Case 2 (reteach) share: mutate the
realized slot sequence; let the projector absorb the dates. Independently shippable — ends
with a working, tested mutation service + overflow read, no planner/reteach changes yet.

## F-1.1 — Migration: slot provenance + flex

**Spec:** add `origin`, `reteach_for_sub_slo_id`, `flex` to `class_lesson_slots` and `origin`
to `class_assessment_slots`, per [02-data-model.md](02-data-model.md). New migration file in
`server/src/dars/migrations/` (append-only; timestamp after `20260610000000`).
**Acceptance:** migration applies clean on Postgres (Railway deploy) and on sqlite (tests);
existing rows default to `origin='breakdown'`, `flex=false`. Data model doc matches in the
same PR.

## F-1.2 — `slot_mutation_service.py`

**Spec:** new `server/src/dars/breakdown/slot_mutation_service.py` with structured logging
(entry/exit/error per CLAUDE.md rule 11). Functions:

- `insert_lesson_slot(conn, cst_id, after_position, *, topic_ids, lp_type, origin='manual', reteach_for_sub_slo_id=None, flex=False) -> UUID`
  — open a gap at `after_position+1`: renumber every lesson AND assessment row with
  `position > after_position` up by one (D-8: both tables, single tx, descending order or
  two-step offset to dodge the `UNIQUE (cst_id, position)` collision), then insert a `planned`
  lesson + its `class_lesson_slot_topics`. Returns new slot id.
- `remove_slot(conn, cst_id, position) -> None` — only if the slot at `position` is
  `planned`/`scheduled` (else ValueError); delete it + its topics; renumber the tail down by one.
- `consume_flex_slot(conn, cst_id, after_position, *, reteach_for_sub_slo_id, lp_type, topic_ids) -> UUID | None`
  — find the nearest `flex=true planned` lesson slot at `position > after_position`; repurpose
  it in place (`origin='reteach'`, `flex=false`, set `reteach_for_sub_slo_id`, rewrite topics,
  clear `generated_lp_id`). Return its id, or `None` if no downstream flex slot (caller then
  decides to `insert_lesson_slot`).

**Acceptance:** each function in one transaction; position uniqueness preserved; returns
documented values. Raw SQL, portable to sqlite (D-11).

## F-1.3 — Taught-lock invariant

**Spec:** a helper `_assert_mutable(conn, cst_id, after_position)` (D-7) that rejects any
mutation at/before the CST's `max(position)` over rows with `status IN ('taught','completed')`
across both tables. All three F-1.2 functions call it.
**Acceptance:** mutating before/at the last-taught position raises a clear ValueError → 422 at
the route layer; mutating after it succeeds.

## F-1.4 — Overflow surfacing (thin slice)

**Spec:** expose the projector's existing `is_overflow` to the teacher app. Either a field on
the existing timeline/today read or a small `GET .../overflow-warnings` returning the count +
first overflowing slot. No new projection logic — just read `ProjectedSlot.is_overflow`.
**Acceptance:** a CST whose slots exceed its teaching days reports the overflow count; a CST
that fits reports zero. Ships the Case-1 (holiday) story visibly even before reteach exists.

## F-1.5 — Tests (sqlite-runnable)

**Spec:** `server/tests/test_slot_mutation_service.py` (D-11), provisioning a sqlite DB with
the two slot tables (+ topics join). Cover:
- insert renumbers both lesson and assessment rows past the insertion point;
- `UNIQUE (cst_id, position)` holds throughout the renumber;
- taught-lock rejects insert-at/before last-taught; allows after;
- `remove_slot` refuses a `taught` slot, succeeds on `planned`, renumbers tail;
- `consume_flex_slot` picks the nearest downstream flex slot and returns `None` when none.
**Acceptance:** `pytest` green on sqlite with no `DATABASE_URL` set.

## Dependencies

F-1.2 depends on F-1.1 (columns). F-1.3 is used by F-1.2. F-1.5 depends on F-1.1–F-1.3.
F-1.4 is independent (read-only) and can land in the same PR or a fast-follow.
