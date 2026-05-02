CREATE TABLE IF NOT EXISTS custom_exam_generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    external_id TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    curriculum VARCHAR(50) NOT NULL,
    grade INTEGER NOT NULL,
    subject VARCHAR(255) NOT NULL,
    page_ranges TEXT NOT NULL,
    generation_type VARCHAR(50) NOT NULL DEFAULT 'exam',
    result JSONB,
    error_detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_custom_exam_generations_client_id
    ON custom_exam_generations (client_id);

CREATE INDEX IF NOT EXISTS ix_custom_exam_generations_external_id
    ON custom_exam_generations (client_id, external_id);
