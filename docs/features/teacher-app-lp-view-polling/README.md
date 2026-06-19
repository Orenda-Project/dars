# Teacher-App LP View + Polling

A dedicated teacher-app page that opens a single lesson plan and follows its generation to completion. When a teacher hits **Generate LP** on a lesson slot, they land on this page. If the LP is already `READY`, it shows the content immediately. If it is still being generated (`PENDING` / `IN_FLIGHT`), the page shows a "generating…" state and **polls `GET /api/v1/class-lesson-slots/{slot_id}` every 5 seconds** until the status resolves. On `ERROR` it stops polling, shows the failure message, and offers a **Retry** button that re-fires `generate-lp`.

This is a **frontend-only** feature in the Next.js webapp under `/teacher-app`. It reuses the existing slot-read and generate-lp endpoints and the existing `dars-api.ts` client — no backend change, no migration. It exists because the current flow leaves a generated LP stuck behind an inline slide-over with a short polling ceiling; a teacher who generates an LP has no durable, linkable place to watch it land. (Context: a staging generation was observed stuck `IN_FLIGHT` because the flow is callback-only with no recovery surface — this page gives the teacher a live view of generation progress.)

## Documents

1. [`01-decision-log.md`](01-decision-log.md) — architectural decisions (D-1…). **Read first — load-bearing.**
2. [`03-phase-1-lp-view-page.md`](03-phase-1-lp-view-page.md) — the single phase: the page, the poll loop, status rendering, retry.
3. [`ONRAMP.md`](ONRAMP.md) — single entry point for any agent picking this up cold (written after plan approval).

## Document precedence

If two docs disagree, resolve in this order (code is lowest authority):

```
1. 01-decision-log.md   (D-N references are canonical)
2. phase docs           (specs derived from above)
3. running code         (last; code may be stale)
```

No `00-glossary.md` or `02-data-model.md` — this feature introduces no new domain concepts and no schema change. All terms (`lp_status`, `lp_content`, `lp_error_message`, slot) are defined by the existing slot-read endpoint, quoted in the phase doc.
