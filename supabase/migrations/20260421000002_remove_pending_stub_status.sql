-- Remove pending as a valid stub status; stubs are generated synchronously
ALTER TABLE curriculum_lp_stubs DROP CONSTRAINT IF EXISTS curriculum_lp_stubs_status_check;
ALTER TABLE curriculum_lp_stubs ADD CONSTRAINT curriculum_lp_stubs_status_check
  CHECK (status IN ('generating', 'generated', 'failed'));
UPDATE curriculum_lp_stubs SET status = 'generating' WHERE status = 'pending';
