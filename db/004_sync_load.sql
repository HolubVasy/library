-- Lets the code (archive_app) run the incremental layer 1-2 load on its own:
-- the staging table carries the collection method, and the app may empty it between runs.
alter table load_carrier_file add column if not exists method text;
grant truncate on load_carrier_file to archive_app;
