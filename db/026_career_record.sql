-- Career records, as agreed in story 276: a period of work at an organization, linked to the documents it was read
-- from. Every record is signed with its method, so the roles a model read from one CV and the merged records stay
-- apart. Only on top: the code adds rows, nothing is rewritten.
--   dict.country          countries, added by the code on first use
--   dict.organization     organizations as written, with their country
--   career.record         a period of work: organization, position as written, start and end (empty end: current)
--   career.record_artifact  where a record comes from: the artifact and, for scans, the page
begin;

create table dict.country (like dict.tech_step including all);
comment on table dict.country is 'Страны: name по-английски, как его дала методика.';

create table dict.organization (like dict.tech_step including all);
alter table dict.organization add column country_id bigint references dict.country(id);
alter table dict.organization drop constraint organization_name_key;   -- one name may stand for entities in several countries
alter table dict.organization add unique nulls not distinct (name, country_id);
comment on table dict.organization is 'Организации, как они записаны в документах, со страной.';

create table career.record (
    id              bigserial primary key,
    organization_id bigint not null references dict.organization(id),
    position        text not null,                   -- as written
    start_date      date,                            -- the first day of the month or year when the day is not given
    end_date        date,                            -- empty for the current job
    method_id       bigint not null references archive.method(id),
    created_at      timestamptz not null default now()
);
create index record_method_idx on career.record (method_id);
comment on table career.record is 'Период работы: организация, должность как записана, начало и конец. Подписан методикой.';

create table career.record_artifact (
    id          bigserial primary key,
    record_id   bigint not null references career.record(id),
    artifact_id bigint not null references archive.artifact(id),
    page        int,                                 -- for scans; empty for a text
    created_at  timestamptz not null default now(),
    unique (record_id, artifact_id)
);
create index record_artifact_artifact_idx on career.record_artifact (artifact_id);
comment on table career.record_artifact is 'Откуда запись: артефакт и, для сканов, страница.';

grant select on dict.country, dict.organization, career.record, career.record_artifact to archive_app, archive_reader;
grant insert on dict.country, dict.organization, career.record, career.record_artifact to archive_app;
grant usage, select on all sequences in schema dict, career to archive_app;

commit;
