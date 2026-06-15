# Phase 1 — Today screen focus

One phase, one PR. Frontend-led with a tiny additive backend enrichment.
Independently shippable to staging.

References: D-1 … D-5 in [01-decision-log.md](01-decision-log.md).

---

## F-1.1 — Remove the Last/Next strip from the Today screen (D-1)

**Spec.** In `webapp/components/templates/today-template.tsx`, `CSTBlock` renders
a `<PrevNextStrip>` after today's lesson card. Remove that render. Delete the now-unused
`PrevNextStrip` and `PrevNextCell` helpers (they are only used here). Leave the
`previous_taught` / `next_up` fields on `TodayEntry` untouched — other code paths
read them.

**Acceptance.**
- The Today screen shows, per class: the header (Grade · Subject · Day), the
  "You're on Chapter N" block, today's lesson/assessment card, and the new
  coverage bar (F-1.4). No Last lesson / Next lesson cells.
- `npm run build` (or typecheck) is clean — no unused-import / dead-code errors.

## F-1.2 — Return parent SLO on each sub-SLO coverage entry (D-4)

**Spec.** Enrich `GET /api/v2/csts/{cst_id}/sub-slo-coverage`
(`server/src/dars/v2_api/router_class_actions.py`, `get_sub_slo_coverage`):

- Add `sl.id AS slo_id, sl.code AS slo_code` to the universe SELECT by joining
  `sub_slos ss → slos sl ON sl.id = ss.slo_id`. Group/order accordingly.
- Add `slo_id: UUID` and `slo_code: str` to `SubSLOCoverageEntry` in
  `schemas_class_actions.py` (or wherever it is defined) and populate them.
- Structured logging: the endpoint already logs entry/exit — keep the existing
  log lines; no behavior change beyond the two extra columns.

**Acceptance.**
- Response items each carry `slo_id` + `slo_code` alongside the existing
  `sub_slo_id` / `sub_slo_code` / `status`.
- Existing consumers (class-detail Today tab tally, org coverage report) are
  unaffected — they ignore the new fields.
- No schema migration (both `sub_slos.slo_id` and `slos` already exist).

## F-1.3 — Mirror the new fields in the FE type + compute the rollup (D-3)

**Spec.** In `webapp/lib/dars-api.ts`, add `slo_id: UUID; slo_code: string;` to
`SubSLOCoverageEntry`. Add a small pure helper (FE) that takes a
`SubSLOCoverageResponse` and returns the proportional SLO-coverage value per D-3:

```
group entries by slo_id
per SLO: fraction = (# entries with status === "taught") / (# entries in that SLO)
bar value (0..1) = mean of per-SLO fractions   // simple average across SLOs
sloCount = number of distinct SLOs
```

Return `null` when there are zero in-scope SLOs (no bar).

**Acceptance.**
- Helper is unit-reasonable: an SLO with 2/3 taught contributes 0.667; the bar
  is the mean across SLOs, not the global taught/total sub-SLO ratio.
- `unknown` and `not_taught` both count as "not taught" in the numerator.

## F-1.4 — Render the full-SLO coverage bar at the bottom of each class box (D-2, D-5)

**Spec.**
- `today/page.tsx`: after `todayApi.get()`, fetch coverage for every class in
  parallel — `Promise.all(items.map(e => getSubSLOCoverage(e.cst_id)))` — and
  build a `Map<cst_id, rollup>` (rollup = `{ percent, sloCount }` from F-1.3,
  or absent on failure/empty). A failed coverage call for one class must not
  break the page or the other classes' bars; catch per-call and omit. Pass the
  map into `TodayTemplate`.
- `today-template.tsx`: `TodayTemplate` + `CSTBlock` accept the coverage map.
  Render a coverage bar at the bottom of `CSTBlock` (where `PrevNextStrip` was),
  separated by a hairline rule. Reuse the `CoverageMeter` visual idiom from
  `class-today-tab.tsx`: label row ("SLO coverage" + "{pct}% · {n} SLOs") above a
  2px terra fill on a `bg-dars-parchment-deep` rounded track. Label says **SLO
  coverage** (not sub-SLO). Hide the bar entirely when the class has no rollup.

**Acceptance.**
- Each class box shows an "SLO coverage" bar at the bottom with the proportional
  percentage and SLO count.
- A class with no SLOs in scope (or a failed coverage fetch) shows no bar and no
  error.
- The bar fill width matches the proportional percentage from F-1.3.
- Visual language matches the existing `CoverageMeter` (terra on parchment-deep).

## Dependencies

- F-1.3 depends on F-1.2 (needs `slo_id` in the response).
- F-1.4 depends on F-1.3 (uses the rollup helper) and F-1.1 (takes the strip's slot).

## Notes from execution

_(append during/after implementation)_
