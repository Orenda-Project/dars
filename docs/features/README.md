# Features

One folder per feature under `docs/features/<slug>/`. Each folder has its own `README.md`, `ONRAMP.md` (after plan approval), `01-decision-log.md`, and one or more phase docs. See `dars/.claude/skills/feature/SKILL.md` for the workflow.

The v2 rebuild (`docs/plans/2026-05-15-dars-v2-rebuild/`) predates this convention and stays where it is; new features start here.

## Active

- [class-timeline-view](class-timeline-view/README.md) — replaces the teacher app's separate Lessons + Assessments tabs with one **unified, dated timeline**: lessons + assessments interleaved by position, stamped with projected dates from the backend projector, grouped by chapter, with a "you are here" marker and quiet generation status. New `GET /csts/{id}/timeline` endpoint (Phase 1) + Timeline tab (Phase 2). Phase 1 in flight.
- [class-today-dashboard](class-today-dashboard/README.md) — new **Today** tab as the default class view in the teacher app: today's date, today's LP/assessment with view + mark-taught, a Covered/Now/Next strip, and a sub-SLO coverage meter. Frontend-only. Phase 1 in flight.
- [ncp-english-g1-seed](ncp-english-g1-seed/README.md) — real NCP curriculum data (English × G1) alongside the synthetic Dars seed: SLOs from `fde_staging.slo_ncpslo`, sub-SLOs via Schema-style breakdown, lp_type via Claude, book 1171 prose from `book.book_text`. Phase 1 in flight.

## Closed

- [lp-showcase-multigrade](lp-showcase-multigrade/README.md) — 3 multi-grade LPs (G2–G3, G4–G5, G1–G5) added to the public showcase via LP Assistant's multigrade endpoint + Python renderer for its JSON response. Shipped 2026-05-21 via PR #88.
- [breakdown-slot-editing](breakdown-slot-editing/README.md) — org-admin per-slot editing (slot_type / lp_type / topic_id) + add/delete in draft org breakdowns. Shipped 2026-05-20 via PR #84.
- [lp-slo-injection-and-linkage](lp-slo-injection-and-linkage/README.md) — inject topic sub-SLOs into LP Assistant `custom_prompt` and persist the requested set on `generated_lps`. Shipped 2026-05-20 via PR #82.
