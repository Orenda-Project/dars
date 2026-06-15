# Phase 2 — Shared header + labels (frontend)

Introduce the one shared LP-context presentation and apply it everywhere an LP is shown to a teacher (D-2, D-3, D-6, D-7). One PR. Depends on Phase 1 for the slide-over chapter fields and the `/today` topic title.

Precedence: derives from `01-decision-log.md` (D-2/D-3/D-5/D-6/D-7) and `02-data-model.md`. They win on conflict.

Webapp layering (`webapp/CLAUDE.md`): `lpTypeLabel()` is a pure `lib/` helper; `LpContextHeader` is a `molecules/` component (props + atoms/ui only, no hooks, no fetch); page/template files feed it data.

---

## F-2.1 — `lpTypeLabel()` helper (D-3)

**Spec.** Add a pure function in `webapp/lib/` (e.g. `lib/lp-type-label.ts`) mapping raw `lp_type` → human-readable label per the D-3 table. Unknown/`null` values: `null`/empty → return `null` (caller hides the badge); unknown non-empty → title-case the underscore-split raw value as a fallback. Export the map too if a caller needs the full set.

**Acceptance.** Unit-level reasoning: `lpTypeLabel("comprehension_word_meanings")` === "Comprehension: Word Meanings"; `lpTypeLabel("reading")` === "Reading"; `lpTypeLabel("some_future_type")` === "Some Future Type"; `lpTypeLabel(null)` === null. (Add a small test if the webapp has a test runner wired; otherwise verify by usage.)

**Dependencies.** None.

---

## F-2.2 — `LpContextHeader` molecule (D-2, D-6)

**Spec.** Add `webapp/components/molecules/lp-context-header.tsx`. Props:
```
{
  chapterNumber?: number | null;
  chapterTitle?: string | null;
  topicTitle?: string | null;
  lpType?: string | null;
  variant?: "default" | "compact";   // default: "default"
}
```
- **`default`** (D-2): chapter eyebrow on top (`CH {n} · {title}`, uppercase tracking-wide muted `text-[10px]`/`text-xs`, omit silently if no chapter); topic title as the headline (`font-semibold text-dars-ink`, fall back to a muted "Lesson" if no topic); LP-type badge to the right — `rounded-full bg-dars-terra text-dars-parchment text-[11px] font-semibold px-2 py-0.5`, text from `lpTypeLabel(lpType)`, hidden if that's null. Match the existing badge pattern in `reteach-panel.tsx`.
- **`compact`** (D-6): single line — chapter muted, then topic (bold), then the type badge inline; parts separated by `·`/`›`. Truncate topic if long.
- Pure presentation: no hooks, no data fetching (molecule rule). Styling via Dars tokens only.

**Acceptance.** Renders all three when all present; drops the eyebrow when no chapter, the badge when no/unknown-null type, and uses the "Lesson" fallback when no topic — no empty bullets or dangling separators in either variant. Type label is never a raw enum string.

**Dependencies.** F-2.1.

---

## F-2.3 — Apply at the LP slide-over `LPViewer` (D-7)

**Spec.** In `webapp/components/molecules/lp-viewer.tsx`, render `<LpContextHeader variant="default" ... />` above the `CoveredSLOs` section, fed from the already-fetched `ClassLessonSlotDetail` (`detail.chapter_number`, `detail.chapter_title`, `detail.topic_text` as the topic headline, `detail.lp_type`). Add `chapter_number`/`chapter_title` to the `ClassLessonSlotDetail` type in `lib/dars-api.ts` (Phase-1 backend now returns them). `topic_text` can be long — pass it as the topic title (the header truncates in compact; in default it wraps).

**Acceptance.** Opening any LP slide-over shows chapter + topic + a readable type badge at the top, then the SLO chips + body. A slot with no chapter still renders (eyebrow hidden).

**Dependencies.** F-2.1, F-2.2, Phase 1 F-1.2.

---

## F-2.4 — Apply at the Today card (D-2)

**Spec.** In `webapp/components/templates/today-template.tsx`, replace the current subtle inline `· {slot.lp_type}` (the `LessonCard` "Lesson/Revision · reading" line, ~line 285-288) with `<LpContextHeader variant="default" ... />`, fed chapter from the entry's `current_chapter` (chapter_number + title), topic from `slot.topic_title` (Phase-1 F-1.1), and type from `slot.lp_type`. Add `topic_title` to the relevant frontend type(s) (`LessonSlotEntry`) in `lib/dars-api.ts`. Keep the existing slot/Lesson-vs-Revision framing coherent — the header's badge carries the type; the "Revision" notion is conveyed via `lpType="revision"` → "Revision" badge, so the old separate "Revision" tag can be dropped or kept as the eyebrow context, builder's judgment, as long as it's not redundant.

**Acceptance.** The Today lesson card shows chapter eyebrow + topic headline + type badge. No raw `reading` text. The PrevNext "next up" strip continues to work; give it the readable label via `lpTypeLabel()` (it has no topic/chapter, so just swap the raw `next.lp_type` for `lpTypeLabel(next.lp_type)` — a one-line readability fix, not the full header).

**Dependencies.** F-2.1, F-2.2, Phase 1 F-1.1.

---

## F-2.5 — Apply at the dashboard Class Today tab (D-2)

**Spec.** In `webapp/components/templates/class-today-tab.tsx`, the `TodayWorkCard` shows `work.lpType` as muted monospace (~line 239-242) and has `work.topicTitle`. Replace with `<LpContextHeader variant="default" ... />` using the topic title it already has and the lp type via the label map. Chapter may be absent here — header hides the eyebrow gracefully. (If `TodayWork` lacks chapter, do not add a backend call for it in this feature; the eyebrow simply omits — consistent with D-2's graceful-omit rule.)

**Acceptance.** Dashboard Class Today card shows topic headline + readable type badge (chapter eyebrow if available). No raw monospace enum.

**Dependencies.** F-2.1, F-2.2.

---

## F-2.6 — Apply at the timeline / syllabus rows, compact variant (D-6)

**Spec.** In `webapp/components/templates/class-timeline-tab.tsx`, the `KindTag` (~line 353-379) renders the raw `lp_type` as tiny monospace for lessons. Rows already have `breakdown_chapter_position`, `breakdown_chapter_title`, `topic_title`, `lp_type` (context-complete). Replace the lp-type rendering with the compact header or, at minimum, route the type through `lpTypeLabel()` and render it as the compact badge. Keep the row dense — use `variant="compact"`. Revision rows keep their "Revision" treatment (which now equals `lpTypeLabel("revision")`), so unify if clean.

**Acceptance.** Timeline/syllabus lesson rows show chapter · topic · readable type badge on one line, no raw enum, no layout break in the dense row. Assessment rows (no lp_type) are unaffected.

**Dependencies.** F-2.1, F-2.2.

---

## Out of scope (D-5)
- `/me/calendar` cells and `app/dashboard/generations/failures/page.tsx` — unchanged.
- Showcase LPs — they have no `lp_type` in the model; unchanged.

## Notes from execution
_(append-only; fill in during the phase)_
