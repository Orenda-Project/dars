# Phase 1 — LP Assistant SLO injection + linkage

**Goal:** Every LP dispatched to LP Assistant carries a `custom_prompt` listing its topic's sub-SLOs, and the requested sub-SLOs are persisted on the `generated_lps` row at insert time.

**Bead:** `feat-lp-slo-injection-and-linkage`.

**Pre-reqs:** v2 rebuild Phase 3 already merged on staging (F3.1–F3.13). `topic_sub_slos` populated by the seed.

**Deliverables:**
- Migration adding `requested_sub_slo_ids UUID[]` to `generated_lps`
- `LPRequest` accepts a `sub_slo_statements: list[str] | None` field
- `_build_body` adds `custom_prompt` only when statements list is non-empty
- Service helper `_load_topic_sub_slos(conn, topic_id)` returns `list[tuple[UUID, str]]` `(sub_slo_id, statement)` sorted by `sub_slos.code`
- `_insert_pending_lp` accepts and persists `requested_sub_slo_ids`
- All three entry points (`get_or_generate_lp`, `get_or_generate_class_specific_lp`, `get_or_generate_revision_lp`) wire the new piece through
- Update v2 rebuild plan: cross-reference D-1's supersession of "do NOT send custom_prompt" in `05-phase-3-generation-pipeline.md` F3.2 spec
- Tests: unit test for the body-build path with and without sub-SLOs; service-layer test that requested column gets populated correctly

**NOT in this phase:**
- Backfilling existing LPs (D-7)
- F3.8 changes — `covered_sub_slo_ids` continues to be set the same way (D-8)
- Cache-key changes (D-6)
- UI changes to surface "requested vs covered" anywhere
- Exam-side SLO injection (UG_EG) — analogous work but separate

---

## Feature order

1. **F1.1** — Migration: add `requested_sub_slo_ids` column
2. **F1.2** — Topic→sub-SLO loader helper
3. **F1.3** — Wire `custom_prompt` into the request body
4. **F1.4** — Thread requested set through all three service entry points
5. **F1.5** — Tests + plan-doc cross-reference + staging smoke

---

## F1.1 — Migration

