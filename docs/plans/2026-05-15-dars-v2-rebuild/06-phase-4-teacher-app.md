# Phase 4: Teacher App

**Goal:** Full rewrite of `/teacher-app/*` against the new data model. Auth-free (sample integration model, D-9). Real LPs/exams from cache. Mid-year onboarding. Mastery entry. SLO progress view. Book reader.

**Bead:** `feat-v2-phase-4-teacher-app`.

**Pre-reqs:** Phase 3 complete on staging (cached LPs exist for the demo class).

**Deliverables:**
- `webapp/app/teacher-app/` deleted and rebuilt from scratch (D-35)
- New page set:
  - `/teacher-app/today` — today's slot with real LP/exam links
  - `/teacher-app/classes` — list of CSTs (already works conceptually; rewire to new API)
  - `/teacher-app/classes/[cst_id]` — class detail with tabs: Lessons / Assessments / Timetable / Book / SLO Progress
  - `/teacher-app/calendar` — week view with deep links
  - `/teacher-app/onboarding/[cst_id]` — mid-year onboarding wizard
  - `/teacher-app/quick-lp` (kept; rewire to new API)
  - `/teacher-app/quick-exam` (kept; rewire to new API)
  - `/teacher-app/classes/[cst_id]/assessments/[slot_id]/results` — mastery entry form
- Aesthetic kept (amber/serif, D-36); only the data and routes change
- Reuses existing shadcn components where possible

**NOT in this phase:** dashboard pages (Phase 5).

---

## Feature order

1. **F4.1** — Delete existing `webapp/app/teacher-app/` and `webapp/app/dashboard/` (clean slate)
2. **F4.2** — Rebuild api client (`webapp/lib/dars-api.ts`) matching new endpoints
3. **F4.3** — Teacher app shell: layout, top nav, banner, no auth
4. **F4.4** — `/teacher-app/today` rebuilt
5. **F4.5** — `/teacher-app/classes` rebuilt
6. **F4.6** — `/teacher-app/classes/[cst_id]` — Lessons tab
7. **F4.7** — `/teacher-app/classes/[cst_id]` — Assessments tab
8. **F4.8** — `/teacher-app/classes/[cst_id]` — Timetable tab
9. **F4.9** — `/teacher-app/classes/[cst_id]` — Book tab (book reader, D-A1)
10. **F4.10** — `/teacher-app/classes/[cst_id]` — SLO Progress tab
11. **F4.11** — `/teacher-app/calendar` rebuilt with deep links
12. **F4.12** — `/teacher-app/onboarding/[cst_id]` mid-year wizard
13. **F4.13** — Mastery entry form
14. **F4.14** — Quick LP / Quick Exam pages rewired
15. **F4.15** — Loading / error / empty states across all pages

---

## F4.1 — Delete existing teacher app and dashboard

**Motivation:** D-35. Clean slate.

**Spec:**
- `rm -rf webapp/app/teacher-app/`
- `rm -rf webapp/app/dashboard/`
- `rm -f webapp/lib/school-api.ts` (old API client)
- Update top-level `app/page.tsx` and `app/layout.tsx` if they reference deleted routes
- Webapp still compiles (`npm run build`)

**Test plan:** `npm run build` exits 0.

**Acceptance:** clean repo, no orphan references.

---

## F4.2 — Rebuild API client

**Motivation:** All teacher app and dashboard pages call the same client.

**Spec:**
- File: `webapp/lib/dars-api.ts`
- Async `fetch`-based client (no extra deps)
- Auth: reads API key from `localStorage.getItem('dars_org_api_key')` and sends as `X-API-Key` header (same convention dars uses today)
- Base URL from `process.env.NEXT_PUBLIC_API_URL`
- TypeScript interfaces for every response model (auto-generated from OpenAPI is ideal but for v1 hand-author; doable since the API set is finite)
- Functions per endpoint group:
  - `tenancy`: `getMyOrg()`, `getSchools()`, `getTeachers()`, `getCSTs()`, `getCST(id)`
  - `curriculum`: `getCurriculums()`, `getSLOs(...)`, `getSubSLOs(slo_id)`
  - `books`: `getBook(id)`, `getBookChapters(book_id)`, `getTopic(id)`
  - `breakdowns`: `getBreakdownsForCST(cst_id)`, `getMyClassBreakdown(cst_id)`
  - `slots`: `getLessonSlots(cst_id)`, `getAssessmentSlots(cst_id)`, `markTaught(slot_id)`, `skipLesson(slot_id)`, `completeAssessment(slot_id)`
  - `generations`: `getGeneratedLP(id)`, `getGeneratedExam(id)`, `refreshLP(id)`, `refreshExam(id)`
  - `today`: `getToday()`
  - `calendar`: `getCalendar(week_start)`
  - `progress`: `getSubSLOCoverage(cst_id)`, `getCSTState(cst_id)`
  - `onboarding`: `onboardCST(cst_id, position)`
  - `mastery`: `submitExamResults(slot_id, results)`

**Test plan:** type-check passes; smoke test against staging.

**Acceptance:** client compiles, function signatures match server.

