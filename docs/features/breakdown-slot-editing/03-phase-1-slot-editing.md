# Phase 1 — Slot editing

**Goal:** wire the breakdown editor's side panel and per-chapter header to the existing slot CRUD endpoints so an org admin can change a slot's `slot_type`, `lp_type`, `topic_id` and add/delete slots in a draft org-scope breakdown.

**Branching:** `feat/breakdown-slot-editing` off `staging`.

**One PR. One bead: `feat-breakdown-slot-editing`.**

---

## F1.1 — Webapp: extend `dars-api.ts` with slot mutation wrappers

**Motivation:** the existing client (`webapp/lib/dars-api.ts`) only exposes `patchSlotAnchor`. To unblock the UI we need wrappers for the three slot endpoints already in the v2 router.

**Spec:**

Add three functions on `breakdowns` in `webapp/lib/dars-api.ts`:

```ts
addSlot(breakdownId: UUID, body: {
  breakdown_chapter_id: UUID;
  position: number;
  chapter_position: number;
  slot_type: "lesson" | "formative_assessment" | "summative_assessment" | "revision";
  lp_type: string | null;
  topic_id: UUID | null;
  anchor_date: ISODate | null;
  extra_topic_ids?: UUID[];
}): Promise<BreakdownSlot>;

patchSlot(breakdownId: UUID, slotId: UUID, body: {
  slot_type?: "lesson" | "formative_assessment" | "summative_assessment" | "revision";
  lp_type?: string | null;
  topic_id?: UUID | null;
}): Promise<BreakdownSlot>;

deleteSlot(breakdownId: UUID, slotId: UUID): Promise<void>;
```