**Spec:**
- New file: `server/src/dars/migrations/<timestamp>_generated_lps_requested_sub_slos.sql`
- Statement: `ALTER TABLE generated_lps ADD COLUMN requested_sub_slo_ids UUID[] NULL;`
- No index (we don't query by this column in v1)
- No backfill (D-7)

**Acceptance:**
- Migration file lives in `server/src/dars/migrations/` (CLAUDE.md rule #7)
- Applies cleanly on staging Railway deploy
- Schema check via `\d generated_lps` shows the column

---

## F1.2 — Topic→sub-SLO loader

**Spec:**
- New helper in `dars/generated_lps/service.py`:
  ```python
  async def _load_topic_sub_slos(
      conn: asyncpg.Connection, topic_id: UUID
  ) -> list[tuple[UUID, str]]:
      """Return (sub_slo_id, statement) for a topic, ordered by sub_slos.code."""
  ```
- SQL: `SELECT ss.id, ss.statement FROM topic_sub_slos tss JOIN sub_slos ss ON ss.id = tss.sub_slo_id WHERE tss.topic_id = $1 ORDER BY ss.code`
- Empty result → empty list (D-4)
- For revision: a sibling helper `_load_union_topic_sub_slos(conn, topic_ids: list[UUID])` does `WHERE tss.topic_id = ANY($1)` with `DISTINCT ON (ss.id)` ordered by code

**Acceptance:**
- Helper returns deterministically sorted list
- Empty topic returns `[]`
- Revision union de-dupes

---

## F1.3 — `custom_prompt` in request body

**Spec:**
- Extend `LPRequest` (in `lp_assistant_client.py`):
  ```python
  sub_slo_statements: list[str] | None = None
  ```
- Extend `_build_body`:
  ```python
  if req.sub_slo_statements:
      bullets = "\n".join(f"- {s}" for s in req.sub_slo_statements)
      body["custom_prompt"] = (
          "After this lesson plan, the following sub-SLOs should be covered:\n"
          f"{bullets}"
      )
  ```
- Empty / None → no `custom_prompt` key in body (D-4)
- Log line in `request_lp_generation` adds `sub_slo_count=<n>` (entry log only — don't log statements themselves; they're long)

**Acceptance:**
- Body contains `custom_prompt` iff `sub_slo_statements` is non-empty
- The string exactly matches D-1's frozen format
- Existing fields unchanged

---

## F1.4 — Thread requested set through service entry points

**Spec:**

`_insert_pending_lp` gains a new kwarg:
```python
async def _insert_pending_lp(
    ...,
    requested_sub_slo_ids: list[UUID],
) -> UUID:
```
and SQL becomes:
```sql
INSERT INTO generated_lps (
    cache_key, scope, scope_ref_id,
    curriculum_id, grade_id, subject_id,
    topic_id, lp_type, status, requested_sub_slo_ids
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'PENDING', $9)
RETURNING id
```

`_dispatch_and_mark` gains `sub_slo_statements: list[str]` and passes it to `LPRequest`.

`get_or_generate_lp`:
- Before insert: `pairs = await _load_topic_sub_slos(conn, topic_id)`
- `requested_ids = [p[0] for p in pairs]`
- `statements = [p[1] for p in pairs]`
- Pass `requested_ids` to `_insert_pending_lp`, `statements` to `_dispatch_and_mark`
- Cache hit path: no change (the existing row's `requested_sub_slo_ids` is already set or NULL for legacy rows)

`get_or_generate_class_specific_lp`:
- Same as above; sub-SLOs come from the same topic regardless of scope

`get_or_generate_revision_lp`:
- After computing the capped `prior` list, build `prior_topic_ids = [r["topic_id"] for r in prior]`
- `pairs = await _load_union_topic_sub_slos(conn, prior_topic_ids)`
- Same threading

Update the revision INSERT statement too (it's a separate inline SQL) — add `requested_sub_slo_ids` column and bind the array.

**Acceptance:**
- Three new rows inserted via the three entry points all have `requested_sub_slo_ids` populated correctly
- The LP Assistant request body contains `custom_prompt` for every dispatch
- Cache hits don't re-dispatch and don't re-populate (the existing row's column is preserved as-is)

---

## F1.5 — Tests + plan cross-reference + staging smoke

**Tests** (in the same style as existing tests under `server/tests/`):
- `test_lp_assistant_client.py`:
  - body without sub-SLOs has no `custom_prompt` key
  - body with sub-SLOs has the exact D-1 string
  - empty list also produces no `custom_prompt`
- `test_generated_lps_service.py` (or wherever the existing service tests live):
  - lesson slot path: requested_sub_slo_ids populated from topic_sub_slos
  - topic with zero sub-SLOs → empty array, no custom_prompt sent (assert via dispatcher mock capturing the LPRequest)
  - revision path: requested_sub_slo_ids = union over prior topics

**Plan-alive updates:**
- In `docs/plans/2026-05-15-dars-v2-rebuild/05-phase-3-generation-pipeline.md`, in the F3.2 spec where it says "Do NOT send `custom_prompt`": amend to add a "(Superseded by lp-slo-injection-and-linkage D-1 on YYYY-MM-DD — `custom_prompt` is now sent for sub-SLO steering)" note. Do not delete the original line.
- In `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md`, in the `generated_lps` table: add the row `| requested_sub_slo_ids | UUID[] NULL | intent set at dispatch; see features/lp-slo-injection-and-linkage |`.

**Staging smoke (manual, after PR merge):**
- Hit `POST /api/v1/generated-lps/refresh` on a fresh slot via the demo API key
- Query `SELECT requested_sub_slo_ids, covered_sub_slo_ids FROM generated_lps WHERE id = '<uuid>'`
- Confirm `requested_sub_slo_ids` non-empty for the demo topic; `covered_sub_slo_ids` populated after F3.8 finishes

**Acceptance:**
- All tests pass
- Plan docs updated in the same PR
- Staging smoke confirms both columns populate

---

## Phase wrap-up checklist

- [ ] Migration applied on staging
- [ ] All three entry points populate `requested_sub_slo_ids`
- [ ] LP Assistant requests include `custom_prompt` for topics with sub-SLOs
- [ ] Empty-sub-SLO topics dispatch cleanly (no error, no custom_prompt)
- [ ] Tests pass locally and on CI
- [ ] v2 rebuild plan docs cross-reference D-1 + new column
- [ ] ONRAMP.md `Step 5 — Current state` reflects ✅
- [ ] Bead closed
