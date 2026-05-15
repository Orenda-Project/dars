# Phase 5: Dashboard

**Goal:** Full rewrite of `/dashboard/*`. Org admin authentication (email/password, D-17). Org setup, school/teacher/class management, curriculum browse, breakdown editor (review draft, edit days, anchor admin-level dates, fork from global), generation progress dashboard, SLO coverage reports, cost/usage views.

**Bead:** `feat-v2-phase-5-dashboard`.

**Pre-reqs:** Phase 4 complete on staging.

**Deliverables:**
- `webapp/app/dashboard/` rebuilt from scratch
- Email/password auth for org admins
- Multi-school IA (one admin oversees N schools)
- Breakdown editor: review draft topics, edit per-chapter days, anchor dates (admin-only), fork from global
- Live batch-generation progress view (D-49)
- Failed LP retry surface (D-50)
- SLO coverage report per class / aggregated across an org
- Cost and usage report
- API key management

---

## Feature order

1. **F5.1** — Dashboard shell: layout, sidebar nav, auth gate
2. **F5.2** — Backend: org admin login endpoints
3. **F5.3** — Login + signup pages (signup = create-org flow)
4. **F5.4** — Org settings (name, curriculum, default teacher, API key view/rotate)
5. **F5.5** — Schools list + create/edit
6. **F5.6** — Teachers list + create/edit per school
7. **F5.7** — Academic years per school
8. **F5.8** — Classes per AY + CST assignment
9. **F5.9** — Curriculum browser: SLOs, sub-SLOs, books, chapters, topics (read-only)
10. **F5.10** — Breakdown editor: list breakdowns; create/fork/edit/publish
11. **F5.11** — Breakdown editor: per-chapter day-budget UI
12. **F5.12** — Breakdown editor: per-slot detail and anchor placement
13. **F5.13** — Generation status dashboard (live progress)
14. **F5.14** — Failed LP retry surface
15. **F5.15** — SLO coverage report (per class + org-wide)
16. **F5.16** — Cost & usage report
17. **F5.17** — Holiday management (org + school overrides)

---

## F5.1 — Dashboard shell

**Motivation:** Layout + nav for all dashboard pages.

**Spec:**
- `webapp/app/dashboard/layout.tsx`
- Sidebar nav: Overview | Schools | Curriculum | Breakdowns | Generations | Reports | Settings
- Auth gate: reads session cookie; redirects to `/dashboard/login` if missing
- Top bar: org name + admin name + logout
- Desktop-first design (admins use laptops); responsive but not mobile-optimized

**Test plan:** auth flow gates pages correctly.

**Acceptance:** shell works; nav routes to placeholder pages.

---

## F5.2 — Backend: org admin login

**Motivation:** D-17. Email/password for humans.

**Spec:**
- Endpoint: `POST /api/v1/admin/signup` body `{ email, password, name, org_name }` → creates Org + OrgAdmin + first API key. Returns `{ session_token, org_id, api_key }`. v1 quality: no email verification.
- Endpoint: `POST /api/v1/admin/login` body `{ email, password }` → returns session token if creds valid
- Endpoint: `POST /api/v1/admin/logout` → invalidates session
- Endpoint: `GET /api/v1/admin/me` → current admin + org info
- Sessions stored in a `sessions` table or as signed JWTs (pick one; JWT simpler for v1, table easier to invalidate). **Pick: session table** (`session_token PK, org_admin_id, expires_at`). One signed token derived from row id; lookup on every request.
- Password hashing: bcrypt with cost factor 12

**Test plan:**
- Signup → login → me works
- Wrong password → 401
- Logout → token invalidated

**Acceptance:** auth backend works.

---

## F5.3 — Login + signup pages

**Spec:**
- `/dashboard/login` — email + password form
- `/dashboard/signup` — org_name + admin email + password + admin name → creates org + admin
- Both pages save session token to localStorage `dars_admin_session`
- After login, fetch `/api/v1/admin/me`; store API key + org info locally
- Redirect to `/dashboard/overview` after login

