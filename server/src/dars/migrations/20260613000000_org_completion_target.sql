-- Feature: dynamic-chapter-planner — Phase 2 (F-2.2, D-14).
-- Adds the org-wide completion-target knob that drives buffer-budgeted planning.
--
--   organizations:
--     * default_completion_target — fraction of a chapter's teaching days planned
--                                   into MANDATORY content; the remainder becomes
--                                   interleaved flex (revision) buffer slots
--                                   (D-3/D-4). 0.80 = plan to 80%, keep 20% buffer.
--
-- D-14 (frozen 2026-06-12): ORG DEFAULT ONLY — no per-CST override (deferrable).
-- One place for org-wide policy; a per-CST override can be added later if a real
-- need appears. Supersedes the 02-data-model.md "org default + optional per-CST
-- override" placeholder.
--
-- Single ADD COLUMN with a literal NUMERIC default — no PG-only syntax, so it
-- applies on both Postgres (Railway deploy) and sqlite (planner/budget tests run
-- against an in-memory DB; D-11). NUMERIC maps to sqlite's NUMERIC affinity and
-- round-trips a float.
--
-- Append-only. See docs/features/dynamic-chapter-planner/02-data-model.md.

ALTER TABLE organizations
  ADD COLUMN default_completion_target NUMERIC NOT NULL DEFAULT 0.80;
