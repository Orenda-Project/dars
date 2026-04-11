create table if not exists lesson_plan_edits (
  id          uuid primary key default gen_random_uuid(),
  client_id   uuid not null references clients(id) on delete cascade,
  lp_id       uuid not null references lesson_plans(id) on delete cascade,
  edit_prompt text not null,
  content_before text,
  content_bilingual_before text,
  created_at  timestamptz not null default now()
);

create index lesson_plan_edits_lp_id_idx on lesson_plan_edits(lp_id);
create index lesson_plan_edits_client_id_idx on lesson_plan_edits(client_id);