---

## F4.3 — Teacher app shell

**Motivation:** Layout shared across all teacher pages.

**Spec:**
- `webapp/app/teacher-app/layout.tsx`
- Layout structure:
  - Top: amber banner with "Sample Integration — this is what a teacher's experience could look like. Build your own using Dars API."
  - Top nav: Today | My Classes | Calendar | Quick LP | Quick Exam (links)
  - Auth: reads `dars_org_api_key` from localStorage; if missing, redirects to a "set API key" page (`/teacher-app/setup`). The setup page accepts a raw API key and saves it. No password.
  - Identifies the teacher via the org's `default_teacher_id` (returned from `getMyOrg()`). Teacher app operates as that teacher.
- Mobile responsive (it's a teacher tool; most use phones)
- Amber primary, slate neutrals, Tailwind utilities

**Test plan:** navigation works, banner shows, setup flow works.

**Acceptance:** ready to host all child pages.

---

## F4.4 — `/teacher-app/today`

**Motivation:** Most-used page. Teachers open Dars, see today, click LP, mark taught.

**Spec:**
- Calls `getToday()` → array of TodayEntry per CST
- For each entry:
  - Class header (class name, subject, teacher name)
  - Previous taught lesson (small, faded)
  - Today's primary card:
    - If `assessment_slot` is populated → FA/SA card (rose for FA, violet for SA). Title, day number, "View Exam" button → opens slide-over with rendered ExamPaperView. "Record Results" button → navigates to mastery entry form.
    - Else if `next_planned_slot` → lesson card. Title, lp_type, day number, "View LP" button → slide-over with rendered HTML. "Mark Taught" button.
    - Else → "No teaching today" empty state
- LP and Exam content come from `getGeneratedLP(id)` / `getGeneratedExam(id)`. If status=READY → render. If PENDING/IN_FLIGHT → poll every 3s. If ERROR → show "LP unavailable — contact admin," still allow mark-taught.

**Test plan:** seed should produce a CST whose today resolves to a real slot; LP slide-over shows real HTML.

**Acceptance:** every UX state covered (LP ready, LP loading, LP error, today is FA, today is empty).

---

## F4.5 — `/teacher-app/classes`

**Motivation:** Teacher picks their class.

**Spec:**
- Lists the teacher's CSTs (`getCSTs()` filtered to this teacher implicitly via the org's `default_teacher_id`)
- Each card: class name, subject, "next up: Day N — title", progress bar (taught slots / total slots), "View" button
- Click → `/teacher-app/classes/{cst_id}`

**Test plan:** seed has one CST; shows it correctly.

**Acceptance:** UX is browsable.

---

## F4.6 — Class detail: Lessons tab

**Motivation:** Browse all lesson slots in the class breakdown.

**Spec:**
- Default tab on class detail page
- Lists all lesson slots ordered by position, grouped by breakdown chapter
- Each slot: position, title (= topic title), lp_type badge, status (planned/taught/skipped), action buttons:
  - "View LP" → slide-over with HTML (always available; falls back to error message if LP status=ERROR per D-50)
  - "Mark Taught" (if planned)
  - "Skip" (if planned)
- Sticky chapter headers
- "Generate LP" button removed — generation is admin-side, batched on breakdown publish (D-46, D-48)

**Test plan:** all slots show; mark-taught flips the status badge in-place.

**Acceptance:** entire chapter visible, smooth scroll, mark-taught works.

---

## F4.7 — Class detail: Assessments tab

**Motivation:** Browse all assessments.

