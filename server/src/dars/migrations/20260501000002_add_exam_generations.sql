CREATE TABLE IF NOT EXISTS exam_generations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    webhook_url     TEXT,
    curriculum      TEXT NOT NULL,
    grade           INTEGER NOT NULL,
    subject         TEXT NOT NULL,
    page_ranges     TEXT NOT NULL,
    generation_type TEXT NOT NULL DEFAULT 'exam',
    status          TEXT NOT NULL DEFAULT 'PENDING',
    result          JSONB,
    error_detail    TEXT,
    external_ref    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
