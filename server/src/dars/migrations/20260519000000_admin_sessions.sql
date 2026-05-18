-- F5.2 — admin session storage.
--
-- Lookup-on-every-request session table (D-17 / phase doc): the
-- session_token is the row's id, signed and base64'd into the cookie
-- the client carries as `dars_admin_session`. Idempotent.

CREATE TABLE IF NOT EXISTS admin_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_admin_id UUID NOT NULL REFERENCES org_admins(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_admin_sessions_admin
    ON admin_sessions(org_admin_id);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_active
    ON admin_sessions(expires_at) WHERE revoked_at IS NULL;
