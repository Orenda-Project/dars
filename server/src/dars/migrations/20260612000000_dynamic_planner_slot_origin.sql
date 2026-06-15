-- Feature: dynamic-chapter-planner — Phase 1 (F-1.1, D-1, D-8, D-10).
-- Adds slot provenance + flex buffer columns so the live plan can be mutated
-- (insert / remove / consume-flex) while recording where each slot came from.
--
--   class_lesson_slots:
--     * origin                 — 'breakdown' (seeded), 'reteach', 'manual'
--     * reteach_for_sub_slo_id — the sub-SLO a reteach slot re-covers (NULL otherwise)
--     * flex                   — droppable buffer (revision) lesson slot
--   class_assessment_slots:
--     * origin                 — same provenance enum, for read symmetry (assessments
--                                are not dynamically inserted yet)
--
-- Plain ADD COLUMN with literal defaults + a CHECK — portable to both Postgres
-- (Railway deploy) and sqlite (mutation tests, D-11). UUID is TEXT under sqlite
-- (existing pattern); no gen_random_uuid() here, so no dialect split.
--
-- Append-only. See docs/features/dynamic-chapter-planner/02-data-model.md.

ALTER TABLE class_lesson_slots
  ADD COLUMN origin TEXT NOT NULL DEFAULT 'breakdown'
    CHECK (origin IN ('breakdown', 'reteach', 'manual'));
ALTER TABLE class_lesson_slots
  ADD COLUMN reteach_for_sub_slo_id UUID REFERENCES sub_slos(id);
ALTER TABLE class_lesson_slots
  ADD COLUMN flex BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE class_assessment_slots
  ADD COLUMN origin TEXT NOT NULL DEFAULT 'breakdown'
    CHECK (origin IN ('breakdown', 'reteach', 'manual'));
