-- F1.3 prep: SLOs gain a `recommended_lp_type` column.
--
-- Why: the breakdown engine needs to know which LP Assistant `lp_type` an SLO
-- should be taught with. Encoding it at SLO authoring time (instead of
-- inferring later) makes the breakdown deterministic and lets us catch
-- SLO/lp_type mismatches at seed time. See REBUILD.md note on lp_type enum
-- (08-reference-lp-assistant-api.md).
--
-- Allowed values per subject are enforced by application code, not the DB
-- (the enum is per-subject; a CHECK constraint would either be subject-wise
-- complex or too permissive). Application code that inserts SLOs MUST
-- validate against LP Assistant's VALID_LP_TYPES table.

ALTER TABLE slos
    ADD COLUMN recommended_lp_type TEXT;
