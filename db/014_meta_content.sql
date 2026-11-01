-- Level 3 tables. meta and content each point only at the artifact; they know nothing of each other.
--   dict_format  format and its version by signature (PRONOM PUID), a property of the artifact
--   meta         properties written inside the file: title, its own date, the rest as is (JSON)
--   content      text taken out of the file, as is; versions per method, one selected
begin;

alter table dict_extraction_outcome rename to dict_outcome;
alter table dict_extraction_error rename to dict_error;
update dict_outcome set description = 'Методика не отработала. Вид ошибки — из dict_error, сообщение инструмента хранится у производной как есть.'
where name = 'Ошибка';

create table dict_format (like dict_tech_step including all);
alter table dict_format add column mime text not null default '';
comment on table dict_format is 'Формат и его версия по реестру PRONOM: name = PUID (fmt/412), description = название и версия.';

alter table artifact add column format_id smallint references dict_format(id);

create table meta (
    id          bigserial primary key,
    artifact_id bigint not null references artifact(id),
    method_id   int not null references method(id),
    title       text,                                -- subject of a letter, Title of a document, as written
    dated_at    timestamptz,                         -- the document's own date: sent, created, taken
    data        jsonb not null default '{}',         -- every other property as the tool gave it
    created_at  timestamptz not null default now(),
    unique (artifact_id, method_id)
);
comment on table meta is 'Свойства, записанные внутри файла: заголовок, дата документа, остальное как есть. Уровень 3.';

create table content (
    id            bigserial primary key,
    artifact_id   bigint not null references artifact(id),
    method_id     int not null references method(id),
    outcome_id    smallint not null references dict_outcome(id),
    error_id      smallint references dict_error(id),
    error_message text,                              -- the tool's own words, only on an error
    body          text,                              -- text as taken out, never edited
    body_hash     text,                              -- SHA-256 of body: equal texts in different files
    selected      boolean not null default false,
    created_at    timestamptz not null default now(),
    unique (artifact_id, method_id)
);
create unique index content_selected_one on content (artifact_id) where selected;
comment on table content is 'Содержание: текст, вынутый из предмета, как есть. Версии по методикам, выбрана одна. Уровень 3.';

create index meta_artifact_idx on meta (artifact_id);
create index content_artifact_idx on content (artifact_id);

-- code adds what it finds; closed lists stay read-only for it
revoke insert, update on dict_outcome, dict_error from archive_app;
grant select on dict_outcome, dict_error, dict_format, meta, content to archive_app, archive_reader;
grant insert on dict_format, method, meta, content to archive_app;
grant update (format_id) on artifact to archive_app;
grant update (selected) on content to archive_app;
grant usage, select on all sequences in schema public to archive_app;

commit;

select string_agg(table_name, ', ' order by table_name) from information_schema.tables where table_schema = 'public';
