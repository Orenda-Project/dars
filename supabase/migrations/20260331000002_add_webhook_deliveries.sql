create table if not exists webhook_deliveries (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references clients(id) on delete cascade,
    lesson_plan_id uuid not null references lesson_plans(id) on delete cascade,
    event text not null,
    payload jsonb not null,
    status text not null default 'pending' check (status in ('pending', 'delivered', 'failed')),
    attempts integer not null default 0,
    last_attempt_at timestamptz,
    next_attempt_at timestamptz,
    response_status integer,
    created_at timestamptz not null default now()
);

create index if not exists webhook_deliveries_client_id_idx on webhook_deliveries(client_id);
create index if not exists webhook_deliveries_status_idx on webhook_deliveries(status);
