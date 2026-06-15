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

**Built (2026-06-15).** Frontend-only, on top of Phases 1+2 (commit `bf58635`).

### Files created
- `webapp/app/teacher-app/classes/[cst_id]/chapters/[position]/page.tsx` — the Chapter Page (F-3.1/F-3.2).

### Files modified
- `webapp/components/templates/class-syllabus-tab.tsx` — `PathRow` → navigation `Link`; exported shared pieces (F-3.3).
- `webapp/app/teacher-app/classes/[cst_id]/page.tsx` — removed dead inline-expand plumbing; pass `cstId` to the syllabus tab.

### F-3.1 / F-3.2 — Chapter Page
- `"use client"`, reads `cst_id` + `position` via `useParams<{ cst_id; position }>()`, `pos = Number(position)` (per the spec + the bundled `use-params.md`; the existing class detail page uses the same `useParams` pattern, so no `await params`/`use(params)` plumbing).
- Self-fetching (D-10): on mount, `Promise.allSettled([getSyllabus, getTimeline, today.get])` under a `cancelled` guard. Today is fetched too so the "Now" marker (`currentSlotId`) can pin today's slot exactly as the class detail page does. Shell + "← Back to syllabus" link paint immediately; body shows "Loading chapter…" until the syllabus lands, then "Chapter not found" (with back link, no crash) for an out-of-range position.
- Resolves the chapter via `chapters.find(c => c.position === pos)` and its slots via `timeline.filter(t => t.breakdown_chapter_position === pos)`, position-sorted (D-9).
- Header reuses the exact `PathRow` presentation by importing `formatDate` + `ChapterStatusBadge` (newly exported from `class-syllabus-tab.tsx`) plus the same `Ch {n} · {title}` / `{slot_count} periods` / `formatDate(start)→formatDate(end)` strings — no duplicated date logic.
- Body renders `ChapterContents` (now exported from `class-syllabus-tab.tsx` — D-11), so the lesson/assessment rows are the same `TimelineRow`s with the Phase-2 compact LP-type badge; not re-styled.

### How the Chapter Page wires its handlers
The page owns the same slot-action surface the class detail page has, copied over: `openLP`, `onTimelineViewLP`, `onTimelineViewExam`, `onTimelineMarkTaught` (lesson → mark-taught, assessment → complete), `onTimelineSkip`, `generateLPAndPoll` + `onTimelineGenerateLP`, `generateExamAndPoll` + `onTimelineGenerateExam`, `markTaughtById`, the `rowCallbacks` useMemo, `currentSlotId` useMemo, and the `{ kind; slotId; title; subtitle }` drawer state with `currentSlotId`/`generatingSlotId`/`generatingExamSlotId`/`busySlotId`. Each handler's `refetch` reloads **this page's** timeline (`loadTimeline`); mark-taught/skip/complete also re-fetch the syllabus (chapter status + slot_count can change). The slide-over renders at the bottom exactly like the class detail page: `<SlideOver open={drawer!==null} …>` containing `<LPViewer slotId/>` or `<ExamViewer slotId/>`. Result: a superset of the old inline accordion — View LP, View exam, Mark taught, Skip, Generate LP (+poll), Generate exam (+poll) all work.

### F-3.3 — syllabus row navigates instead of expanding
`PathRow` is now a `next/link` `Link` to `/teacher-app/classes/${cstId}/chapters/${ch.position}`; the whole row header is the link target. The "Generate chapter plan" button uses `e.preventDefault()` + `e.stopPropagation()` so it acts without navigating. The disclosure caret is a static right chevron (`›`, no rotation = "go to page"). Added a `cstId: string` prop to `ClassSyllabusTab`, threaded from the page. The chapter card summary (number, title, status, periods, dates) is unchanged.

### What was removed from the syllabus tab + page
- **`class-syllabus-tab.tsx`:** dropped the inline-expand props from `SyllabusTabProps` and `ClassSyllabusTab` (`timeline`, `currentSlotId`, `expandedChapterId`, `onToggleChapter`, `rowCallbacks`, `generatingSlotId`, `generatingExamSlotId`, `busySlotId`) and the `itemsByPosition` map; `PathRow` lost `expanded`/`onToggle`/`ChapterContents`. `ChapterContents` itself is **kept and exported** (shared by the Chapter Page). `formatDate`, `ChapterContents`, and the chapter `StatusBadge` (renamed `ChapterStatusBadge` on export) are now exported.
- **`page.tsx`:** removed `expandedChapterId` state, `onToggleChapter`, `rowCallbacks` (useMemo), `currentSlotId` (useMemo), and the six `onTimeline*` handlers (`onTimelineViewLP/ViewExam/MarkTaught/Skip/GenerateLP/GenerateExam`) — all of which existed *only* to back the inline accordion. The `<ClassSyllabusTab>` call site now passes just `data` / `cstId` / `onBreakDown` / `busyChapterId`. Removed the now-unused `TimelineRowCallbacks` import.

### Deliberately KEPT (still used elsewhere — not dead)
- `timeline` state + `timelineError` + `loadTimeline`, and the `?slot=` deep-link `useEffect` (`openLP`): the calendar template deep-links to `…?tab=lessons&slot=<id>`, which `asTab` maps to the **syllabus** tab; the `slotFocus` effect needs `timeline` loaded to find that slot and open its LP slide-over. Per "when in doubt, leave the load in place," `loadTimeline()` still fires on syllabus-tab activation. The `timelineError` banner above the syllabus tab is preserved.
- `generateLPAndPoll` / `generateExamAndPoll`, `markTaughtById`, `loadToday`, `loadLessons`, `generatingSlotId` / `generatingExamSlotId` / `busySlotId` state: all still used by the **Today** tab (`onTodayGenerateLP`/`onTodayGenerateExam`, the today card's mark-taught/view-LP, its busy/generating flags).

### Verification (in the worktree, after `npm ci`)
- `npx tsc --noEmit` → **exit 0**.
- `npx eslint` on the three files → **exit 0** (clean).
- `npm run build` → **exit 0**, "Compiled successfully"; the new route `ƒ /teacher-app/classes/[cst_id]/chapters/[position]` appears in the route manifest.

### Deviations / ambiguities
- None that required a new decision. The back-link copy ("← Back to syllabus") and styling (`text-sm text-dars-muted` + `hover:text-dars-terra`) match the existing "← All classes" pattern. The chapter `StatusBadge` was exported under the name `ChapterStatusBadge` to avoid colliding with the unrelated `StatusBadge` in `class-timeline-tab.tsx` (different visual contract).
