# LP Context Header

Wherever the app shows a Lesson Plan (LP) — today's card, the syllabus/timeline rows, the LP slide-over, the calendar — the **LP type** (e.g. `reading`, `comprehension_word_meanings`) currently appears as tiny, raw, muted/monospace trailing text, and the **Chapter** and **Topic** context is inconsistently present (some sites show topic, some only a `topic_id`, some show nothing). A teacher looking at an LP can't quickly tell *which chapter, which topic, and what kind of lesson* it is.

This feature makes those three facts **clear and consistent** everywhere an LP is shown. It introduces one shared presentation — **topic title as the headline, chapter as a small eyebrow above it, and LP type as a human-readable colored badge** (D-2) — backed by a single label map that turns raw enum values into readable text (`comprehension_word_meanings` → "Comprehension: Word Meanings"; D-3). A small set of backend JOINs fills the data gaps so every LP-display endpoint carries chapter + topic + lp_type together (D-4).

It also restructures the teacher-app **syllabus**: clicking a chapter now opens a **dedicated Chapter Page** (`/teacher-app/classes/[cst_id]/chapters/[position]`) instead of an inline accordion — a self-fetching client route that renders instantly with a back link to the all-chapters list (D-8/D-9/D-10/D-11). That page is the natural home for the new compact LP-context rows.

## Documents (precedence order)

1. [01-decision-log.md](01-decision-log.md) — **canonical**; `D-N` references win
2. [02-data-model.md](02-data-model.md) — backend response-shape deltas (no schema/migration changes)
3. [00-glossary.md](00-glossary.md) — terminology
4. Phase docs:
   - [03-phase-1-backend-context-fields.md](03-phase-1-backend-context-fields.md) — backend: add chapter/topic fields to the LP-display endpoints that lack them
   - [04-phase-2-shared-header-and-labels.md](04-phase-2-shared-header-and-labels.md) — frontend: the `LpContextHeader` molecule + `lpTypeLabel()` map, applied at every LP display site
   - [05-phase-3-syllabus-chapter-page.md](05-phase-3-syllabus-chapter-page.md) — frontend: dedicated per-chapter page in the teacher-app syllabus (replaces inline accordion)
5. [ONRAMP.md](ONRAMP.md) — single entry point for a fresh agent
6. running code — lowest authority

## Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (response shape is ground truth)
3. 00-glossary.md             (terminology)
4. phase docs                 (specs derived from above)
5. running code               (last; code may be stale)
```

If two docs disagree, this order resolves it. Code is lowest authority. Surface conflicts; don't silently pick a side.