**Test plan:** signup → land on dashboard. Logout → land on login.

**Acceptance:** flows work.

---

## F5.4 — Org settings

**Spec:**
- Page: `/dashboard/settings/org`
- Shows: org name (editable), curriculum (read-only since picked at signup; D-25), default teacher (dropdown of all teachers in the org)
- API key section: shows key prefix (`dk_test_a1b2…`), "Rotate" button (generates new key, invalidates old; displays once)
- "Copy API key" button (only on rotate, never persistent display)

**Spec backend:**
- `PATCH /api/v1/orgs/me` body `{ name?, default_teacher_id? }`
- `POST /api/v1/orgs/me/rotate-api-key` → returns new key + invalidates old

**Test plan:** rotate key → old key returns 401; new key works.

**Acceptance:** settings work.

---

## F5.5 — Schools

**Spec:**
- Page: `/dashboard/schools`
- List schools for the org
- "Add School" → modal: name input → POST
- Each school: name, count of classes, count of teachers, "Manage" link → `/dashboard/schools/[id]`
- School detail page: edit name, view teachers, view classes

**Spec backend:**
- `POST /api/v1/schools` body `{ name }`
- `PATCH /api/v1/schools/{id}` body `{ name }`

**Test plan:** create school → appears in list. Edit name → updates.

**Acceptance:** schools CRUD works.

---

## F5.6 — Teachers

**Spec:**
- Page: `/dashboard/schools/[id]/teachers`
- List teachers in this school
- "Add Teacher" modal: name, optional email
- Each teacher: name, count of CSTs, "Edit" / "Delete" buttons

**Spec backend:**
- `POST /api/v1/teachers` body `{ school_id, name, email? }`
- `PATCH /api/v1/teachers/{id}`
- `DELETE /api/v1/teachers/{id}` (soft delete; sets `is_active=false`)

**Acceptance:** teacher CRUD per school.

---

## F5.7 — Academic Years

**Spec:**
- Page: `/dashboard/schools/[id]/academic-years`
- List AYs, create new (name, start, end)
- Each AY: range, count of classes, "Manage Classes" link

**Spec backend:**
- `POST /api/v1/academic-years` body `{ school_id, name, start_date, end_date }`
- `PATCH /api/v1/academic-years/{id}`

**Acceptance:** AY CRUD.

---

## F5.8 — Classes and CST assignment

**Spec:**
- Page: `/dashboard/schools/[id]/academic-years/[ay_id]/classes`
- List classes in this AY
- "Add Class" modal: grade dropdown, section input, name (auto-generated from grade+section)
- Each class: list of CSTs (one per subject); "Add Subject" → modal: subject dropdown + teacher dropdown + book dropdown (filtered by curriculum+grade+subject)
- Each CST: subject, teacher, book, "Edit" / "Remove"
- Removing a CST cascades to its slots (warn + confirm)

**Spec backend:**
- `POST /api/v1/classes` body `{ school_id, academic_year_id, grade_id, section }`
- `POST /api/v1/csts` body `{ school_class_id, subject_id, teacher_id, book_id }`
- `PATCH /api/v1/csts/{id}` body `{ teacher_id?, book_id? }`
- `DELETE /api/v1/csts/{id}` (soft delete with cascade warning)

**Acceptance:** classes + CSTs fully manageable.

---

## F5.9 — Curriculum browser

**Motivation:** Admins want to see what they're teaching before authoring a breakdown.

**Spec:**
- Page: `/dashboard/curriculum`
- Tabs: SLOs / Books / Topics
- SLOs tab: list SLOs filtered by grade + subject; expand to see sub-SLOs
- Books tab: list books in the org's curriculum; click → book detail with chapter list
- Book detail: list chapters; click → chapter detail with `chapter_text` preview + topics list
- Topic detail: shows `topic_text` and linked sub-SLOs
- Read-only (curriculum is global, D-24)

