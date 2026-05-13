-- Data: map any legacy book curriculum values to new codes (no-op on clean DB)
UPDATE books SET curriculum = 'NCP' WHERE curriculum = 'ICT';
UPDATE books SET curriculum = 'SNC' WHERE curriculum IN ('Punjab', 'Sindh');

-- SLOs
CREATE TABLE IF NOT EXISTS slos (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  curriculum  TEXT NOT NULL REFERENCES curriculums(code),
  grade       INT NOT NULL,
  subject     TEXT NOT NULL REFERENCES subjects(code),
  code        TEXT NOT NULL,        -- e.g. "R1.1", "M3.2"
  description TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (curriculum, code)
);

-- Topic → SLO mapping
CREATE TABLE IF NOT EXISTS topic_slos (
  topic_id  UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
  slo_id    UUID NOT NULL REFERENCES slos(id) ON DELETE CASCADE,
  PRIMARY KEY (topic_id, slo_id)
);

CREATE INDEX IF NOT EXISTS idx_slos_curriculum_grade_subject ON slos(curriculum, grade, subject);
CREATE INDEX IF NOT EXISTS idx_topic_slos_topic ON topic_slos(topic_id);
