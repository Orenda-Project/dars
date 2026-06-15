# Phase 3 — Syllabus chapter page (frontend)

Replace the teacher-app syllabus inline-accordion chapter expand with a dedicated per-chapter page (D-8/D-9/D-10/D-11). One PR. Depends on Phase 2 for the `LpContextHeader` (the chapter page renders its slot rows with the compact header).

Precedence: derives from `01-decision-log.md` (D-8…D-11) and `00-glossary.md`. They win on conflict.

Webapp layering (`webapp/CLAUDE.md`): the new `page.tsx` owns hooks/fetch; presentational pieces stay in `templates/`/`molecules/`. **Read the relevant guide in `node_modules/next/dist/docs/` before writing route code — this Next.js has breaking changes from training data.**

Context (from exploration):
- Syllabus is `?tab=syllabus` on `webapp/app/teacher-app/classes/[cst_id]/page.tsx`; data via `slotsApi.getSyllabus(cstId)` (→ `SyllabusForCstResponse.chapters: ClassPathChapter[]`) + `slotsApi.getTimeline(cstId)` (→ `CstTimelineItem[]`).
- Chapter rows render via `PathRow` in `components/templates/class-syllabus-tab.tsx`; expand state is `expandedChapterId`; body is `<ChapterContents>` (renders `TimelineRow`s for the chapter's lessons + assessments).
- Join key: `ClassPathChapter.position` === `CstTimelineItem.breakdown_chapter_position`.
- Existing back-link pattern: `<Link href="/teacher-app/classes/...">← …</Link>` (see `class-detail-template.tsx`).

---

## F-3.1 — The chapter page route (D-8, D-9, D-10)

**Spec.** Add `webapp/app/teacher-app/classes/[cst_id]/chapters/[position]/page.tsx`, a `"use client"` component.
- Read params: `useParams<{ cst_id: string; position: string }>()`; `pos = Number(position)`.
- On mount (`useEffect`), fetch `slotsApi.getSyllabus(cstId)` and `slotsApi.getTimeline(cstId)` in parallel (mirror the existing class-detail loaders — same error/cancel handling).
- Resolve: `chapter = syllabus.chapters.find(c => c.position === pos)`; `items = timeline.filter(t => t.breakdown_chapter_position === pos)`.
- Render immediately (D-10): page shell + back link paint at once; show a light skeleton in the body until data lands; if the position isn't found after load, show a friendly "Chapter not found — back to syllabus" state.
- Back link: `<Link href={\`/teacher-app/classes/${cstId}?tab=syllabus\`}>← Back to syllabus</Link>` at the top.
- Header area: chapter number + title as the page heading, plus its dates/status/slot_count summary (reuse what `PathRow` shows today).

**Acceptance.**
- Direct-navigating to `/teacher-app/classes/<cst>/chapters/3` (fresh load, no in-app nav) renders the page shell + back link instantly and then the chapter's slots.
- Browser refresh and back/forward work (no reliance on parent state).
- Back link returns to `…/classes/<cst>?tab=syllabus`.
- An out-of-range position shows the not-found state, not a crash.

**Dependencies.** Phase 2 (F-2.2) for the header used by the slot rows.

---

## F-3.2 — Render the chapter body with the compact LP-context rows (D-11, D-6)

**Spec.** Reuse the existing `ChapterContents` (and the `TimelineRow` it renders) to list the chapter's lesson + assessment slots on the page. Ensure lesson rows use the Phase-2 compact `LpContextHeader` (or at minimum `lpTypeLabel()` — the timeline items are context-complete: they carry `breakdown_chapter_*`, `topic_title`, `lp_type`). Preserve existing row affordances (view LP slide-over, mark-taught, generate, generate-exam, status) — the page must be a superset of what the inline accordion offered, not a regression.

**Acceptance.**
- The chapter page shows every lesson + assessment slot the inline accordion showed, in the same order, with the same actions working.
- Lesson rows show readable type (no raw `reading`/`comprehension_word_meanings`).
- Assessment rows unaffected by the LP-type changes.

**Dependencies.** F-3.1; Phase 2 (F-2.2, F-2.6).

---

## F-3.3 — Make the syllabus chapter row navigate, not expand (D-8, D-11)

**Spec.** In `components/templates/class-syllabus-tab.tsx`, change `PathRow` from an accordion toggle to a navigation `Link` (or a row whose click pushes `/teacher-app/classes/${cstId}/chapters/${chapter.position}`). Remove the `expandedChapterId` toggle plumbing and the inline `<ChapterContents>` render from the syllabus tab (the body now lives on the page). Keep the chapter card's summary content (number, title, dates, status, slot_count) and the disclosure affordance restyled as "open" (e.g. a chevron pointing right that now means "go to page"). The syllabus tab no longer needs to load the full timeline solely to back inline expansion — but verify nothing else on that tab depends on `timeline` before removing the load; if it does (e.g. the "Now" marker), leave the load.

**Acceptance.**
- Clicking a chapter on `…?tab=syllabus` navigates to its chapter page; no inline accordion remains.
- The syllabus list still shows all chapters with their summaries and statuses.
- No dead state/handlers left behind (`expandedChapterId` and unused props removed cleanly); no console errors.

**Dependencies.** F-3.1.

---

## Out of scope
- The dashboard (admin) syllabus/curriculum views — this is the teacher-app syllabus only.
- Changing the syllabus data endpoints — Chapter Page reuses `getSyllabus` + `getTimeline` as-is.

## Notes from execution
_(append-only; fill in during the phase)_
