-- F1.1 (feat/lp-slo-injection-and-linkage)
-- Adds `requested_sub_slo_ids` to `generated_lps`.
--
-- Records the sub-SLOs the LP was asked to cover at dispatch time. Set on
-- the initial PENDING insert from the slot's topic_sub_slos. Distinct from
-- `covered_sub_slo_ids` (the post-generation F3.8 evidence-based output).
--
-- D-2, D-7 (decision log: docs/features/lp-slo-injection-and-linkage/01-decision-log.md):
--   * separate "intent" column from existing "evidence" column
--   * no backfill — legacy rows stay NULL (honest record: we did not
--     communicate any intent to LP Assistant for those dispatches)

ALTER TABLE generated_lps
    ADD COLUMN requested_sub_slo_ids UUID[] NULL;
