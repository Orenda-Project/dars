-- Initial schema for Dars B2B lesson plan service
-- Creates: clients, lesson_plans, webhook_deliveries

-- ──────────────────────────────────────────────
-- clients
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clients (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name              TEXT NOT NULL,
    api_key_hash      TEXT NOT NULL UNIQUE,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    webhook_url       TEXT,
    email             TEXT UNIQUE,
    supabase_user_id  TEXT UNIQUE,
    is_admin          BOOLEAN NOT NULL DEFAULT FALSE,
    default_teacher_id UUID,            -- nullable; no FK — teachers table is not used
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- lesson_plans
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lesson_plans (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    webhook_url         TEXT,
    grade               TEXT NOT NULL,
    subject             TEXT NOT NULL,
    topic               TEXT,
    page_number         TEXT,
    class_strength      INTEGER,
    status              TEXT NOT NULL DEFAULT 'PENDING',
    content             TEXT,
    content_bilingual   TEXT,
    tags                JSONB NOT NULL DEFAULT '{}',
    metadata_           JSONB NOT NULL DEFAULT '{}',
    external_ref        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ──────────────────────────────────────────────
-- webhook_deliveries
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id         UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    lesson_plan_id    UUID NOT NULL,
    event             TEXT NOT NULL,
    payload           JSONB NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending',
    attempts          INTEGER NOT NULL DEFAULT 0,
    last_attempt_at   TIMESTAMPTZ,
    next_attempt_at   TIMESTAMPTZ,
    response_status   INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Drop teachers table if it exists (we are not building teachers for now)
DROP TABLE IF EXISTS teachers CASCADE;
