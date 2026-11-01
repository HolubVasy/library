-- Only on top, enforced by rights: the code role adds rows and never rewrites them.
-- Default privileges of 003 gave archive_app table-wide UPDATE (and INSERT on closed dictionaries); CI caught it.
-- Revoking a table privilege also drops its column grants, so the few columns the code may set are granted again.
begin;

revoke update on archive.content, archive.meta, archive.method, archive.artifact_category from archive_app;
revoke insert, update on dict.category, dict.platform from archive_app;
revoke update on dict.format, dict.source from archive_app;

grant update (selected) on archive.content to archive_app;
grant update (format_id) on archive.artifact to archive_app;
grant update (removed_at, removed_reason) on archive.artifact_tag to archive_app;

alter default privileges for role archive in schema public revoke insert, update on tables from archive_app;

commit;
