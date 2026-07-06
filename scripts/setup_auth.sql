-- One-time auth migration. Run in the Supabase SQL editor.
-- Companion step: run scripts/wipe_report_chunks.py to clear pre-auth Qdrant
-- points, and enable the Email auth provider in Authentication > Providers.
--
-- WIPES all existing (pre-auth, unowned) rows — they have no user and would
-- violate the NOT NULL user_id constraint.

begin;

delete from public.markers;
delete from public.reports;

-- DEFAULT auth.uid(): inserts through the anon-key client with a user JWT get
-- the owner stamped by Postgres itself — the app never passes user_id.
alter table public.reports
  add column user_id uuid not null default auth.uid() references auth.users(id) on delete cascade;

create index if not exists reports_user_id_idx on public.reports (user_id);

alter table public.reports enable row level security;
alter table public.markers enable row level security;

create policy "users manage own reports" on public.reports
  for all to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- markers have no user_id column: ownership flows through the parent report
create policy "users manage own markers" on public.markers
  for all to authenticated
  using (
    exists (
      select 1 from public.reports r
      where r.id = markers.report_id and r.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.reports r
      where r.id = markers.report_id and r.user_id = auth.uid()
    )
  );

commit;
