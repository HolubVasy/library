-- Closed lists from the concept ("Лестницы") and the methodology that every derivative will point to.
-- Dictionaries are keyed by their name, so a row reads the same in the DB as in the concept.

create table if not exists tech_step (            -- лестница технологий (КАК)
    name text primary key,
    ord  smallint not null unique
);
insert into tech_step values ('Детерминированная', 1), ('Гибридная', 2), ('Недетерминированная', 3), ('Комплексная', 4)
on conflict do nothing;

create table if not exists escalation_step (      -- лестница эскалации (КТО)
    name text primary key,
    ord  smallint not null unique
);
insert into escalation_step values ('Правило', 1), ('Низкий уровень', 2), ('Средний уровень', 3),
                                   ('Высокий уровень', 4), ('Персона', 5)
on conflict do nothing;

create table if not exists platform (
    name text primary key
);
insert into platform values ('.NET'), ('Python'), ('Anthropic API') on conflict do nothing;

create table if not exists extraction_outcome (   -- итог получения производной
    name        text primary key,
    description text not null default ''
);
alter table extraction_outcome add column if not exists description text not null default '';
delete from extraction_outcome where name = 'Не поддерживается';
insert into extraction_outcome values
 ('Вынуто', 'Методика отработала и дала непустой результат.'),
 ('Пусто',  'Методика отработала без сбоя, но результата нет: например, скан без текстового слоя.'),
 ('Ошибка', 'Методика не отработала. Вид ошибки берётся из справочника extraction_error, сообщение инструмента хранится у производной как есть.')
on conflict (name) do update set description = excluded.description;

create table if not exists extraction_error (     -- вид ошибки при итоге «Ошибка»
    name        text primary key,
    description text not null default ''
);
insert into extraction_error values
 ('Формат не поддерживается', 'Для этого формата нет методики на текущей ступени.'),
 ('Файл повреждён',           'Инструмент не смог открыть файл: битая структура, обрезан.'),
 ('Защищён паролем',          'Файл или архив зашифрован владельцем.'),
 ('Превышено время',          'Методика не уложилась в отведённое время.'),
 ('Сбой инструмента',         'Инструмент упал или вернул ошибку, причина не из списка выше.')
on conflict (name) do update set description = excluded.description;
grant select on extraction_error to archive_app;

-- carrier types become a closed list; carrier_file keeps the name, now checked against it
create table if not exists carrier_type (
    name text primary key
);
insert into carrier_type values ('Письмо'), ('Документ'), ('Изображение'), ('Таблица'), ('Презентация'),
                                ('Архив'), ('Видео'), ('Аудио'), ('Контакты'), ('Другое')
on conflict do nothing;
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'carrier_file_carrier_type_fkey') then
    alter table carrier_file add constraint carrier_file_carrier_type_fkey foreign key (carrier_type) references carrier_type(name);
  end if;
end $$;

-- a methodology is a fixed recipe; any change in it (version, commit, prompt) is a new row
create table if not exists methodology (
    id               serial primary key,
    tech_step        text not null references tech_step(name),
    escalation_step  text not null references escalation_step(name),
    platform         text references platform(name),      -- empty for Персона
    platform_version text not null default '',
    tool             text not null default '',            -- package, utility, own repo, model family
    tool_version     text not null default '',            -- package version, commit, model version
    formats          text[] not null default '{}',        -- extensions it takes
    description      text not null default '',            -- how it was done; for a model, with the prompt version
    created_at       timestamptz not null default now(),
    unique (tech_step, escalation_step, platform, platform_version, tool, tool_version, description)
);
comment on table methodology is 'Методика: как получена производная. Ступени лестниц, платформа, инструмент, версии, описание.';

grant select on tech_step, escalation_step, platform, extraction_outcome, carrier_type to archive_app;
grant insert on platform, methodology to archive_app;

select 'tech_step' t, count(*) from tech_step union all select 'escalation_step', count(*) from escalation_step
union all select 'platform', count(*) from platform union all select 'extraction_outcome', count(*) from extraction_outcome
union all select 'carrier_type', count(*) from carrier_type union all select 'methodology', count(*) from methodology;