**Acceptance:** admin can browse the entire curriculum.

---

## F5.10 — Breakdown editor: list + create/fork/edit/publish

**Motivation:** Core admin job. Manage org-level breakdowns; review/publish drafts.

**Spec:**
- Page: `/dashboard/breakdowns`
- Lists breakdowns visible to this org (org's own + the global it could fork from)
- For each: scope, curriculum, grade, subject, status, "View" / "Edit" / "Fork" / "Publish" / "Delete" buttons
- "New Breakdown" button → wizard:
  - Step 1: pick global breakdown to fork (must exist) OR start from scratch (will use F2.5 auto-build)
  - Step 2: confirm details → POST `/api/v1/breakdowns/{global_id}/fork-org` or `/api/v1/breakdowns/auto-build` then convert to org scope
- "Publish" button: confirms + calls `/api/v1/breakdowns/{id}/publish`
- "Fork to Class" inline action lets admin create a class-scope breakdown for a specific CST (one-click for each class that should follow this org's plan)

**Acceptance:** admins can manage their org's breakdowns lifecycle.

---

## F5.11 — Breakdown editor: per-chapter day budget

**Motivation:** D-28 — module suggests, admin overrides.

**Spec:**
- On breakdown detail page (draft only): list of chapters with: position, title, suggested days (from auto-build), current days (editable)
- Editing a chapter's days triggers a re-sequence: when admin saves, server regenerates slots for that chapter within the new budget (calls F2.5 logic for that chapter only)
- Total days display at top: 180 (planned) / 195 (current) → admin sees over-budget warnings
- Re-order chapters via drag-and-drop or up/down arrows

**Spec backend:**
- `PATCH /api/v1/breakdowns/{id}/chapters/{chapter_id}` body `{ teaching_days?, position? }`
- After change, server regenerates the slots for that chapter; returns updated slot list

**Acceptance:** admin sees and edits day budgets; sequence regenerates correctly.

---

## F5.12 — Breakdown editor: per-slot detail and anchor placement

**Motivation:** D-7 admins anchor specific slots.

**Spec:**
- Breakdown detail page → click a slot → side panel:
  - Title, type (lesson/FA/SA/revision), lp_type, topic, position
  - "Pin date" toggle → date picker → sets `anchor_date`
  - Conflict warnings shown inline if the anchor causes sequence overflow
  - "Replace topic" dropdown (advanced)
  - "Replace lp_type" dropdown (advanced; bounded by subject's valid list)
- "Save" → PATCH /slots/{id}
- Publish blocked if any conflict unresolved

**Acceptance:** anchors work; conflicts surface.

---

## F5.13 — Generation status dashboard

**Motivation:** D-49. Live progress when batch generation runs.

**Spec:**
- Page: `/dashboard/generations`
- Shows: list of in-flight generation batches (one per recent publish)
- Each: total / pending / in_flight / ready / error counts; progress bar
- Live updates via polling (`GET /api/v1/breakdowns/{id}/generation-status` every 3-5 seconds while batch is non-terminal)
- Click into batch → list of individual generation rows with status; failed rows have "Retry" button

**Acceptance:** progress is visible and updates live.

---

## F5.14 — Failed LP retry surface

**Motivation:** D-50. Admin sees failed generations and can retry.

**Spec:**
- `/dashboard/generations/failures`
- Lists all LP/Exam generation rows with status=ERROR
- For each: cache key, slot reference (which CST is affected), error message, "Retry" button
- Retry: dispatches a new request to LP Assistant/UG_EG, resets status to PENDING

**Spec backend:** `POST /api/v1/generated-lps/{id}/retry`, `POST /api/v1/generated-exams/{id}/retry`

**Acceptance:** retry path works.

---

## F5.15 — SLO coverage report

**Motivation:** D-A1 ultimate goal: "are SLOs being taught?"

**Spec:**
- Page: `/dashboard/reports/slo-coverage`
- Two views:
  1. **Per class** — pick a class (CST); show SLO coverage heatmap (rows = SLOs, columns = ?; or just a list with progress bars). Each SLO has: % sub-SLOs taught, % sub-SLOs mastered (if assessed).
  2. **Org-wide** — aggregate across all CSTs; same SLO list; ratios are class-averaged.
- Filterable by grade + subject + date range

**Spec backend:**
- `GET /api/v1/csts/{id}/sub-slo-coverage` (already in Phase 2)
- `GET /api/v1/orgs/me/coverage-summary?grade_id=&subject_id=` → aggregated per-SLO counts

**Acceptance:** admin can answer "are SLOs being covered?" at both granularities.

---

## F5.16 — Cost & usage report

**Motivation:** D-10.

**Spec:**
- Page: `/dashboard/reports/usage`
- Calls `GET /api/v1/orgs/me/usage?start=&end=`
- Shows: total LPs generated, total exams generated, total cost (in $USD), breakdown by subject + curriculum + month
- Charts: line chart of daily generations + cost

**Acceptance:** usage visibility.

---

## F5.17 — Holiday management

**Motivation:** D-26.

**Spec:**
- Page: `/dashboard/settings/holidays`
- Tabs: Org-level | School-level
- Org-level tab: list org-wide holidays for selected AY; "Add" form (date + name)
- School-level: pick a school, list overrides (additions and removals from org defaults); add/remove
- Teacher-level holidays NOT here (those are in the teacher app, F4.8)

**Acceptance:** holiday flow complete.

---

## Phase 5 wrap-up checklist

- [ ] Dashboard shell + auth working
- [ ] Org/School/Teacher/Class/CST setup flows complete
- [ ] Curriculum browser shows all seeded content
- [ ] Breakdown editor: list, fork, edit days, anchor, publish — all work
- [ ] Generation status dashboard updates live
- [ ] Failed LP retry works
- [ ] SLO coverage report renders per-class and org-wide
- [ ] Usage report shows costs
- [ ] Holidays managed at all 3 levels
- [ ] Staging deployed; manual end-to-end test green (full admin journey: signup → set up class → fork breakdown → publish → see generations → see SLO coverage)

---

## Post-Phase-5 next steps (v2 backlog, not in this plan)

These are explicitly out of scope for v1 but worth listing so the plan reader knows the trajectory:

- **Production migration plan** — separate effort, take production live
- **Per-student mastery tracking** — Student entity, integration with mastery flow
- **Per-school breakdown overrides** — currently org-only (D-23); add school-level if customers ask
- **Multi-curriculum org support** — currently one curriculum per org (D-25); support multiple
- **Multi-book CSTs** — currently one book per CST (D-13)
- **Real teacher auth** — currently auth-free sample; if customers want dars to host the teacher UX
- **i18n** — translated UI; currently English-only
- **Auto-update breakdown forks** — D-18 leaves forks frozen; add "show changes" UI
- **LP regenerate on demand** — D-48 disabled; add when teachers request it
- **Schema's LP observation flow** — Schema has lp_observation_check; could surface in the teacher app as a self-assessment tool
- **Question bank** — taleemabad-core has a curated question bank; importing as a source of seen-questions for exam generation
- **Auto-reteach** — if FA mastery is below threshold, auto-insert a reteaching LP for the missed sub-SLOs
- **NCP and SNC seed** — Phase 1 only seeds Dars Curriculum; import NCP from taleemabad-core; import SNC manually
- **Rate limiting + per-org cost cap** — D-45
- **Observability (Sentry, APM)** — D-44
- **WhatsApp delivery** — push LP / exam URLs to teachers via WhatsApp Business API
- **Mobile app** — wrap the teacher web app or build native; secondary to current web focus
