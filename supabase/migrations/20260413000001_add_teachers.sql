-- Teachers table
create table if not exists teachers (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references clients(id) on delete cascade,
    name text not null,
    email text,
    phone text,
    school text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists teachers_client_id_idx on teachers(client_id);
create unique index if not exists teachers_client_email_uidx on teachers(client_id, email) where email is not null;

create trigger teachers_updated_at
    before update on teachers
    for each row execute function update_updated_at();
