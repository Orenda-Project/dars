# Decision Log — Teacher-App LP View + Polling

Decisions are frozen. To revise: get user OK, mark the old entry "Superseded by D-N on YYYY-MM-DD", add the new entry referencing the supersession. Both stay.

---

**D-1: The page lives in the teacher app, not the dashboard.** *Rationale:* This mirrors the real teacher flow — tap Generate on a lesson, land on the LP, watch it fill in. The dashboard is the admin/integrator surface; watching an LP generate is a teacher action. *Apply:* Route under `/teacher-app/...`, inside `TeacherAppShell`. *Decided:* 2026-06-19 (user, planning).

**D-2: Frontend-only — reuse the existing slot-read endpoint.** *Rationale:* `GET /api/v1/class-lesson-slots/{slot_id}` already returns `lp_status`, `lp_content`, and `lp_error_message` — everything the page needs. Adding a dedicated status endpoint buys a smaller payload but costs a backend change + new contract for no functional gain. *Apply:* Poll `slots.getLessonSlotDetail(slot_id)` from `dars-api.ts`; no new server code, no migration. *Decided:* 2026-06-19 (user, planning).

**D-3: Poll every 5 seconds.** *Rationale:* User-specified cadence. The existing inline `generateLPAndPoll` loop uses 3s/max-40 (~2 min); this page is a durable, dedicated view so a slightly slower 5s tick with a higher ceiling is appropriate. *Apply:* `POLL_MS = 5000`. Stop when `lp_status` becomes `READY` or `ERROR`. *Decided:* 2026-06-19 (user, planning).

**D-4: On `ERROR`, stop polling and show a Retry button.** *Rationale:* `ERROR` is terminal from LP Assistant's side; continuing to poll spins forever. Retry re-fires `POST .../generate-lp` (the existing `slots.generateLPForSlot`), which the backend treats as a fresh generation, and the page resumes polling. *Apply:* On `lp_status === "ERROR"`, render `lp_error_message` + a Retry button wired to `generateLPForSlot(slot_id)` → resume poll. *Decided:* 2026-06-19 (user, planning).

**D-5: The page owns the status UI; do NOT reuse `LPViewer` for rendering.** *Rationale:* The existing `components/molecules/lp-viewer.tsx` renders a hardcoded `STUB_LP_HTML` and ignores `lp_status` entirely — it cannot represent pending/error/ready transitions. *Apply:* The new page renders the four `lp_status` states itself and, when `READY`, renders `lp_content` (HTML) directly. May reuse smaller pieces (`LpContextHeader`, `CoveredSLOs`) but not `LPViewer` as the body. *Decided:* 2026-06-19 (planning; from code exploration).

**D-6: A safety poll ceiling stops the loop after a bounded time.** *Rationale:* A callback-only backend means a dropped callback leaves the slot `IN_FLIGHT` forever (the exact failure that motivated this feature). The page must not poll indefinitely and pin a tab. *Apply:* Cap at `MAX_POLLS` (~10 min at 5s = 120 polls); on hitting the cap while still `PENDING`/`IN_FLIGHT`, stop and show a "still generating — taking longer than expected" state with a manual "Keep checking" button (re-arms the loop) and a link back. Does NOT mark anything failed; the slot is genuinely still pending server-side. *Decided:* 2026-06-19 (planning).

**D-7: Auto-start generation only when the slot has never been generated.** *Rationale:* The page can be reached two ways: (a) freshly, via the Generate button (slot is `not_generated`), or (b) by navigating to an in-flight/ready LP. It must not re-fire generation on a slot that is already `IN_FLIGHT`/`READY`. *Apply:* On mount, read the slot once. If `lp_status === "not_generated"`, fire `generateLPForSlot` then poll. Otherwise (PENDING/IN_FLIGHT) start polling immediately; (READY) render; (ERROR) show retry. *Decided:* 2026-06-19 (planning).

**D-8: The existing class-detail Generate button navigates to this page.** *Rationale:* The feature's whole point is "open the LP right then and there." The current `generateLPAndPoll` opens a slide-over instead. *Apply:* The teacher-app Generate-LP trigger (currently `classes/[cst_id]/page.tsx`) routes to the new page for the slot instead of (or in addition to) the slide-over. Exact integration — replace vs. add-alongside — decided during implementation; default is to navigate. *Decided:* 2026-06-19 (planning).
