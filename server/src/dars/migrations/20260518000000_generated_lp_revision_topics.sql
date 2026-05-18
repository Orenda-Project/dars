-- F3.10: revision LP context.
--
-- A revision LP covers multiple topics (everything taught in the chapter
-- before the revision slot). We already capture that as a SHA-256
-- `revision_topic_set_hash` on `generated_lps`, but the actual topic_id
-- list needs to survive too so the post-process tagging service (F3.8)
-- knows which sub-SLOs to pass as candidates.
--
-- Why a side table instead of a JSONB column: lets us join cleanly with
-- `topic_sub_slos` in the tagging query, and gives us a referential
-- integrity guarantee (ON DELETE CASCADE if a topic is removed).
--
-- Migration: idempotent. Safe to re-run.

CREATE TABLE IF NOT EXISTS generated_lp_revision_topics (
    generated_lp_id UUID NOT NULL REFERENCES generated_lps(id) ON DELETE CASCADE,
    topic_id UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    position INT NOT NULL,
    PRIMARY KEY (generated_lp_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_grt_topic ON generated_lp_revision_topics(topic_id);
