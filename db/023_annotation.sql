-- Annotation: what a document is about, in two or three sentences written by a model. Shaped like content:
-- versions per method, one selected. Only on top: the code adds rows and moves the selection, nothing else.
begin;

create table archive.annotation (
    id          bigserial primary key,
    artifact_id bigint not null references archive.artifact(id),
    method_id   bigint not null references archive.method(id),
    text        text not null,                       -- as the model wrote it, never edited
    selected    boolean not null default false,
    created_at  timestamptz not null default now(),
    unique (artifact_id, method_id)
);
create unique index annotation_selected_one on archive.annotation (artifact_id) where selected;
create index annotation_artifact_idx on archive.annotation (artifact_id);
comment on table archive.annotation is 'Аннотация: о чём документ, в двух или трёх предложениях. Версии по методикам, выбрана одна.';

grant select on archive.annotation to archive_app, archive_reader;
grant insert on archive.annotation to archive_app;
grant update (selected) on archive.annotation to archive_app;
grant usage, select on sequence archive.annotation_id_seq to archive_app;

commit;
