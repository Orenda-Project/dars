alter table lesson_plans
    add column if not exists teacher_id uuid not null references teachers(id) on delete restrict;

create index if not exists lesson_plans_teacher_id_idx on lesson_plans(teacher_id);
