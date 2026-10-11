create table records (
  id bigint generated always as identity primary key,
  name text,
  uid text,
  problem text,
  created_at timestamptz default now()
);

alter table records enable row level security;
