# Class Today Dashboard

Replaces the class detail page's current default tab (Lessons) with a **Today**
overview: a small dashboard for one class that answers "what do I do in this
class today?" — surfacing today's date, today's lesson plan **or** assessment
(whichever is scheduled), and a progress strip showing what's been **covered**,
where the class is **now**, and what's **next**. From this page a teacher can
open the LP/exam and mark the lesson taught without leaving the overview.

The page is frontend-only: it composes data already exposed by the Dars API
(`/api/v2/today` filtered to the class's CST, the per-CST lesson-slots list, and
sub-SLO coverage). It becomes the default view when a teacher opens a class; the
existing Lessons / Assessments / Timetable / Book / SLO Progress tabs remain.

## Documents (precedence order)

1. [01-decision-log.md](01-decision-log.md) — D-N references are canonical
2. [00-glossary.md](00-glossary.md) — terminology
3. [03-phase-1-today-dashboard.md](03-phase-1-today-dashboard.md) — the single phase
4. running code — last; code may be stale

If two docs disagree, this order wins. Code is lowest authority.
