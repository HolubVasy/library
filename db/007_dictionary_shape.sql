-- Every dictionary gets one shape: id, name, description, comment, ord (display order), created_at.
-- Links are <entity>_id. description is the meaning of a value; comment is free notes about it.
begin;

alter table carrier_file drop constraint if exists carrier_file_carrier_type_fkey;
drop table if exists methodology, tech_step, escalation_step, platform, extraction_outcome, extraction_error, carrier_type;

create table tech_step (                 -- лестница технологий (КАК); ord is the order of the steps
    id          smallint generated always as identity primary key,
    name        text not null unique,
    description text not null default '',
    comment     text not null default '',
    ord         smallint,
    created_at  timestamptz not null default now()
);
create table escalation_step (like tech_step including all);      -- лестница эскалации (КТО)
create table platform (like tech_step including all);
create table extraction_outcome (like tech_step including all);   -- итог получения производной
create table extraction_error (like tech_step including all);     -- вид ошибки при итоге «Ошибка»
create table carrier_type (like tech_step including all);

insert into tech_step (name, ord, description) values
 ('Детерминированная', 1, 'Код и софт: скрипт, утилита, библиотека. Тот же вход и та же версия дают тот же результат.'),
 ('Гибридная', 2, 'Скрипт + дешёвая модель в любом порядке. Повторяемости нет.'),
 ('Недетерминированная', 3, 'Только модели и агенты, всё, что не повторяется.'),
 ('Комплексная', 4, 'Конвейер из всего сразу: детерминированные и недетерминированные шаги, несколько моделей.');

insert into escalation_step (name, ord, description) values
 ('Правило', 1, 'Исполнитель — код по правилу, без модели.'),
 ('Низкий уровень', 2, 'Дешёвая модель.'),
 ('Средний уровень', 3, 'Модель средней силы.'),
 ('Высокий уровень', 4, 'Сильная модель.'),
 ('Персона', 5, 'Человек.');

insert into platform (name, ord, description) values
 ('.NET', 1, 'Свой код на .NET.'),
 ('Python', 2, 'Скрипты на Python; из них же запускаются утилиты (LibreOffice, Tesseract, 7-Zip).'),
 ('Anthropic API', 3, 'Модели Claude через API.');

insert into extraction_outcome (name, ord, description) values
 ('Вынуто', 1, 'Методика отработала и дала непустой результат.'),
 ('Пусто', 2, 'Методика отработала без сбоя, но результата нет: например, скан без текстового слоя.'),
 ('Ошибка', 3, 'Методика не отработала. Вид ошибки — из extraction_error, сообщение инструмента хранится у производной как есть.');

insert into extraction_error (name, ord, description) values
 ('Формат не поддерживается', 1, 'Для этого формата нет методики на текущей ступени.'),
 ('Файл повреждён', 2, 'Инструмент не смог открыть файл: битая структура, обрезан.'),
 ('Защищён паролем', 3, 'Файл или архив зашифрован владельцем.'),
 ('Превышено время', 4, 'Методика не уложилась в отведённое время.'),
 ('Сбой инструмента', 5, 'Инструмент упал или вернул ошибку, причина не из списка выше.');

insert into carrier_type (name, ord, description) values
 ('Письмо', 1, 'Сообщение электронной почты.'),
 ('Документ', 2, 'Текстовый документ: PDF, Word, RTF, текст.'),
 ('Таблица', 3, 'Excel, CSV и подобные.'),
 ('Презентация', 4, 'PowerPoint и подобные.'),
 ('Изображение', 5, 'Фото, скан, картинка.'),
 ('Архив', 6, 'ZIP, RAR, 7z: контейнер с другими файлами.'),
 ('Контакты', 7, 'Выгрузка контактов (vCard).'),
 ('Видео', 8, ''),
 ('Аудио', 9, ''),
 ('Другое', 10, 'Всё, что не подошло под типы выше.');

-- layer 1 links the carrier type by id
alter table carrier_file add column carrier_type_id smallint references carrier_type(id);
update carrier_file c set carrier_type_id = t.id from carrier_type t where t.name = c.carrier_type;
do $$ begin
  if exists (select 1 from carrier_file where carrier_type_id is null) then
    raise exception 'carrier types not in the dictionary: %', (select string_agg(distinct carrier_type, ', ') from carrier_file where carrier_type_id is null);
  end if;
end $$;
alter table carrier_file alter column carrier_type_id set not null, drop column carrier_type;
create index carrier_file_carrier_type_id_idx on carrier_file(carrier_type_id);

-- the source dictionary gets the same notes and order
alter table source add column if not exists description text not null default '',
                   add column if not exists comment text not null default '',
                   add column if not exists ord smallint,
                   add column if not exists created_at timestamptz not null default now();

create table methodology (               -- как получена производная; any change is a new row
    id                 serial primary key,
    tech_step_id       smallint not null references tech_step(id),
    escalation_step_id smallint not null references escalation_step(id),
    platform_id        smallint references platform(id),   -- empty for Персона
    platform_version   text not null default '',
    tool               text not null default '',            -- package, utility, own repo, model family
    tool_version       text not null default '',            -- package version, commit, model version
    formats            text[] not null default '{}',        -- extensions it takes
    description        text not null default '',            -- how it was done; for a model, with the prompt version
    comment            text not null default '',
    created_at         timestamptz not null default now(),
    unique (tech_step_id, escalation_step_id, platform_id, platform_version, tool, tool_version, description)
);
comment on table methodology is 'Методика: как получена производная. Ступени лестниц, платформа, инструмент, версии, описание.';

-- closed lists are read-only for the code; platforms and methodologies it may add
revoke insert, update on tech_step, escalation_step, extraction_outcome, extraction_error, carrier_type from archive_app;
grant select on tech_step, escalation_step, platform, extraction_outcome, extraction_error, carrier_type to archive_app, archive_reader;
grant insert on platform to archive_app;
grant select, insert on methodology to archive_app;
grant select on methodology to archive_reader;
grant usage, select on all sequences in schema public to archive_app;

commit;

select t.name, count(*) from carrier_file c join carrier_type t on t.id = c.carrier_type_id group by t.name, t.ord order by t.ord;
