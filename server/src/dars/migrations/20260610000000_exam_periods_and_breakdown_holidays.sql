-- Feature: exam-periods-and-formative-assessments — Phase 1 (F-1.1, D-1, D-14).
-- Two new tables hanging off a global Syllabus Breakdown:
--   * exam_periods       — reserved non-teaching ranges for exams (D-1)
--   * breakdown_holidays — general non-teaching ranges (Eid, public holidays) that
--                          inherit down to every class plan on the triple (D-14)
-- Both are date ranges (admins think in spans); a single-day holiday is a 1-day
-- range (start_date == end_date). Their expanded dates union into the
-- teaching-day exclusion set in the admin display AND the teacher projection
-- (D-2/D-3/D-15). end_date >= start_date is enforced in the service layer
-- (advisory per D-4), NOT a CHECK, to keep validation uniform with chapter ranges.
--
-- Append-only. See docs/features/exam-periods-and-formative-assessments/02-data-model.md.

CREATE TABLE exam_periods (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    syllabus_breakdown_id UUID NOT NULL REFERENCES syllabus_breakdowns(id) ON DELETE CASCADE,
    start_date            DATE NOT NULL,
    end_date              DATE NOT NULL,
    name                  TEXT NOT NULL,           -- e.g. 'Mid-term exams'
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_exam_periods_breakdown ON exam_periods(syllabus_breakdown_id);

CREATE TABLE breakdown_holidays (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    syllabus_breakdown_id UUID NOT NULL REFERENCES syllabus_breakdowns(id) ON DELETE CASCADE,
    start_date            DATE NOT NULL,
    end_date              DATE NOT NULL,
    name                  TEXT NOT NULL,           -- e.g. 'Eid-ul-Fitr'
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_breakdown_holidays_breakdown ON breakdown_holidays(syllabus_breakdown_id);
