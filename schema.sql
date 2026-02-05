create table app_users (
    id uuid primary key references auth.users(id) on delete cascade,
    full_name text,
    plan_code text default 'lite',
    beta_flag boolean default false,
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    constraint plan_check check (plan_code in ('lite','starter','pro','elite','beta'))
);

create table prediction_history (
    id bigserial primary key,
    timestamp_utc timestamptz not null,
    fixture_id bigint not null,
    league_id int not null,
    season int not null,
    home_team text,
    away_team text,
    selection text,
    confidence numeric,
    status_snapshot text,
    success_flag boolean,
    bet_stake numeric,
    bet_odd numeric,
    bet_return numeric,
    edge_comment text,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz default now()
);
