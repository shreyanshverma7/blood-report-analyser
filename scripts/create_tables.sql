create table if not exists reports (
    id            uuid primary key default gen_random_uuid(),
    uploaded_at   timestamptz not null default now(),
    report_date   date,
    patient_age   integer,
    patient_gender text,
    lab_name      text,
    raw_text      text not null
);

create table if not exists markers (
    id          uuid primary key default gen_random_uuid(),
    report_id   uuid not null references reports(id) on delete cascade,
    name        text not null,
    value       float,
    value_text  text,
    unit        text,
    ref_low     float,
    ref_high    float,
    flag        text check (flag in ('normal', 'high', 'low', 'abnormal'))
);

create index if not exists markers_report_id_idx on markers(report_id);
