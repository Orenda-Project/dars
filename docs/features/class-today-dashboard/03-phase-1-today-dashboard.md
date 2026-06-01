# Phase 1 — Today dashboard (default class view)

Single phase. Frontend-only. One PR to `staging`. No schema change.

All work is in `webapp/`. Follow the layer rules in `webapp/CLAUDE.md`:
data fetching in `page.tsx`, layout in a `templates/` component, no hooks/fetch
in templates.

## F1.1 — Add `today` as the first tab and the default

**Spec.** In `class-detail-template.tsx`: add `"today"` to `ClassDetailTab` and
prepend `{ key: "today", label: "Today" }` to `TABS`. In `page.tsx`:
`TAB_NAMES` includes `"today"` and `asTab()` defaults to `"today"` (not
`"lessons"`).

**Acceptance.** Opening `/teacher-app/classes/[cst_id]` with no `?tab=` shows the
Today tab highlighted and the Today dashboard rendered. The other five tabs
still work via `?tab=`.

## F1.2 — `ClassTodayTab` template

**Spec.** New `components/templates/class-today-tab.tsx`. Pure layout, all data
via props. Sections, top to bottom:

1. **Date header** — today's date, long form (e.g. "Monday, 1 June 2026"),
   plus class name/subject context already in the page header (don't duplicate).
2. **Today's work card** — the headline. Three states:
   - **Lesson today:** topic title, Day N, LP type, an LP status pill
     (planned / taught / skipped), a **View lesson plan** button (opens the LP
     slide-over) and a **Mark as taught** button (hidden once taught).
   - **Assessment today:** assessment type (formative/summative), topic titles,
     a **View exam** button (opens the exam slide-over / placeholder).
   - **Nothing today:** a calm empty state ("No class scheduled today") with a
     pointer to what's next (from the progress strip).
3. **Progress strip — Covered · Now · Next.** Three compact cells:
   - *Covered:* count of taught lesson slots, e.g. "12 lessons taught".
   - *Now:* current slot's Day N + topic (today's slot, else next planned — D-3).
   - *Next:* the following planned slot's Day N + topic, or "End of course".
4. **Coverage meter** — a thin progress bar: `taught / total` sub-SLOs as a
   percentage, with the raw fraction as a label. Hidden if coverage is empty.

Use Dars tokens only (`text-dars-ink`, `bg-dars-parchment`, `border-dars-rule-light`,
`text-dars-terra`, etc.). Match the visual language of the existing tab
templates (`class-lessons-tab.tsx`, `today-template.tsx`).

**Acceptance.** Given props for each of the three "today's work" states, the
card renders the right content and buttons. Progress strip and coverage meter
render from props. No hooks, no fetch, no routing logic in the template.

## F1.3 — Wire data in `page.tsx`

**Spec.** Add a `today` branch to the lazy tab-load effect. The Today tab needs:
- `todayApi.get()` → find the `TodayEntry` whose `cst_id === cstId` (may be
  undefined). Gives today's `lesson_slot` / `assessment_slot`.
- The lessons list (`loadLessons()` data — reuse; trigger it for the today tab
  too) → for covered count, Now fallback, and Next. Derive:
  - `coveredCount` = lessons with `status === "taught"`.
  - `nowSlot` = today's lesson slot if present, else lowest-`position` lesson
    with `status === "planned"` (D-3).
  - `nextSlot` = lowest-`position` planned lesson with `position > nowSlot.position`.
- `progressApi.getSubSLOCoverage(cstId)` → `taught / total` for the meter
  (reuse the SLO tab's loader pattern; only the counts are needed here).

Map topic titles via the lessons list (`topic_title` is already on
`ClassLessonSlotListItem`); for the assessment-today case use the today entry's
`topic_ids` count (titles aren't on the today payload — show count, consistent
with the existing `onViewExam` subtitle).

Reuse the existing `onViewLP`, `onViewExam`, `onMarkTaught`, `drawer` state, and
`SlideOver`/`LPViewer` already in `page.tsx`. The today entry's slot ids map to
the same slot objects, so resolve the matching `ClassLessonSlotListItem` from
the lessons list before calling `onViewLP`/`onMarkTaught` (those handlers take
the list item).

**Acceptance.**
- Today tab loads today's slot + progress on first open; switching away and back
  doesn't refetch (lazy, same as other tabs).
- View LP opens the slide-over with the correct slot; Mark as taught calls
  `slotsApi.markTaught` and refreshes covered count + the today card.
- On a no-class day the card shows the empty state and Now/Next still populate
  from planned slots.
- Errors render via the existing `TabError`; loading via `TabLoading`.

## Dependencies

F1.2 and F1.3 both depend on F1.1 (the tab must exist). F1.3 depends on F1.2
(the template it fills). Build F1.1 → F1.2 → F1.3 in order; all in one PR.

## Notes from execution

_(append during/after execution)_
