# Teacher-Adjustable Syllabus (suggestion-led)

> **Status: REOPENED 2026-06-15 (Phase 3 — Revival).** Originally shipped 2026-06-03 (PR
> #109), then frozen read-only by `teacher-readonly-syllabus` (#130/#131). The user has
> reversed that: teachers edit their own class's path again — full pick / set-dates /
> reorder / remove. The class is auto-seeded from the org's published breakdown (kept,
> D-10) and the teacher edits on top. See **[`05-phase-3-revival.md`](05-phase-3-revival.md)**
> and D-9…D-12 in the decision log. D-1…D-8 stand unchanged.

**Scope (deliberately narrow):** let the teacher decide *which chapters to teach, and in
what order*, guided by a recommendation from the global syllabus. That's the whole job.

Today a class is implicitly bound to the published **global** Syllabus Breakdown for its
(curriculum, grade, subject). This feature makes the global **advisory** and gives the
class its own ordered chapter path:

- The class has its **own ordered list of chapters** it will teach (`class_chapters`).
- The global only **recommends** what to teach next. At session start (empty path), the
  app shows *"Nothing planned — the default suggests Chapter 1. What would you like to
  teach?"* — Ch 1 recommended, **any** chapter selectable.
- **Pick a chapter** → records it in the path. **Set its dates.** **Reorder** chapters in
  the path. That's Action 1 — this feature.
- **Break it down** (Action 2) is the **already-shipped** `/plan` flow, unchanged. This
  feature just points it at a chapter from the class path. **What break-it-down generates
  (LPs, assessments, LLM units) is NOT this feature's concern** — that belongs to the
  separate `intelligent-chapter-planner`.

### Explicitly NOT in scope
- How a chapter breaks into LPs/assessments, LPs-only, LLM planning → `intelligent-chapter-planner`.
- Per-class syllabus *scope*/forking (an early draft explored this — dropped, D-1).
- Chapter **status** (in-progress/done) and **locking** taught chapters from reorder are
  **nice-to-have, not blocking** — included as optional polish (Phase 2), can be cut.

---

## Documents

1. [`00-glossary.md`](00-glossary.md) — terms (class path, recommendation, pick, reorder).
2. [`01-decision-log.md`](01-decision-log.md) — frozen decisions D-1….
3. [`02-data-model.md`](02-data-model.md) — `class_chapters` table.
4. [`03-phase-1-class-chapters.md`](03-phase-1-class-chapters.md) — `class_chapters` + pick/date/list + recommended-next (backend). _(shipped #109, mutation layer later removed)_
5. [`04-phase-2-teacher-ui.md`](04-phase-2-teacher-ui.md) — teacher-app: recommendation prompt, pick, set dates, reorder; (optional) status badges + lock. _(shipped #109, later read-only-fied)_
6. [`05-phase-3-revival.md`](05-phase-3-revival.md) — **active.** Restore the mutation layer + editable UI on top of today's auto-seeded, expandable tab (D-9…D-12).
7. [`ONRAMP.md`](ONRAMP.md) — single entry point for any agent picking this up.

## Document precedence

```
1. 01-decision-log.md   (D-N references are canonical)
2. 02-data-model.md     (schema is ground truth)
3. 00-glossary.md       (terminology)
4. phase docs           (specs derived from above)
5. running code         (last; code may be stale)
```

If two docs disagree, this is the order. Surface conflicts; don't silently pick a side.

## Builds on

The shipped `syllabus-breakdown-and-teacher-chapter-plan` (global syllabus + the
break-it-down `/plan` flow + class slots). The global stays global and advisory; the
class's path lives in `class_chapters`. Action 2 (`/plan`) is reused untouched.
