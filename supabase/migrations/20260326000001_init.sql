-- Enable UUID generation
create extension if not exists "pgcrypto";

-- Clients table (B2B tenants)
create table if not exists clients (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    api_key_hash text not null unique,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

-- Lesson plans table
create table if not exists lesson_plans (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references clients(id) on delete cascade,
    external_ref text,
    grade text not null,
    subject text not null,
    topic text,
    page_number integer,
    class_strength integer,
    content text,
    content_bilingual text,
    status text not null default 'PENDING' check (status in ('PENDING', 'READY', 'ERROR')),
    metadata jsonb not null default '{}',
    tags jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists lesson_plans_client_id_idx on lesson_plans(client_id);
create index if not exists lesson_plans_status_idx on lesson_plans(status);
create index if not exists lesson_plans_created_at_idx on lesson_plans(created_at desc);

-- Lesson plan edits table
create table if not exists lesson_plan_edits (
    id uuid primary key default gen_random_uuid(),
    lesson_plan_id uuid not null references lesson_plans(id) on delete cascade,
    content text not null,
    edit_source text not null check (edit_source in ('USER', 'AI', 'GENERATED')),
    edit_instruction text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists lesson_plan_edits_lp_id_idx on lesson_plan_edits(lesson_plan_id);

-- Auto-update updated_at on lesson_plans
create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger lesson_plans_updated_at
    before update on lesson_plans
    for each row execute function update_updated_at();
