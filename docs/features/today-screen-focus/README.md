# Today Screen Focus

The teacher app's first screen (`/teacher-app/today`) currently shows, for each
class, a "You're on Chapter N" header, today's lesson card, **and** a Last
lesson / Next lesson strip bracketing today. This feature trims that to **just
today's activity** — the Last/Next strip is removed — and adds a **full SLO
coverage bar** inside each class box so the teacher sees, at a glance, how far
the class has progressed against its learning outcomes.

Frontend-led with a tiny additive backend change. No schema change. The
per-class coverage data already comes from `GET /api/v2/csts/{id}/sub-slo-coverage`
(`progressApi.getSubSLOCoverage`); the endpoint is widened to also return each
sub-SLO's parent `slo_id` / `slo_code` so the frontend can roll the sub-SLO
statuses up to **full SLO** coverage (proportional). The bar reuses the existing
`CoverageMeter` visual idiom from the class-detail Today tab. One PR.

## Documents

1. [01-decision-log.md](01-decision-log.md) — architectural decisions (canonical)
2. [03-phase-1-today-focus.md](03-phase-1-today-focus.md) — the single phase: remove the strip + add the bar
3. [ONRAMP.md](ONRAMP.md) — single entry point for a fresh agent

## Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. phase docs                 (specs derived from above)
3. running code               (last; code may be stale)
```

If two docs disagree, this is the order. Code is **lowest** authority.
