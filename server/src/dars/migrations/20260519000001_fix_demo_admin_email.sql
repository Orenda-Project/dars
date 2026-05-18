-- Fix the demo org admin's email so it can pass through EmailStr
-- validation. The old value `admin@dars-demo.local` was inserted by
-- the F1.5 seed (PR #42) before the dashboard's login endpoint
-- existed, and `.local` is mDNS-reserved — Pydantic's EmailStr
-- (via the email-validator library) refuses to accept it, so the
-- admin literally couldn't log in.
--
-- Migration is idempotent + targeted: only updates the row if it
-- still has the old `.local` value. New orgs created via the signup
-- API are unaffected.
--
-- The seed file is updated in the same change so reseeds use the new
-- value too.

UPDATE org_admins
SET email = 'admin@dars-demo.example',
    updated_at = now()
WHERE email = 'admin@dars-demo.local';
