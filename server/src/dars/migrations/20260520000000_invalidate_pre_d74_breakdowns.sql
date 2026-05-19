-- D-74: slot-per-day model change. Pre-D-74 breakdowns have far fewer
-- slots than total_teaching_days (e.g. 27 days → 7 slots). The seed
-- (seed_demo_breakdown in seeds/breakdown_demo.py) is idempotent and
-- will skip rebuilding if a published breakdown already exists for the
-- demo (DARS, G1, Eng) / org / CST. So to force a rebuild on the next
-- deploy, we soft-delete the existing demo breakdowns + drop the
-- realized class slots.
--
-- Targeted to the demo org/CST only. Other orgs (if any exist on
-- staging) are untouched. Idempotent: re-running this migration after
-- the new auto-build has run is a no-op because the new breakdowns
-- have count(slots) == total_teaching_days and we only delete the old
-- ones (by id range / scope_ref_id match).
--
-- Demo identifiers (deterministic seed UUIDs — see dars/seeds/lookups.py
-- seed_uuid()):
--   curriculum DARS  = '722770bf-42b2-51be-b070-d810064a58ae'
--   grade G1         = 'a1b98ed9-bdbb-53d7-b03d-1ac7e0b84081'
--   subject Eng      = 'a35a677c-4b65-5a99-b54e-3ec3cc10262d'
--   demo org         = '3cf70981-62fb-5c80-9233-5a702e11fdf1'
--   demo CST         = '818597c7-749d-59e5-b3d9-60b33131fc7c'

-- 1. Soft-delete the demo's class-scope breakdown(s). This stops the
--    next seed run from short-circuiting on "class_existing".
UPDATE breakdowns
SET status = 'deleted', updated_at = now()
WHERE status IN ('draft', 'published')
  AND scope = 'class'
  AND scope_ref_id = '818597c7-749d-59e5-b3d9-60b33131fc7c'
  AND curriculum_id = '722770bf-42b2-51be-b070-d810064a58ae'
  AND grade_id = 'a1b98ed9-bdbb-53d7-b03d-1ac7e0b84081'
  AND subject_id = 'a35a677c-4b65-5a99-b54e-3ec3cc10262d';

-- 2. Soft-delete the demo's org-scope breakdown.
UPDATE breakdowns
SET status = 'deleted', updated_at = now()
WHERE status IN ('draft', 'published')
  AND scope = 'org'
  AND scope_ref_id = '3cf70981-62fb-5c80-9233-5a702e11fdf1'
  AND curriculum_id = '722770bf-42b2-51be-b070-d810064a58ae'
  AND grade_id = 'a1b98ed9-bdbb-53d7-b03d-1ac7e0b84081'
  AND subject_id = 'a35a677c-4b65-5a99-b54e-3ec3cc10262d';

-- 3. Soft-delete the global breakdown for (DARS, G1, Eng). The seed
--    only ever publishes one; no other org can have created one.
UPDATE breakdowns
SET status = 'deleted', updated_at = now()
WHERE status IN ('draft', 'published')
  AND scope = 'global'
  AND curriculum_id = '722770bf-42b2-51be-b070-d810064a58ae'
  AND grade_id = 'a1b98ed9-bdbb-53d7-b03d-1ac7e0b84081'
  AND subject_id = 'a35a677c-4b65-5a99-b54e-3ec3cc10262d';

-- 4. Drop the realized class slots so the new realize() pass starts
--    clean. (class_lesson_slots / class_assessment_slots derive from
--    the class-scope breakdown; once it's gone, these orphan.)
DELETE FROM class_lesson_slots
WHERE cst_id = '818597c7-749d-59e5-b3d9-60b33131fc7c';

DELETE FROM class_assessment_slots
WHERE cst_id = '818597c7-749d-59e5-b3d9-60b33131fc7c';
