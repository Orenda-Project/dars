# Phase 1 — Merged timeline endpoint

**Goal:** A single backend endpoint that returns a CST's lessons + assessments interleaved by `position`, each stamped with its projected date and conflict/overflow flags, carrying enough context (chapter, topic(s), status, generation status) for the frontend to render the full timeline with no further fetches.

Independently shippable: the endpoint is consumable + testable on its own. No frontend change required to merge Phase 1.

Backend file: `server/src/dars/v2_api/router_class_actions.py` (+ schemas in `schemas_class_actions.py`). Projector: `dars.breakdown.projector.project_cst_schedule` (reuse, D-5).

---

## F-1.1 — `GET /api/v2/csts/{cst_id}/timeline` endpoint

**Spec.** New route in `router_class_actions.py`, auth identical to the existing `lesson-slots` / `assessment-slots` list endpoints (org/client scoped — copy their dependency + `client_id` filtering exactly; see Critical Rule #3). Steps:

1. Call `project_cst_schedule(conn, cst_id)` → `ProjectedSlot[]`. Build a map `proj[(slot_kind, slot_id)] → ProjectedSlot`.
2. Run the **existing** lesson-slots query (router_class_actions.py:283-333) and assessment-slots query (router_class_actions.py:336-399) — reuse the SQL verbatim so topic/chapter/status/generation fields stay identical to the per-kind endpoints.
3. Build timeline items:
   - For each lesson row → a `kind:"lesson"` item, attaching `projected_date`, `is_anchor`, `is_conflict`, `is_overflow` from the projector map.
   - For each assessment row → a `kind:"assessment"` item, same projector fields.
4. Merge both lists and **sort by `position`** (the global spine, D-1). Stable; ties shouldn't occur (positions are unique across kinds per the projector merge).
5. Return `CstTimelineResponse`.

**Acceptance.**
- `GET /api/v2/csts/{seeded_cst}/timeline` returns 200 with items in strictly ascending `position`.
- Lesson + assessment items both present and interleaved (not all-lessons-then-all-assessments).
- Each item has a `projected_date` (ISO date or null), and the date matches what `project_cst_schedule` returns for that slot id.
- A CST belonging to another client returns 404/empty per existing tenancy behaviour (mirror the per-kind endpoints' test).
- Structured logging: entry (cst_id), exit (cst_id, item count, overflow count, conflict count). Errors at ERROR with `exc_info=True`.

## F-1.2 — `CstTimelineResponse` + item schemas (D-4)

**Spec.** In `schemas_class_actions.py`:

```python
class TimelineLessonItem(BaseModel):
    kind: Literal["lesson"]
    id: UUID
    position: int
    projected_date: date | None
    is_anchor: bool
    is_conflict: bool
    is_overflow: bool
    slot_type: str                 # "lesson" | "revision"
    lp_type: str | None
    topic_id: UUID | None
    topic_title: str | None
    status: str                    # planned | taught | skipped
    generated_lp_id: UUID | None
    lp_status: str                 # not_generated | PENDING | IN_FLIGHT | READY | ERROR
    breakdown_chapter_id: UUID
    breakdown_chapter_position: int
    breakdown_chapter_title: str

class TimelineAssessmentItem(BaseModel):
    kind: Literal["assessment"]
    id: UUID
    position: int
    projected_date: date | None
    is_anchor: bool
    is_conflict: bool
    is_overflow: bool
    assessment_type: str           # formative | summative
    topic_ids: list[UUID]
    topic_titles: list[str]
    status: str                    # scheduled | completed | skipped
    generated_exam_id: UUID | None
    exam_status: str
    breakdown_chapter_id: UUID
    breakdown_chapter_position: int
    breakdown_chapter_title: str

TimelineItem = Annotated[
    Union[TimelineLessonItem, TimelineAssessmentItem],
    Field(discriminator="kind"),
]

class CstTimelineResponse(BaseModel):
    cst_id: UUID
    items: list[TimelineItem]
```

Field names mirror the existing `ClassLessonSlotListItem` / `ClassAssessmentSlotListItem` exactly (don't rename), plus the four projector fields. The frontend `dars-api.ts` types mirror these.

**Acceptance.**
- Response validates; `kind` discriminator round-trips through the OpenAPI schema.
- A lesson item and an assessment item in the same response deserialize to their correct types on the client.

## F-1.3 — Endpoint test

**Spec.** DB-gated e2e mirroring `TestClassActionsE2E` (Community 19) against the v2 seed. Assert ordering by position, presence of both kinds, projected_date matches the projector for a known slot, and that a conflict/overflow slot (construct one via an anchor on a holiday if the seed allows, else assert flags default to false) carries the right flags.

**Acceptance.** Test passes locally against the seeded DB and in CI's DB-gated lane.

---

## Dependencies

- Reuses `project_cst_schedule` (no change to projector).
- Reuses the two existing list SQL queries (copy, don't refactor them out yet — keep per-kind endpoints intact for now; a later cleanup can dedupe).
