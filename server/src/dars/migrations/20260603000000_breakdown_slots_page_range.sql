-- Phase 2 (chapter-breakdown-and-plan): explicit page range per slot.
-- D-4: a Chapter Plan slot records the book pages it covers
-- (e.g. "LP1: pages 1-10"). Both nullable -- not every slot maps to
-- pages (e.g. revision). Validated advisory in the service/UI layer.
-- See docs/features/chapter-breakdown-and-plan/02-data-model.md (Delta 2).

ALTER TABLE breakdown_slots
    ADD COLUMN IF NOT EXISTS page_start INT,
    ADD COLUMN IF NOT EXISTS page_end   INT;
