-- Roles: the admin role (archive) owns the schema and runs migrations;
-- archive_app is what the code uses; archive_reader is for viewing (UI, reports).
-- Passwords come in as psql variables (-v app_pw=... -v reader_pw=...) and are never stored in this file.

revoke create on schema public from public;

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'archive_app') then create role archive_app login; end if;
  if not exists (select 1 from pg_roles where rolname = 'archive_reader') then create role archive_reader login; end if;
end $$;
alter role archive_app password :'app_pw';
alter role archive_reader password :'reader_pw';

grant connect on database archive to archive_app, archive_reader;
grant usage on schema public to archive_app, archive_reader;

-- code: read and add; layers 1-2 are append-only, so no delete or truncate
grant select, insert on carrier_file, artifact, load_carrier_file to archive_app;
grant select, insert, update on source to archive_app;
grant usage, select on all sequences in schema public to archive_app;
grant select on all tables in schema public to archive_reader;

-- tables created by later migrations get the same split by default
alter default privileges for role archive in schema public grant select, insert, update on tables to archive_app;
alter default privileges for role archive in schema public grant usage, select on sequences to archive_app;
alter default privileges for role archive in schema public grant select on tables to archive_reader;

select rolname, rolsuper, rolcreaterole, rolcreatedb from pg_roles where rolname like 'archive%' order by 1;
