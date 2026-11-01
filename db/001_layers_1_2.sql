-- Layer 2 (uniqueness): one row per distinct content, identified by SHA-256.
create table if not exists artifact (
    id          bigserial primary key,
    sha256      char(64)    not null unique,
    size_bytes  bigint      not null,
    created_at  timestamptz not null default now()
);
comment on table artifact is 'Слой 2 «Артефакт» (уникальность): одно содержимое — одна строка, по хешу.';

-- Layer 1 (presence): every copy of every file, duplicates included, flat; append-only.
create table if not exists carrier_file (
    id            bigserial primary key,
    artifact_id   bigint      not null references artifact(id),
    location      text        not null unique,   -- path relative to the archive root, same on the PC (Cold) and the VPS (/srv/cold)
    source_system  text       not null,          -- where it was collected from: Google Drive, Gmail, Почта Mail.ru, Облако Mail.ru, Notion ...
    source_account text       not null,          -- which account or mailbox of that system
    name          text        not null,
    ext           text        not null,
    carrier_type  text        not null,          -- file kind: document, sheet, presentation, image, mail ...
    size_bytes    bigint      not null,
    modified_at   date,
    added_at      timestamptz not null default now()
);
comment on table carrier_file is 'Слой 1 «Файл носителя» (наличие): каждая копия каждого файла, с дублями; только пополняется.';
create index if not exists carrier_file_artifact_idx on carrier_file(artifact_id);
create index if not exists carrier_file_source_idx on carrier_file(source_system, source_account);

-- Staging for bulk loads of layer 1.
create unlogged table if not exists load_carrier_file (
    location text, source_system text, source_account text, name text, ext text, carrier_type text,
    size_bytes bigint, modified_at date, sha256 char(64)
);
