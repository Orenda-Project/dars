-- Add review column to lesson_plans for storing LP reviewer results
alter table lesson_plans
    add column if not exists review jsonb null;
