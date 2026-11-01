-- Source dictionary: where every carrier file was collected from (type, kind, account) and how.
create table if not exists source (
    id            serial primary key,
    source_type   text not null,          -- Облако, Почта, Контакты, Заметки, Профиль, Бумага, Локальный носитель, Аккаунт
    source_kind   text not null,          -- Google Drive, Облако Mail.ru, Gmail, Почта Mail.ru, Notion, LinkedIn ...
    account       text not null default '',
    method        text,                   -- how it was collected: rclone, Outlook, Takeout, вручную
    collected_on  date,
    completeness  text,                   -- полный / частичный (и почему)
    unique (source_type, source_kind, account)
);
comment on table source is 'Справочник источников: тип, вид, аккаунт; способ, дата и полнота сбора.';

-- map the two loose columns of layer 1 onto the dictionary
create temporary table source_map (old_system text, old_account text,
    source_type text, source_kind text, account text, method text, collected_on date, completeness text);
insert into source_map values
 ('Google Drive', 'dkhj459878@gmail.com', 'Облако', 'Google Drive', 'dkhj459878@gmail.com', 'rclone', '2026-10-29', 'полный; 3 объекта не выгружаются'),
 ('Google Drive', 'holubvasy@gmail.com', 'Облако', 'Google Drive', 'holubvasy@gmail.com', 'rclone', '2026-10-29', 'полный; 2 объекта не выгружаются'),
 ('Google Drive', 'vasili.holub.family@gmail.com', 'Облако', 'Google Drive', 'vasili.holub.family@gmail.com', 'rclone', '2026-10-29', 'полный; 3 объекта не выгружаются'),
 ('Облако Mail.ru', 'vasiliygolub@mail.ru', 'Облако', 'Облако Mail.ru', 'vasiliygolub@mail.ru', 'rclone', '2026-10-29', 'полный'),
 ('Gmail', 'holubvasy@gmail.com', 'Почта', 'Gmail', 'holubvasy@gmail.com', 'Outlook', '2026-10-29', 'частичный: без папки All Mail'),
 ('Gmail', 'dkhj459878@gmail.com', 'Почта', 'Gmail', 'dkhj459878@gmail.com', 'Outlook', '2026-10-29', 'частичный: без папки All Mail'),
 ('Gmail', 'vasili.holub.family@gmail.com', 'Почта', 'Gmail', 'vasili.holub.family@gmail.com', 'Outlook', '2026-10-29', 'частичный: без папки All Mail'),
 ('Почта Mail.ru', 'vasiliygolub@mail.ru', 'Почта', 'Почта Mail.ru', 'vasiliygolub@mail.ru', 'Outlook', '2026-10-29', 'полный'),
 ('Почта Яндекс', 'vasiliygolub@yandex.ru', 'Почта', 'Почта Яндекс', 'vasiliygolub@yandex.ru', 'Outlook', '2026-10-29', 'полный'),
 ('Почта jaydevs.dev', 'vasili.holub@jaydevs.dev', 'Почта', 'Почта JayDevs', 'vasili.holub@jaydevs.dev', 'Outlook', '2026-10-29', 'проверить полноту'),
 ('Экспорт контактов', 'Mail.ru', 'Контакты', 'Mail.ru', 'vasiliygolub@mail.ru', 'вручную', '2026-10-29', 'полный'),
 ('Экспорт контактов', 'Yandex.ru', 'Контакты', 'Яндекс', 'vasiliygolub@yandex.ru', 'вручную', '2026-10-29', 'полный'),
 ('Экспорт контактов', 'holubvasy@gmail.com', 'Контакты', 'Google', 'holubvasy@gmail.com', 'вручную', '2026-10-29', 'без Other contacts'),
 ('Экспорт контактов', 'dkhj459878@gmail.com', 'Контакты', 'Google', 'dkhj459878@gmail.com', 'вручную', '2026-10-29', 'без Other contacts'),
 ('LinkedIn', 'профиль', 'Профиль', 'LinkedIn', 'vasili-holub', 'вручную', '2026-10-29', 'только PDF профиля; архив данных запрошен'),
 ('Экспорт вручную', '', 'Аккаунт', 'Google Takeout', 'vasili.holub.family@gmail.com', 'Takeout', '2026-10-29', 'архив не распакован');

insert into source (source_type, source_kind, account, method, collected_on, completeness)
select source_type, source_kind, account, method, collected_on, completeness from source_map
on conflict (source_type, source_kind, account) do nothing;

alter table carrier_file add column if not exists source_id int references source(id);
update carrier_file c set source_id = s.id
from source_map m join source s on (s.source_type, s.source_kind, s.account) = (m.source_type, m.source_kind, m.account)
where c.source_id is null and c.source_system = m.old_system and c.source_account = m.old_account;

do $$ begin
  if exists (select 1 from carrier_file where source_id is null) then
    raise exception 'carrier_file rows without source: %', (select count(*) from carrier_file where source_id is null);
  end if;
end $$;

alter table carrier_file alter column source_id set not null;
drop index if exists carrier_file_source_idx;
alter table carrier_file drop column source_system, drop column source_account;
create index if not exists carrier_file_source_id_idx on carrier_file(source_id);

-- future loads name the source by type, kind and account
alter table load_carrier_file drop column if exists source_system, drop column if exists source_account;
alter table load_carrier_file add column if not exists source_type text, add column if not exists source_kind text, add column if not exists account text;

select s.source_type, s.source_kind, s.account, s.method, s.completeness, count(c.id) files
from source s left join carrier_file c on c.source_id = s.id group by s.id order by 1, 2, 3;