`addSlot` POSTs to `/api/v2/breakdowns/{breakdownId}/slots`. `patchSlot` PATCHes `/api/v2/breakdowns/{breakdownId}/slots/{slotId}`. `deleteSlot` DELETEs the same. (Confirmed against `patchSlotAnchor`'s URL pattern in `dars-api.ts`.)

`patchSlot` deliberately omits `position`, `chapter_position`, and `anchor_date` (anchor stays on its own wrapper).

**Acceptance:**
- Each function returns the parsed `BreakdownSlot` (where applicable) or throws `DarsApiError` on non-2xx.
- Types compile.
- A quick `tsc --noEmit` is clean.

**Dependencies:** none.

---

## F1.2 — Webapp: side-panel slot editor

**Motivation:** the right-hand side panel on `/dashboard/breakdowns/[breakdown_id]/page.tsx` currently shows `slot_type`, `lp_type`, and `topic_id` as plain `<dd>` text. We replace those with editable controls when the breakdown is draft + org-scope.

**Spec:**

Rewrite the side panel's body (`if (selectedSlot)` branch in the existing page). The component holds local form state `{ slot_type, lp_type, topic_id }`, initialized from `selectedSlot` whenever `selectedSlot.id` changes. Visible controls:

1. **Slot type / LP type** — single `<select>` listing all legal combos for the breakdown's subject. Build the option list from `LP_TYPES_BY_SUBJECT[subject_code]` (port the constant from `server/src/dars/v2_api/lp_types.py` into `webapp/lib/slot-types.ts` — this is a small static table and duplicating it is cheaper than adding an API call). Option labels:
   - `Lesson — reading`, `Lesson — comprehension (Q&A)`, …
   - `Formative assessment` (slot_type=`formative_assessment`, lp_type=`null`)
   - `Summative assessment` (slot_type=`summative_assessment`, lp_type=`null`)
   - `Revision` (slot_type=`revision`, lp_type=`revision`)
   - Each option's `value` encodes `<slot_type>::<lp_type|none>`. The component parses it back on save.

2. **Topic** — `<select>` populated by `curriculum.getTopics(book_chapter_id)` where `book_chapter_id = bookChaptersById.get(selectedSlot.breakdown_chapter_id)?.book_chapter_id` (load lazily on first select; cache in a state map keyed by `book_chapter_id`).
   - Options: every topic in the slot's chapter, label `Topic N — <title>` (truncated).
   - Disabled when `slot_type` is `formative_assessment` or `summative_assessment` (those use `extra_topic_ids`, out of scope for this PR — they fall back to whatever the auto-build set; assessment topic editing is a follow-up).

3. **Anchor date** — keep the existing input as-is. Anchor still has its own endpoint and existing wrapper.

4. **Save / Cancel** — small button row at the bottom of the panel. "Save" is disabled if no field changed vs the loaded slot. "Save" calls `patchSlot(breakdownId, slotId, dirtyFields)`, then `load()`. "Cancel" reverts form state to the slot's current values. The existing `busy` flag drives the disabled state.

5. **Delete slot** — a small destructive-styled link at the bottom of the panel (only on `editable && data.scope === 'org'`). On click: `confirm()` then `deleteSlot(breakdownId, slotId)`, then `setSelectedSlot(null)` and `load()`.

The existing read-only fallback (when `!editable` OR `data.scope !== 'org'`) keeps the current dl/dd display verbatim.

**Acceptance:**
- Selecting a slot in a draft org-scope breakdown shows the form.
- Changing the slot-type/lp-type dropdown to a valid combo and saving sends one PATCH with both fields; server returns 200; UI reloads with the new state visible in the list.
- Changing topic to another topic in the same chapter saves; the list shows the new topic_id under the slot.
- Trying to set `lp_type` to something not in `LP_TYPES_BY_SUBJECT[subject_code]` is impossible — the option doesn't exist.
- Hitting Cancel reverts the form without an API call.
- Delete confirms, removes the slot, list re-renders without it, side panel clears.
- Published breakdowns: form does not render — read-only fallback shows instead.
- Class-scope breakdowns: form does not render — read-only fallback shows.

**Dependencies:** F1.1.

---

## F1.3 — Webapp: per-chapter "+ Add slot" button

**Motivation:** Add slot needs to know which chapter. Place the action on the chapter header so the chapter context is implicit.

**Spec:**

In the chapter header (`<header>` inside each `<li>` in the chapters list, draft only): add a small `+ Add slot` button next to the Days input. On click:

1. Compute new positions:
   - `position = max(s.position for all slots in breakdown) + 1` (or `1` if no slots).
   - `chapter_position = max(s.chapter_position for slots in this chapter) + 1` (or `1`).
2. Call `addSlot(breakdownId, { breakdown_chapter_id: chapter.id, position, chapter_position, slot_type: "lesson", lp_type: <first valid lp_type for subject>, topic_id: null, anchor_date: null })`.
3. `await load()`; auto-select the newly added slot (find it by `position` in `data.slots`).

**Acceptance:**
- Clicking "+ Add slot" on a chapter appends a new lesson slot at the end of the chapter and end of the breakdown.
- The new slot is auto-selected in the side panel, where the admin can immediately set its topic.
- Button is hidden on published breakdowns and on non-org-scope breakdowns.
- If the subject has no valid `lp_type` (Science, GK — only "revision"), the new slot defaults to a revision slot (`slot_type=revision, lp_type=revision`) instead of a lesson.

**Dependencies:** F1.1.

---

## F1.4 — Manual E2E on staging

**Motivation:** the v2 rebuild's discipline is "don't claim done until Railway shows SUCCESS on the new commit + manual smoke."

**Spec:**
1. Merge PR; watch both Railway services (server is unchanged, but webapp deploy must go green).
2. Log in to `https://dars-fe-stage.up.railway.app/dashboard/login` with the demo admin (see seed; same creds the F5 close-out used).
3. Navigate to Breakdowns → open an org draft breakdown.
4. Run through each acceptance criterion in F1.2 and F1.3 once. Note any issue against the PR.

**Acceptance:** all five F1.2 + F1.3 acceptance items pass on staging.

**Dependencies:** F1.1, F1.2, F1.3 merged.

---

## Out of scope (explicit follow-ups, do not implement here)

- **Mid-insertion of slots.** D-6. Append only.
- **Drag-reorder.** No `position` rewrites here.
- **Add/remove/reorder chapters.** Auto-build still owns chapters.
- **Edit `extra_topic_ids` for assessment slots.** A follow-up; FA/SA topic coverage is whatever auto-build picked.
- **"Edit published breakdown" button.** D-8. Today, to edit a published breakdown the admin still has to roundtrip via the API or the legacy "PATCH on published forks a draft" behavior — UI-level fork-a-draft button is a separate ticket.
- **Class-scope editing.** D-7.
