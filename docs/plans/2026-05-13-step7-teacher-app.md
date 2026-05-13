---
type: plan
last_verified: 2026-05-13
owner: hataf
---

# Plan: Step 7 — Teacher App (Sample Integration)

## What this does

A standalone `/teacher-app` section — a complete, functioning sample application showing clients what a teacher-facing integration with Dars looks like. Uses the client's `default_teacher_id`. Teacher can view today's schedule, browse their classes, manage lessons, view/generate LPs and exams, and make freehand LP/exam requests.

## Why

The client is a developer. They need to see concretely what the teacher experience looks like — not as a diagram, but as a working app. The teacher app demonstrates the full Dars feature set from the teacher's perspective, using the client's own API key and data.

## What changes

### DB

No new tables. One new endpoint on the backend.

### Backend — new endpoint (`school/router.py`)

`GET /api/v1/me/classes`
- Returns all `ClassSubjectTeacher` rows where `teacher_id = client.default_teacher_id`
- Each entry includes: cst_id, class_name, grade, section, subject, book_title, chapter_count, taught_count (slots with status=taught), next_planned_slot (next ClassLessonSlot with status=planned)
- Filtered by `client_id`
- Returns empty list (not 404) if `default_teacher_id` is null

Schema: `MyClassEntry` — cst_id, class_name, subject, grade, book_title, chapter_count, taught_count, next_slot: ClassLessonSlotRead | None

### Frontend — new route `/teacher-app`

#### Layout: `webapp/app/teacher-app/layout.tsx`

Completely separate from the dashboard layout. No sidebar.

Structure:
- Top bar: Dars logo (small, left) + "Teacher App" label + "Back to Dashboard →" link (right)
- Banner below top bar: amber strip — "Sample Integration — this shows what you can build with the Dars API"  
- Main content area (white background, clean — not the dark dashboard)
- Internal top nav: **Today** | **My Classes** | **Quick LP** | **Quick Exam**

Auth: same `dars_pef_session` from localStorage. If no session → redirect to `/dashboard/login`.

Component: `components/molecules/teacher-app/top-nav.tsx`

#### Page: Today — `webapp/app/teacher-app/today/page.tsx`

Calls `GET /api/v1/today`.

For each entry (class scheduled today):
- Card: class name + subject + teacher name
- Previous taught lesson (greyed, strikethrough)
- Current lesson: LP type badge + title + "View LP" button (slide-over) + "Mark as Taught" button
- Next planned lesson (greyed)

Empty state: "No classes scheduled for today" with day of week shown.

"Mark as Taught" → PATCH `/api/v1/class-lesson-slots/{id}/mark-taught` → card updates inline.

#### Page: My Classes — `webapp/app/teacher-app/classes/page.tsx`

Calls `GET /api/v1/me/classes`.

List of class cards:
- Class name, subject, grade
- Progress bar: taught / total lesson slots
- Next lesson title (from `next_slot`)
- Click → `/teacher-app/classes/[cst_id]`

Empty state: "No classes assigned. Set up your school structure in the dashboard."

#### Page: Class Detail — `webapp/app/teacher-app/classes/[cst_id]/page.tsx`

Two tabs: **Lessons** | **Assessments**

**Lessons tab:**
- Chapter selector (dropdown of ChapterPlan rows for this CST)
- If no slots for selected chapter: "Generate Lesson Breakdown" button → POST generate → slots appear
- Slot list (day number, LP type badge, title, status)
- Each planned slot: "Mark as Taught" button + "View LP" / "Generate LP" button
- "Generate All LPs" button at chapter level

**Assessments tab:**
- List of AssessmentSlots for this CST
- Columns: chapter, type (FA/SA badge), scheduled date, status, action
- "Generate Exam" button per slot → PENDING badge → "View Exam" when ready
- Status update: dropdown (scheduled → completed / skipped)

#### Page/Modal: Quick LP — accessible from top nav

Freehand LP form (same as dashboard lesson plans page):
- Grade, subject, topic (free text), page number (optional)
- "Generate" → POST `/api/v1/lesson-plans` → poll → show result in slide-over
- No chapter linkage — purely freehand

#### Page/Modal: Quick Exam — accessible from top nav

Freehand exam form (same as dashboard exam generator page):
- Grade, subject, page ranges
- "Generate" → POST `/api/v1/exams` → poll → show result
- No assessment slot linkage

#### Sidebar update

`components/molecules/dashboard/sidebar.tsx`:

Add section below main nav items:
```
── Sample App ──
  Teacher App  →  /teacher-app (with external link icon)
```

Section label styled differently (lighter, smaller) to signal it's a separate thing.

### Tests

File: `server/tests/test_teacher_app.py`
- `GET /api/v1/me/classes` returns CSTs for default_teacher_id
- Returns empty list if default_teacher_id is null (not 404)
- Client isolation: cannot see another client's teacher's classes

### Frontend E2E

1. Navigate to `/teacher-app` → redirects to `/teacher-app/today`
2. Banner "Sample Integration" always visible
3. Today tab: cards for scheduled classes (or empty state)
4. "Mark as Taught" → card updates without reload
5. My Classes → list with progress bars
6. Click class → Class Detail opens on Lessons tab
7. Chapter selector → lesson slots load
8. "Generate LP" on a slot → spinner → "View LP" when ready
9. Assessments tab → assessment slots listed
10. "Generate Exam" → PENDING → View Exam when done
11. Quick LP → freehand form → generates and shows in slide-over
12. Quick Exam → freehand form → generates and shows
13. "Back to Dashboard" → returns to `/dashboard`

## Bead

- ID: `feat-step7-teacher-app`
- Title: Step 7 — Teacher App
- Category: feature

## Risks & constraints

- The teacher app shares the client's API key — it is not a multi-teacher login system. The `default_teacher_id` is always the teacher shown.
- The "Sample Integration" banner must never be removable — it is a permanent UI element, not a dismissable toast.
- If `default_teacher_id` is null (client never set up school structure), the app should show a clear "Set up your school first" state pointing to the dashboard planner.
- Quick LP and Quick Exam in the teacher app are identical in function to the dashboard versions — consider extracting shared components rather than duplicating.
- The teacher app must work without the school structure being set up — graceful empty states at every level.
