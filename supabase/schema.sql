-- Table: reports
create table if not exists reports (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    summary text,
    tags text[] default '{}',
    pdf_path text,
    status text default 'draft',
    author text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- Table: social_queue
create table if not exists social_queue (
    id uuid primary key default gen_random_uuid(),
    channel text not null,
    payload jsonb not null,
    metadata jsonb default '{}'::jsonb,
    status text not null default 'pending',
    run_at timestamptz default now(),
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    error_message text
);
create index if not exists idx_social_queue_status_run_at
    on social_queue (status, run_at);

-- Table: user_settings
create table if not exists user_settings (
    id uuid primary key default gen_random_uuid(),
    email text not null,
    preferences jsonb default '{}'::jsonb,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
create unique index if not exists idx_user_settings_email on user_settings (email);

-- Table: webhook_logs
create table if not exists webhook_logs (
    id uuid primary key default gen_random_uuid(),
    source text not null,
    payload jsonb not null,
    status text not null,
    created_at timestamptz default now()
);

-- Basic policies skeleton (à adapter selon votre projet)
-- enable row level security
alter table reports enable row level security;
alter table social_queue enable row level security;
alter table user_settings enable row level security;
alter table webhook_logs enable row level security;

-- sample policy (admin-only via service role)
create policy "service-role-full-access" on reports
    for all to service_role using (true);
create policy "service-role-full-access" on social_queue
    for all to service_role using (true);
create policy "service-role-full-access" on user_settings
    for all to service_role using (true);
create policy "service-role-full-access" on webhook_logs
    for all to service_role using (true);
