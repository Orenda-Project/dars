# Glossary — Breakdown Slot Editing

Inherits all terms from the v2 rebuild's [00-glossary.md](../../plans/2026-05-15-dars-v2-rebuild/00-glossary.md). This file adds only terms specific to this feature.

**Side panel** — The right-hand pane on `/dashboard/breakdowns/[breakdown_id]`. Shows the currently selected `BreakdownSlot`'s fields. Today it is read-only except for `anchor_date`. After this feature: editable for `lp_type`, `slot_type`, `topic_id` on draft breakdowns.

**Chapter topic pool** — The set of `Topic` rows whose `book_chapter_id` equals the slot's `breakdown_chapter.book_chapter_id`. A slot's `topic_id` may only be set to a topic from this pool (validation already enforced server-side in `add_slot`; we replicate it client-side as the dropdown's option list).

**Slot draft** — A pending change to a slot that has not yet been saved. The side panel will hold local form state; the API call fires on a "Save" button, not on each field's blur, so the user can change multiple fields at once and ship them in one PATCH (matches the backend's all-fields-optional `BreakdownSlotUpdate`).
