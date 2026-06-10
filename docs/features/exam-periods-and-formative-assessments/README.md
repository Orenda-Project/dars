# Exam Periods & Formative Assessments

Two related additions to the syllabus-breakdown / chapter-planner / calendar subsystem, planned and shipped together because they share the same calendar machinery.

**Exam Periods** let an admin reserve date ranges on a global Syllabus Breakdown (e.g. "1–20 August: Mid-term exams"). Those dates are excluded from teaching-day derivation everywhere — the admin's `derived_teaching_days` display *and* the teacher's real slot projection (`compute_teaching_days`). A lesson or assessment never lands on a reserved exam date, so the period count is an accurate picture of when lesson plans can actually be taught.

**Formative Assessments (FAs)** extend the intelligent Chapter Planner so it *decides* where Formative Assessments belong in a chapter's slot sequence — not just lessons. An FA slot is persisted as a `class_assessment_slot` and carries **Exam Generator inputs** (subject, grade, topics, sub-SLOs, a default formative question config) exactly the way a lesson slot carries Lesson Plan inputs — so an FA slot can drive the existing exam-generation path end-to-end.

---

## Index

1. [00-glossary.md](00-glossary.md) — every capitalised term used below
2. [01-decision-log.md](01-decision-log.md) — **load-bearing**; all D-N decisions with rationale
3. [02-data-model.md](02-data-model.md) — final schema: `exam_periods` table + planner/slot changes
4. [03-phase-1-exam-periods.md](03-phase-1-exam-periods.md) — exam-period storage, calendar exclusion, admin UI
5. [04-phase-2-fa-planner.md](04-phase-2-fa-planner.md) — planner emits FA slots; persist as assessment slots
6. [05-phase-3-fa-exam-inputs.md](05-phase-3-fa-exam-inputs.md) — FA slots → Exam Generator inputs (default config)
7. [ONRAMP.md](ONRAMP.md) — *(written after plan approval)* single entry point for a fresh agent

## Document precedence

If two docs disagree, resolve in this order:

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (schema is ground truth)
3. 00-glossary.md             (terminology)
4. phase docs                 (specs derived from above)
5. running code               (last; code may be stale)
```

Code is **lowest** authority. Surface conflicts; don't silently pick a side.

## Size

**L** — schema change (new table + slot population), a frozen planner-contract change, two backend service paths, calendar-derivation change, admin + teacher UI. Three independently shippable phases.

## Supersedes / relates to

- Builds directly on `syllabus-breakdown-and-teacher-chapter-plan` (D-1..D-16) and `intelligent-chapter-planner`.
- Does **not** supersede them — it extends. Their decisions remain frozen; this folder's log references them where relevant.
