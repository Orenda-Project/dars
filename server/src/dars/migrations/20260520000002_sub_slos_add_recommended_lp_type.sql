-- Sub-SLOs gain a `recommended_lp_type` column (mirrors the column on `slos`).
--
-- Why: per the NCP English G1 seed (D-11 of docs/features/ncp-english-g1-seed/),
-- lp_type is more accurately a property of a sub-SLO than its parent SLO. One
-- broad SLO can break into sub-SLOs that warrant different lp_types (e.g. a
-- vocabulary sub-skill vs a writing sub-skill of the same comprehension SLO).
-- The new NCP seed populates this column via a Claude-backed classifier; the
-- existing Dars sub-SLOs stay NULL and fall back to the parent SLO's value via
-- the precedence chain in `breakdown/lp_type_heuristics.py` (D-13).
--
-- Allowed values per subject are enforced by application code, not the DB
-- (same reasoning as the equivalent column on `slos`).

ALTER TABLE sub_slos
    ADD COLUMN recommended_lp_type TEXT;
