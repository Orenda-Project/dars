# Decision Log — Today Screen Focus

Every architectural decision, indexed. Frozen once recorded; supersede, never
overwrite.

---

**D-1: The Today screen's first view shows *only today's activity* per class — remove the Last lesson / Next lesson strip.**
*Rationale:* The teacher's first screen should answer "what do I teach right now," not surround it with yesterday/tomorrow context. The `PrevNextStrip` (last taught + next-up with projected date) is noise on the landing screen; the per-class detail page and the calendar/timeline already carry that context for anyone who wants it.
*Apply:* Delete the `PrevNextStrip` render from `CSTBlock` in `today-template.tsx`; the `previous_taught` / `next_up` fields on `TodayEntry` stay in the API (used elsewhere) but go unused on this screen.
*Decided:* 2026-06-15 (this feature).

**D-2: Each class box gets a *full SLO* coverage bar at the bottom of the box.**
*Rationale:* The teacher wants a glanceable sense of how far the class has progressed against its learning outcomes, in the same box as the class. Placed at the bottom (where the removed strip sat) so the body still leads with today's lesson card. SLO-level, not sub-SLO-level, per the user's explicit correction — outcomes are the unit a teacher reasons about.
*Apply:* New per-CST coverage bar in `CSTBlock`, reusing the `CoverageMeter` visual idiom (terra fill on parchment-deep track) already in `class-today-tab.tsx`.
*Decided:* 2026-06-15. *Note:* the bar started as "sub-SLO coverage"; the user corrected it to full SLO coverage mid-plan — see D-3/D-4.

**D-3: "Full SLO coverage" = proportional rollup — the bar is the mean of each SLO's taught-sub-SLO fraction.**
*Rationale:* Per-class coverage is only tracked at sub-SLO level (`cst_sub_slo_coverage`). To show an SLO-level bar the sub-SLO statuses must roll up to the parent SLO. The user chose the *proportional* rollup: each SLO contributes `taught_sub_slos / total_sub_slos`, and the bar value is the average of those fractions across all in-scope SLOs. Partial progress on an SLO still moves the bar, which reads as honest progress rather than a step function. Only `taught` counts toward the numerator; `unknown` (pre-onboarding) and `not_taught` do not.
*Apply:* Group the per-CST sub-SLO coverage entries by parent SLO, compute per-SLO fraction, average. Display as a percentage with an "N SLOs" denominator label.
*Decided:* 2026-06-15 (user-chosen over all-taught and any-taught rollups).

**D-4: The per-CST coverage endpoint returns the parent `slo_id` (and `slo_code`) on each sub-SLO entry; the rollup happens in the frontend.**
*Rationale:* D-3's proportional rollup needs to know which SLO each sub-SLO belongs to — the current `GET /api/v2/csts/{id}/sub-slo-coverage` returns a flat sub-SLO list with no parent. Adding `slo_id` + `slo_code` to each entry is additive (the SELECT joins `sub_slos.slo_id` → `slos`, both already exist; no schema migration). Keeping the rollup math in the FE avoids a second endpoint and keeps the existing sub-SLO consumers (class-detail Today tab, coverage report) working unchanged — they ignore the new fields.
*Rationale (against a new SLO-rollup endpoint):* A dedicated `/slo-coverage` endpoint would duplicate the universe-building query for one extra grouping. Cheaper to enrich the one we have.
*Apply:* Add `slo_id` + `slo_code` to the SELECT and to `SubSLOCoverageEntry` (backend schema + FE type). The Today page fetches per-CST coverage (N parallel calls, one per class) and rolls up per D-3.
*Decided:* 2026-06-15.

**D-5: The Today page fetches coverage per-CST in parallel; the `/today` response is not changed.**
*Rationale:* `/today` returns one entry per class but no coverage. Rather than widen that endpoint (and re-run the coverage universe query inside the today assembly for every class on every poll), the page fires one `getSubSLOCoverage(cst_id)` per class in parallel after `/today` resolves. The class count is small (a teacher's classes), so N parallel calls are cheap, and the bar can render progressively / degrade to hidden if a call fails without blocking today's lesson cards.
*Apply:* In `today/page.tsx`, after `todayApi.get()`, `Promise.all` a `getSubSLOCoverage` per `cst_id`; pass a `coverageByCst` map into `TodayTemplate`. A class whose coverage call fails or returns zero SLOs simply renders no bar.
*Decided:* 2026-06-15.
