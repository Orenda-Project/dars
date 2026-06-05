---
type: plan
last_verified: 2026-05-12
owner: hataf
---

# Plan: Teacher App — Sample Integration

## What this does

A standalone `/teacher-app` section in the webapp — a complete, functioning sample application that shows clients what a teacher-facing integration with Dars looks like. It uses the client's own `default_teacher_id` and their API key (already in session). The app covers the full teacher daily workflow: see today's classes, view the lesson breakdown for each class, mark lessons as taught, and review scheduled assessments.

This is structurally separate from `/dashboard` — different layout, different visual identity, different purpose. The dashboard is for the developer/admin configuring the system. The teacher app is for showing what can be built on top of it.

## Why

The client is a developer who integrates Dars APIs into their own application. They need to see concretely what the teacher experience looks like — not as a wireframe, but as a working app they can click through and understand. The separation also establishes a clear mental model: dashboard = your control plane, teacher app = your end product.

## What changes

### Frontend — new route `/teacher-app`

#### Layout: `webapp/app/teacher-app/layout.tsx`

A completely separate layout from the dashboard. No sidebar. Instead:
- Top bar with Dars logo (small), "Teacher App" label, and a "Back to Dashboard" link
- A banner: `"Sample Integration — this is an example of what you can build with the Dars API"`
- Clean white background (not the dark ink sidebar of the dashboard)
- No admin controls, no settings link

#### Entry / redirect: `webapp/app/teacher-app/page.tsx`

Redirects to `/teacher-app/today`. If no session, redirects to `/dashboard/login`.

#### Page: Today — `webapp/app/teacher-app/today/page.tsx`

Calls `GET /api/v1/today`. Shows all class-subject pairs scheduled for today's day of week.

Each card shows:
- Class name + subject
- Teacher name
- Previous taught lesson (greyed out)
- Current lesson (next `planned` slot) — title + LP type badge
- "View Lesson Plan" button → slide-over panel with LP HTML (same `plan-window` molecule already used in dashboard)
- "Mark as Taught" button → PATCH mark-taught, updates status inline
- Next planned lesson (greyed out)

If nothing is scheduled today: friendly empty state ("No classes scheduled for today").

#### Page: My Classes — `webapp/app/teacher-app/classes/page.tsx`

Lists all `ClassSubjectTeacher` records for the session's teacher (filtered server-side by `default_teacher_id` via a new `GET /api/v1/me/classes` endpoint — see backend section below). Each row: class name, subject, chapter progress (X of Y chapters taught), next lesson title. Click a class → goes to `/teacher-app/classes/[cst_id]`.

#### Page: Class Detail — `webapp/app/teacher-app/classes/[cst_id]/page.tsx`

Two tabs: **Lessons** and **Assessments**.

**Lessons tab:**
- Chapter selector (dropdown of chapter plans for this CST)
- Lesson slot list for selected chapter: day number, LP type badge, title, status badge
- "Mark as Taught" on each `planned` slot
- "Generate Lessons" button if no slots exist for the chapter

**Assessments tab:**
- List of `AssessmentSlot` rows for this CST: type (FA/SA), scheduled date, status, chapter
- Inline status update (scheduled → completed / skipped)

#### Navigation within teacher app

Simple top nav links: **Today** | **My Classes**

No sidebar. The teacher app has its own internal navigation component: `components/molecules/teacher-app/top-nav.tsx`.

---

### Backend — one new endpoint

`GET /api/v1/me/classes` — returns all `ClassSubjectTeacher` rows where `teacher_id = client.default_teacher_id`, filtered by `client_id`. Response includes class name, subject, chapter count, and next planned lesson slot.

This is the only new backend change. All other data (today schedule, chapter plans, lesson slots, assessments) already has endpoints from the teacher planning tool.

Router: add to `school/router.py`. Service: add `get_teacher_classes(client, db)` to `school/service.py`.

Schema: `MyClassesResponse` — list of `{cst_id, class_name, subject, chapter_count, next_lesson: ClassLessonSlotRead | None}`.

---

### Sidebar — dashboard link to teacher app

Add a section to `components/molecules/dashboard/sidebar.tsx`:

```
── Sample App ──
  Teacher App  →  /teacher-app
```

Visually distinct — use a different icon (mobile/phone icon) and label it as "Sample App" in the section header so the purpose is clear.

---

### Files that change

| File | Change |
|------|--------|
| `webapp/app/teacher-app/layout.tsx` | New — standalone layout with banner |
| `webapp/app/teacher-app/page.tsx` | New — redirect to /today |
| `webapp/app/teacher-app/today/page.tsx` | New — today's schedule view |
| `webapp/app/teacher-app/classes/page.tsx` | New — teacher's class list |
| `webapp/app/teacher-app/classes/[cst_id]/page.tsx` | New — class detail (lessons + assessments tabs) |
| `components/molecules/teacher-app/top-nav.tsx` | New — top nav for teacher app |
| `components/molecules/dashboard/sidebar.tsx` | Add "Sample App" section with Teacher App link |
| `server/src/dars/school/router.py` | Add GET /api/v1/me/classes |
| `server/src/dars/school/service.py` | Add get_teacher_classes() |
| `server/src/dars/school/schemas.py` | Add MyClassesResponse |
| `server/tests/test_school.py` | Add test for /me/classes endpoint |

---

### What does NOT change

- `/dashboard/curriculum-demo` — stays as-is (configuration tool for admin)
- All existing school API endpoints — untouched
- Lesson plan generation flow — untouched
- Auth / session — teacher app reads from the same `dars_pef_session` localStorage key
<!-- Superseded 2026-06-04: teacher app now reads the org API key `dars_org_api_key`; `dars_pef_session` was removed. -->

---

## Bead

- ID: `feat-teacher-app`
- Title: Teacher App — sample integration route
- Category: feature

## Risks & constraints

- `default_teacher_id` on the client record must exist for `/me/classes` to return anything. If null, return empty list with a helpful message in the UI ("No teacher account linked — set up your school configuration first").
- The teacher app shares the client's API key. It is not a multi-teacher login system — it shows the experience from one teacher's perspective (the default teacher). That's intentional for the prototype.
- The banner ("Sample Integration") must always be visible. It should never be closeable — the distinction between demo and production must be permanently clear.
- Do not move the SLO Tracker into the teacher app — it's static and admin-level. It stays in curriculum-demo.

## E2E test scenarios

1. Navigate to `/teacher-app` → redirects to `/teacher-app/today`
2. Today tab shows cards for classes scheduled today (if any); empty state if none
3. "Mark as Taught" on a lesson slot → status updates to `taught` inline, no full reload
4. "View Lesson Plan" → slide-over opens with LP HTML
5. My Classes → lists all CSTs for the default teacher with chapter progress
6. Click a class → Class Detail opens on Lessons tab
7. Chapter selector → switching chapters updates lesson slot list
8. Generate Lessons on a chapter with no slots → slots appear
9. Assessments tab → list renders with correct types and dates
10. Banner "Sample Integration" is always visible across all teacher-app pages
11. "Back to Dashboard" link returns to `/dashboard`
