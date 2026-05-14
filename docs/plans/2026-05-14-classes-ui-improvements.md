---
type: plan
last_verified: 2026-05-14
owner: hataf
---

# Plan: Classes UI Improvements

## What this does

Three improvements to the teacher app classes experience:

1. **Fix `MyClassEntry` response** — backend currently returns `subject_id: int` and `grade_id: int` (raw FK IDs) but frontend expects `subject: string` (display name) and `grade: number` (grade code like 1, 2, 3). Resolves the display mismatch. Also adds `timetable_days: list[int]` to the response so the list page can show class days.

2. **Classes list page** — add a view toggle (grid ↔ grouped-by-grade). In group view: classes are collapsible sections per grade. In grid view: existing card layout but with day pills (Mon/Tue/etc.) and filter chips by grade/subject. Toggle preference persisted in `localStorage`.

3. **Class detail page** — add a "Timetable" tab alongside Lessons/Assessments. Shows current days as toggleable pills. Save button calls `setTimetable`. Loads current timetable via `getTimetable` on mount.

## Why

With 20+ classes the flat grid is unusable. Teachers need to scan by grade and see at a glance which days a class meets. The detail page had no way to edit the timetable after creation.

## What changes

### Backend

- **`server/src/dars/school/schemas.py`**
  - `MyClassEntry`: replace `subject_id: int` → `subject: str`, `grade_id: int` → `grade: int` (grade code), add `timetable_days: list[int]`

- **`server/src/dars/school/router.py`** (`get_my_classes`)
  - Import `Grade` and `Subject` from `dars.lookup.models`
  - For each CST: `await db.get(Subject, cst.subject_id)` → `subject.display_name`
  - For each SchoolClass: `await db.get(Grade, sc.grade_id)` → `grade.code`
  - Query `Timetable` slots for the CST → collect `day_of_week` values as `timetable_days`

### Frontend

- **`webapp/lib/school-api.ts`**
  - `MyClassEntry`: `subject_id` → `subject: string`, `grade_id` → `grade: number`, add `timetable_days: number[]`

- **`webapp/app/teacher-app/classes/page.tsx`**
  - Add `viewMode: "grid" | "group"` state, init from `localStorage`
  - Toggle button in header (grid icon / group icon)
  - Grid view: existing cards + day pills at bottom of each card, filter chips (grade + subject) at top
  - Group view: sections `Grade 1 (3)`, `Grade 2 (4)` etc., each with a compact row list (class name · subject · day pills · progress bar)
  - Compact row is a `<Link>` to the detail page

- **`webapp/app/teacher-app/classes/[cst_id]/page.tsx`**
  - Add `"timetable"` to the tab union
  - `TimetableTab` component: fetches `getTimetable(classId, cstId)` on mount — but `cst_id` is in params, `class_id` is not. Need to get `class_id` from timetable or another source.
  - **Note**: `getTimetable` needs both `classId` and `cstId`. The detail page only has `cst_id` in the URL. Need to expose `class_id` — either via a new endpoint `GET /api/v1/cst/{cstId}` returning the CST record, or include `class_id` in the timetable response, or fetch it from `getChapterPlansByCst` which returns `class_subject_teacher_id`.
  - Simplest: add `GET /api/v1/cst/{cst_id}` endpoint returning `{id, class_id, subject_id, ...}` — one small endpoint.
  - `TimetableTab`: Mon–Sat toggles, current days pre-selected, Save button → `setTimetable`

### Tests

- **`server/tests/test_teacher_app.py`**
  - Update `test_my_classes_returns_teacher_csts`: assert `item["subject"]` (display name string), `item["grade"]` (int code), `item["timetable_days"]` (empty list when no timetable set)
  - Update `test_my_classes_client_isolation`: assert `subject` and `grade` fields instead of `subject_id`/`grade_id`
  - Add `test_my_classes_timetable_days`: create timetable slots for a CST, verify they appear in `timetable_days`

## Bead
- ID: `feat-classes-ui-improvements`
- Title: Classes UI — view toggle, timetable days, detail timetable tab
- Category: feature

## Risks & constraints
- `get_my_classes` does N+1 queries per CST (already does this for book, chapter count, etc.) — adding 2 more lookups (Grade, Subject) is consistent with the existing pattern; acceptable for now
- `class_id` not in detail page URL — need new `GET /api/v1/cst/{cst_id}` endpoint or pass `class_id` via query param on navigation. New endpoint is cleaner.

## E2E test scenarios
1. Classes list page — grid view shows day pills on each card (Mon/Tue/etc.)
2. Classes list page — click group toggle → classes collapse under grade headings
3. Classes list page — click filter chip "Grade 1" → only Grade 1 classes visible
4. Classes list page — toggle persists on page reload
5. Class detail page — Timetable tab shows correct days pre-selected
6. Class detail page — toggle a day off, click Save → day no longer appears
