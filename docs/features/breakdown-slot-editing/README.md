# Breakdown Slot Editing

Let org admins edit individual slots inside a draft org-scope breakdown from the dashboard. The v2 rebuild's F5.10–F5.12 shipped the breakdown editor with chapter day-budget editing and slot anchor placement, but the per-slot side panel was read-only beyond the anchor field. This feature wires the side panel up to the slot CRUD endpoints that already exist.

End state: from the breakdown detail page, an admin selecting a slot in a draft breakdown can change its `lp_type`, change its `topic_id` (within the chapter's topics), change its `slot_type` (lesson ↔ revision ↔ formative_assessment ↔ summative_assessment), and add/remove slots within a chapter. Publish still flips draft → published and locks everything. No drag-reorder, no chapter add/remove — auto-build still produces the chapter list.

## Index

1. [00-glossary.md](00-glossary.md) — extends the v2 glossary with three terms specific to this feature.
2. [01-decision-log.md](01-decision-log.md) — design decisions for slot editing.
3. [03-phase-1-slot-editing.md](03-phase-1-slot-editing.md) — single phase: backend confirm + webapp side-panel editor + add/delete slot.
4. [ONRAMP.md](ONRAMP.md) — fresh-agent entry point. Written after plan approval.

## Document precedence

If two documents disagree, this is the order of authority:

```
1. 01-decision-log.md         (D-N references are canonical)
2. v2 rebuild's 02-data-model.md (schema is ground truth — no changes here)
3. 00-glossary.md             (terminology)
4. phase docs                  (specs derived from above)
5. running code                (last; code may be stale)
```

The v2 rebuild's plan still governs schema and breakdown semantics. This feature folder only adds decisions about the editing UX.

## Sizing

**Size: S.** One phase, one PR. Backend already has every endpoint this needs (`PATCH/POST/DELETE /breakdowns/{id}/slots[/{slot_id}]`). All new code is on the webapp side: 3 new client wrappers and a rewrite of the side panel + a chapter-level "add slot" button. The acceptance criteria below name 5 concrete user-facing changes.
