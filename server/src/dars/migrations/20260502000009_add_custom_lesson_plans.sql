CREATE TABLE IF NOT EXISTS custom_lesson_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    external_id TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    grade VARCHAR(50) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    curriculum VARCHAR(50) NOT NULL,
    topic TEXT,
    page_number VARCHAR(50),
    content TEXT,
    content_bilingual TEXT,
    tags JSONB NOT NULL DEFAULT '{}',
    metadata_ JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_custom_lesson_plans_client_id
    ON custom_lesson_plans (client_id);

CREATE INDEX IF NOT EXISTS ix_custom_lesson_plans_external_id
    ON custom_lesson_plans (client_id, external_id);
