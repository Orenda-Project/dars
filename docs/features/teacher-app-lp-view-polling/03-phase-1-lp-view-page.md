# Phase 1 — LP View Page with 5s Polling

Single phase. Independently shippable. Frontend-only. Targets `staging`.

**Endpoint shapes (frozen, from code exploration — these are the contract this phase builds on):**

`GET /api/v1/class-lesson-slots/{slot_id}` → `ClassLessonSlotDetail` (in `webapp/lib/dars-api.ts`), relevant fields:
- `lp_status`: `"not_generated" | "PENDING" | "IN_FLIGHT" | "READY" | "ERROR"`
- `lp_content`: `string | null` (HTML when READY)
- `lp_error_message`: `string | null`
- plus `chapter_number`, `chapter_title`, `topic_text`, `lp_type`, `lp_covered_sub_slo_ids` for the header.

`POST /api/v1/class-lesson-slots/{slot_id}/generate-lp` → `GenerateLPResponse` (has `lp_status`).

API client (existing, `webapp/lib/dars-api.ts`):
- `slots.getLessonSlotDetail(slot_id)` — the GET above
- `slots.generateLPForSlot(slot_id)` — the POST above

---

## F-1.1 — The LP view route

**Spec:** New App Router page at `webapp/app/teacher-app/lp/[slot_id]/page.tsx` (client component). Renders inside `TeacherAppShell` via the existing teacher-app layout — the page renders **no** header/nav of its own. The page reads `slot_id` from the route param. Top of the page shows LP context (chapter number/title, topic, lp_type) — reuse `LpContextHeader` if it accepts the detail fields; otherwise inline a small header. A "← Back to class" link uses `next/link` (back to `/teacher-app/classes/[cst_id]` — `cst_id` comes from the slot detail's `cst_id`).

**Acceptance:**
- Navigating to `/teacher-app/lp/<a-real-slot-id>` renders the page within the teacher-app shell.
- The page fetches the slot detail once on mount and shows the chapter/topic header.
- A back link returns to the slot's class page.

**Dependencies:** none.

## F-1.2 — Mount behaviour & auto-start (D-7)

**Spec:** On mount, fetch the slot detail once. Branch on `lp_status`:
- `not_generated` → call `slots.generateLPForSlot(slot_id)`, then enter the poll loop.
- `PENDING` | `IN_FLIGHT` → enter the poll loop immediately (do NOT re-fire generate).
- `READY` → render content (F-1.4), no polling.
- `ERROR` → render error + Retry (F-1.5), no polling.

**Acceptance:**
- Opening the page for a `not_generated` slot fires exactly one generate call, then begins polling.
- Opening it for an already `IN_FLIGHT` slot does NOT fire a second generate call; it just starts polling.
- Opening it for a `READY` slot fires no generate and no poll.

**Dependencies:** F-1.1.

## F-1.3 — The 5-second poll loop (D-3, D-6)

**Spec:** Match the existing `generateLPAndPoll` style (plain `setTimeout`/`async` loop — the webapp has no SWR/react-query; do not add one). `POLL_MS = 5000`. Each tick calls `slots.getLessonSlotDetail(slot_id)` and updates page state. Stop conditions: `lp_status` becomes `READY` or `ERROR`, OR `MAX_POLLS` reached (`120` ≈ 10 min, D-6). The loop must be cancelled on unmount (clear the timer / guard against setting state after unmount) so navigating away kills polling. While polling, show a "Generating your lesson plan…" state with a spinner/animated indicator and a subtle "checking again in 5s" affordance.

**Acceptance:**
- While `PENDING`/`IN_FLIGHT`, the network tab shows a slot-detail GET roughly every 5s.
- The loop stops the instant status flips to `READY` or `ERROR` (no further GETs).
- Navigating away from the page stops the polling (no orphaned timers, no setState-after-unmount warnings).
- After `MAX_POLLS` while still pending, polling stops and the "taking longer than expected" state (D-6) appears with a "Keep checking" button that re-arms the loop.

**Dependencies:** F-1.2.

## F-1.4 — READY rendering (D-5)

**Spec:** When `lp_status === "READY"`, render `lp_content` (HTML string) as the LP body. The page owns this — do NOT use `LPViewer` (it renders a stub and ignores status). Optionally render covered SLOs from `lp_covered_sub_slo_ids` using the existing `CoveredSLOs` molecule if it takes ids. Style with Tailwind + `dars-*` tokens consistent with other teacher-app pages.

**Acceptance:**
- A slot whose `lp_status` is `READY` shows the actual `lp_content`, not a stub.
- The transition pending → ready happens live on the page without a manual refresh (the poll tick that observes `READY` swaps the view).

**Dependencies:** F-1.3.

## F-1.5 — ERROR rendering + Retry (D-4)

**Spec:** When `lp_status === "ERROR"`, stop polling and show `lp_error_message` (fallback to a generic "Generation failed" if null) in a clear error block, plus a **Retry** button. Retry calls `slots.generateLPForSlot(slot_id)`, then re-enters the poll loop (back to the generating state). Disable the button while the retry request is in flight to prevent double-fire.

**Acceptance:**
- A slot with `lp_status === "ERROR"` shows the error message and a Retry button; polling has stopped (no slot-detail GETs).
- Clicking Retry fires one generate call, the page returns to the generating/polling state, and resumes polling.
- The Retry button cannot be double-clicked into two concurrent generate calls.

**Dependencies:** F-1.3.

## F-1.6 — Wire the Generate button to navigate here (D-8)

**Spec:** The teacher-app Generate-LP trigger (today `generateLPAndPoll` + slide-over in `webapp/app/teacher-app/classes/[cst_id]/page.tsx`, with the button surfaced via `ClassTodayTab` / lessons list) navigates to `/teacher-app/lp/<slot_id>` instead of opening the slide-over for the generate-then-watch flow. Use `router.push`. Default: replace the inline generate-and-slide-over path with navigation. If removing the slide-over entirely is risky (it may also be used to *view* already-ready LPs), keep "View LP" on ready slots opening as it does today and only redirect the **Generate** (fresh) action to the new page — decide during implementation and record as a `## Notes from execution` entry.

**Acceptance:**
- Clicking **Generate LP** on a not-yet-generated slot in the teacher app navigates to `/teacher-app/lp/<slot_id>` and the page auto-starts generation + polling.
- No regression to viewing already-ready LPs from the class page.

**Dependencies:** F-1.1…F-1.5.

---

## Verification (whole phase)

On staging, against the NCP test org (G1 English has a real book/LP path):
1. From a class's today/lessons view, hit **Generate LP** on a `not_generated` slot → lands on `/teacher-app/lp/<slot_id>`, shows generating, polls every 5s.
2. When LP Assistant calls back, the page flips to the rendered LP without manual refresh.
3. Force/observe an `ERROR` slot → error message + Retry; Retry restarts the flow.
4. Open the page directly for an already-`READY` slot → renders immediately, no poll. For an `IN_FLIGHT` slot → polls without re-firing generate.
5. Navigate away mid-poll → polling stops (no console warnings).

---

## Notes from execution

- **F-1.6 — slide-over vs. navigate (resolved):** Took the default (navigate). Changed `onTodayGenerateLP` in `webapp/app/teacher-app/classes/[cst_id]/page.tsx` to `router.push('/teacher-app/lp/<slot_id>')` instead of running the inline `generateLPAndPoll` + opening the slide-over. **Viewing** an already-ready LP is untouched — `onViewLP` still opens the existing slide-over — so only the fresh **Generate** action redirects. This made the inline `generateLPAndPoll` callback and the `generatingSlotId` state dead code (the today tab was their only caller); both were removed, and the today card's `generatingLP` prop is now constant `false` (the in-flight state lives on the new page). The FA-exam analogue (`generateExamAndPoll` / `generatingExamSlotId`) is unrelated and left intact.
- **Status pill:** `LPStatusPill` in `class-today-tab.tsx` is module-local (not exported); the new page inlines its own small status affordances rather than refactoring an export, to keep the diff tight.
- **LP body rendering:** Confirmed both `lp-viewer.tsx` and `lp-content-viewer.tsx` render `STUB_LP_HTML` and ignore status (D-5). The new page renders real `lp_content` via `dangerouslySetInnerHTML`, mirroring `exam-viewer.tsx:109` (`exam_paper_html`).
- **Verified:** `tsc --noEmit` clean, `eslint` clean on both changed files, `next build` green with the new route `ƒ /teacher-app/lp/[slot_id]` registered.
