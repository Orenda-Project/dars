# Phase 1 — Rename Chapter Breakdown → Syllabus Breakdown

Pure terminology rename (D-1). No behavior change, no schema change. Ships first so
the vocabulary is consistent before demolition. One PR → staging.

**Bead:** `feat-syllabus-breakdown-phase-1-rename`
**Depends on:** nothing.

---

## F1.1 — Rename in product-facing copy + UI

**Spec.** Replace user-visible "Chapter Breakdown" → "Syllabus Breakdown" in the
dashboard (breakdowns list + detail page headers, labels, helper text) and any teacher-app
copy. Keep DB table names as-is (D-7).

**Acceptance.** No user-visible "Chapter Breakdown" string remains; dashboard reads "Syllabus Breakdown". `grep -ri "chapter breakdown" webapp/` returns only code comments referencing history.

## F1.2 — Rename in API schemas / router naming (non-breaking where possible)

**Spec.** Where it doesn't break the wire contract, rename internal symbols/comments to
"syllabus". Endpoint *paths* can stay `/breakdowns/...` for now (path rename is risky and
not required by D-1); focus on docstrings, comments, and any response copy.

**Acceptance.** `router_breakdown.py` + `schemas_breakdown.py` docstrings/comments use "syllabus" vocabulary. Wire contract unchanged (tests green).

## F1.3 — Rename in docs + persona memory

**Spec.** Update `dars/CLAUDE.md` (Webapp Architecture / any breakdown mention), the
`chapter-breakdown-and-plan` onramp (note the rename + supersession), and the persona
docs. Update the project memory entries that say "Chapter Breakdown".

**Acceptance.** Docs consistently say "Syllabus Breakdown" for the admin artifact; "Chapter Plan" reserved for the teacher per-chapter slots.

---

## Notes from execution

**2026-06-02 — Phase 1 complete (PR open).**
- F1.1: renamed user-visible copy → "Syllabus Breakdown(s)" across dashboard-shell nav, overview stats, generations, breakdowns list, curriculum helper, onboarding-template, class-slos-tab. Routes/identifiers/API-client names left for Phase 2. tsc clean. (Done via agent; ambiguous "breakdown" usages — API-docs prose, SLO-detail expansion, code comments — deliberately left.)
- F1.2: **no-op** — server code never used the literal phrase "Chapter Breakdown" in docstrings; generic "breakdown" terms stay until the Phase 2 code/table rename. CLAUDE.md's only "breakdown" mention (line 80, "lesson breakdown") is the teacher-app/Chapter-Plan concept — left.
- F1.3: added a SUPERSEDED banner to `chapter-breakdown-and-plan/ONRAMP.md` (kept its history per plan-alive rules); fixed one stale memory line. Persona/feature docs use the new vocabulary.