**Spec:**
- Lists all assessment slots ordered by position
- Each slot: position, type badge (FA rose / SA violet), title (= the assessment's topic set summary), status, "View Exam" + "Record Results" buttons
- "Record Results" → mastery entry form (F4.13)
- "Generate Exam" button removed

**Test plan:** assessment slots visible; navigation to results form works.

**Acceptance:** assessments fully navigable.

---

## F4.8 — Class detail: Timetable tab

**Motivation:** Show class days; allow teacher overrides (sick day → add holiday).

**Spec:**
- Top: Mon-Fri pills (which days the CST meets, from timetable)
- Below: list of teacher-level holidays (CST overrides) for this AY
- "Add personal holiday" button → date picker + name field → POST `/api/v1/csts/{id}/holiday-overrides`
- Read-only display of org and school holidays (with a "+" badge if added by an override at lower level)

**Test plan:** add a CST holiday; verify it appears.

**Acceptance:** holiday management works at the teacher level.

---

## F4.9 — Class detail: Book tab

**Motivation:** D-A1's vision: show the book the teacher is using, with coverage overlay.

**Spec:**
- Sidebar: chapter list (numbered)
- Main: selected chapter's `chapter_text` rendered as plain HTML (preserve paragraph breaks)
- Topic boundaries marked visually (e.g. shaded background per topic)
- For each topic: small status indicator showing if the topic's sub-SLOs are taught (computed from `cst_sub_slo_coverage`)
- Click a topic → shows its sub-SLOs in a side panel with mastery if assessed
- Read-only; no edits to the book itself

**Test plan:** book renders; topic boundaries clear; status indicators reflect mark-taught state.

**Acceptance:** teachers can see the book and what they've covered.

---

## F4.10 — Class detail: SLO Progress tab

**Motivation:** D-A1's reporting goal. "Have I taught these SLOs?"

**Spec:**
- Top-level: list of SLOs for this class's `(curriculum, grade, subject)`
- For each SLO: bar showing taught/total sub-SLO ratio
- Click an SLO → expand to see sub-SLOs with status (taught / not taught / unknown) and mastery if any FA/SA assessed them
- Filter by chapter
- Read-only

**Test plan:** seed has known coverage; verify counts match.

**Acceptance:** matches mental model "what have I covered?"

---

## F4.11 — `/teacher-app/calendar`

**Motivation:** Week view; deep links into class detail.

**Spec:**
- Calls `getCalendar(week_start)` → days with projected slots
- Mon-Fri grid (no Saturday per D-27)
- Each cell: list of slot pills (lesson amber, FA rose, SA violet)
- Click a pill → `/teacher-app/classes/{cst_id}?tab=lessons&slot={slot_id}` (already supported by current FE; rebuild matches)
- Prev/next week nav

**Test plan:** calendar matches today endpoint; click flows work.

**Acceptance:** consistent with today; nav works.

---

## F4.12 — Mid-year onboarding wizard

**Motivation:** D-12. Teacher (or org admin acting for them) sets `current_sequence_position`.

**Spec:**
- Page: `/teacher-app/onboarding/[cst_id]`
- Step 1: "Where are you in this class?" Two dropdowns: chapter (from breakdown), day-within-chapter
- Step 2: Confirm — "You'll start at Day X (overall position Y). Previous lessons are marked as 'unknown' in your coverage." 
- Submit → POST `/api/v1/csts/{id}/onboard` with chapter + day
- Redirect to `/teacher-app/today`

**Auto-trigger:** if a CST's `joined_at_position` equals 1 AND there's no mark-taught history AND today is more than 7 days into the academic year, the today page shows a banner "It looks like you're joining mid-year. [Set your starting point]."

**Test plan:** wizard completes; cst_state updated; today page shows the right slot.

**Acceptance:** mid-year flow is one screen, two dropdowns, one submit.

---

## F4.13 — Mastery entry form

**Motivation:** D-32. Teacher records "X out of N got this right" per question.

**Spec:**
- Page: `/teacher-app/classes/[cst_id]/assessments/[slot_id]/results`
- Top: assessment metadata, "Students present" input (default = class size)
- Body: one row per question. Display question text + correct answer. Input field: "How many got this right? out of N."
- "Save & Submit" → POST `/api/v1/class-assessment-slots/{id}/results` body `{ students_present, per_question: [{ question_index, students_correct }] }`
- Server computes per-sub-SLO mastery using question's sub_slo_id from the tagging (F3.9), stores in `sub_slo_mastery`
- Idempotent: re-submitting overwrites
- Mark assessment slot as `completed` automatically

**Test plan:** submit, verify mastery rows; mastery rolls up correctly.

**Acceptance:** mastery flow complete; data shows in SLO Progress tab.

---

## F4.14 — Quick LP / Quick Exam

**Motivation:** Kept for power-user / SDK demonstration purposes; rewire to new API.

**Spec:**
- `quick-lp/page.tsx`:
  - Form: subject, grade, page_content (textarea — teacher pastes content directly OR selects a topic from a dropdown which auto-fills topic_text), lp_type, optional `class_strength`, `generate_bilingual`
  - Submit → calls our `/api/v1/quick-lp` endpoint (which proxies to LP Assistant directly, no caching, returns the result)
  - Display result as slide-over with HTML
- `quick-exam/page.tsx`: similar
- New backend endpoint: `POST /api/v1/quick-lp` (uncached, one-off generation for the form)

**Test plan:** generate via form; result renders.

**Acceptance:** quick-LP/exam work standalone.

---

## F4.15 — Loading / error / empty states

**Motivation:** Polish. Teachers see broken UI when things fail; we cover every state.

**Spec:**
- Every page: loading spinner during initial fetch
- Every page: error banner with retry button if fetch fails
- Empty states: 
  - "No classes assigned to you yet"
  - "No teaching today"
  - "No assessments yet"
  - "No SLOs configured"
- 404 / 403 handling: show friendly message, not raw error

**Test plan:** kill the API; verify error banners; kill the network mid-flight; verify recovery.

**Acceptance:** no page ever crashes the browser.

---

## Phase 4 wrap-up checklist

- [ ] All old webapp deleted
- [ ] New API client compiles + matches server
- [ ] Today page renders real data with real LP slide-overs
- [ ] Class detail tabs (Lessons, Assessments, Timetable, Book, SLO Progress) all work
- [ ] Calendar deep-links work
- [ ] Mid-year wizard works
- [ ] Mastery entry rolls up to per-sub-SLO mastery
- [ ] Quick LP / Exam pages work
- [ ] Loading/error/empty states everywhere
- [ ] Staging deployed; manual smoke test green end-to-end

Open Phase 5 bead.
