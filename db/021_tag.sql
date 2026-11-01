-- Tags: our working decisions about an artifact ("not now", "in work"), unlike categories, which are verdicts of
-- methods. A tag is put and later taken off; taking off keeps the row with the date and reason, so repeated
-- take-offs show where the rules were wrong.
begin;

create table dict.tag (like dict.tech_step including all);
alter table dict.tag add column caption text not null default '';
comment on table dict.tag is 'Рабочие решения о документе: name — ключ, caption — подпись.';
insert into dict.tag (name, caption, description, ord) values
  ('skip', 'Не берём в работу', 'Пока не обрабатываем дальше: шум, карьерные площадки.', 1),
  ('focus', 'В работе', 'Отобрано для работы сейчас.', 2);

create table archive.artifact_tag (
    id             bigserial primary key,
    artifact_id    bigint not null references archive.artifact(id),
    tag_id         bigint not null references dict.tag(id),
    reason         text not null,                    -- why it was put: the query or decision behind it
    created_at     timestamptz not null default now(),
    removed_at     timestamptz,                      -- taken off; the row stays
    removed_reason text
);
create unique index artifact_tag_active_one on archive.artifact_tag (artifact_id, tag_id) where removed_at is null;
create index artifact_tag_artifact_idx on archive.artifact_tag (artifact_id);
comment on table archive.artifact_tag is 'Теги артефакта: ставятся и снимаются, снятые остаются с датой и причиной.';

grant select on dict.tag, archive.artifact_tag to archive_app, archive_reader;
grant insert on archive.artifact_tag to archive_app;
grant update (removed_at, removed_reason) on archive.artifact_tag to archive_app;
grant usage, select on all sequences in schema archive, dict to archive_app;

commit;
