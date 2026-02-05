create table if not exists public.bet_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users(id) on delete cascade,
    prediction_id bigint references public.prediction_history(id) on delete cascade,
    label text not null,
    stake numeric,
    odd numeric,
    status text default 'pending',
    created_at timestamptz default now()
);
create index if not exists bet_logs_user_idx on public.bet_logs(user_id);
create index if not exists bet_logs_prediction_idx on public.bet_logs(prediction_id);

create table if not exists public.ai_requests (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users(id) on delete cascade,
    fixture_id bigint,
    payload jsonb not null,
    response_text text,
    model text,
    tokens_used int,
    created_at timestamptz default now()
);
create index if not exists ai_requests_user_idx on public.ai_requests(user_id);
create index if not exists ai_requests_fixture_idx on public.ai_requests(fixture_id);

create table if not exists public.notifications_log (
    id uuid primary key default gen_random_uuid(),
    event text not null,
    severity text default 'info',
    payload jsonb default '{}'::jsonb,
    created_at timestamptz default now()
);
create index if not exists notifications_event_idx on public.notifications_log(event);

create table if not exists public.fixtures_cache (
    fixture_id bigint primary key,
    payload jsonb not null,
    fetched_at timestamptz default now(),
    expires_at timestamptz
);
create index if not exists fixtures_cache_expiry_idx on public.fixtures_cache(expires_at);
