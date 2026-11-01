-- A source is the unique combination of three separate dictionaries: type, vendor, account.
-- Replaces the free-text source_type / source_kind / account of dict_source.
begin;

create table dict_source_type (like dict_tech_step including all);
create table dict_vendor      (like dict_tech_step including all);
create table dict_account     (like dict_tech_step including all);

insert into dict_source_type (name, ord) values ('Облако', 1), ('Почта', 2), ('Контакты', 3), ('Аккаунт', 4), ('Профиль', 5);
update dict_source_type set description = 'Выгрузка аккаунта целиком (Google Takeout и подобные).' where name = 'Аккаунт';

insert into dict_vendor (name, ord, comment) values
 ('Google', 1, ''), ('Mail.ru', 2, ''), ('Яндекс', 3, ''), ('LinkedIn', 4, ''),
 ('JayDevs', 5, 'Свой почтовый сервер mail.jaydevs.dev (95.217.72.82), не Google и не Microsoft; проверено по MX 2026-10-30.');

-- an account lives at exactly one vendor; dict_source repeats the vendor and a composite key keeps the two in step
alter table dict_account add column vendor_id smallint not null references dict_vendor(id);
alter table dict_account add constraint dict_account_id_vendor_key unique (id, vendor_id);
insert into dict_account (name, ord, vendor_id)
select a.name, a.ord, v.id from (values
 ('dkhj459878@gmail.com', 1, 'Google'), ('holubvasy@gmail.com', 2, 'Google'), ('vasili.holub.family@gmail.com', 3, 'Google'),
 ('vasiliygolub@mail.ru', 4, 'Mail.ru'), ('vasiliygolub@yandex.ru', 5, 'Яндекс'), ('vasili.holub@jaydevs.dev', 6, 'JayDevs'),
 ('vasili-holub', 7, 'LinkedIn')) a(name, ord, vendor) join dict_vendor v on v.name = a.vendor;
update dict_account set comment = 'Профиль LinkedIn (адрес linkedin.com/in/vasili-holub).' where name = 'vasili-holub';

alter table dict_source add column source_type_id smallint references dict_source_type(id),
                        add column vendor_id      smallint references dict_vendor(id),
                        add column account_id     smallint references dict_account(id);

update dict_source s set
  source_type_id = (select id from dict_source_type where name = s.source_type),
  vendor_id = (select id from dict_vendor where name = case
      when s.source_kind in ('Google Drive', 'Gmail', 'Google', 'Google Takeout') then 'Google'
      when s.source_kind in ('Облако Mail.ru', 'Почта Mail.ru', 'Mail.ru') then 'Mail.ru'
      when s.source_kind in ('Почта Яндекс', 'Яндекс') then 'Яндекс'
      when s.source_kind = 'LinkedIn' then 'LinkedIn'
      when s.source_kind = 'Почта JayDevs' then 'JayDevs' end),
  account_id = (select id from dict_account where name = s.account);

do $$ begin
  if exists (select 1 from dict_source where source_type_id is null or vendor_id is null or account_id is null) then
    raise exception 'sources not mapped: %', (select string_agg(concat_ws(' / ', source_type, source_kind, account), '; ')
      from dict_source where source_type_id is null or vendor_id is null or account_id is null);
  end if;
end $$;

alter table dict_source alter column source_type_id set not null, alter column vendor_id set not null,
                        alter column account_id set not null;
alter table dict_source drop constraint if exists source_source_type_source_kind_account_key;
alter table dict_source drop column source_type, drop column source_kind, drop column account;
alter table dict_source add constraint dict_source_type_vendor_account_key unique (source_type_id, vendor_id, account_id);
alter table dict_source add constraint dict_source_account_vendor_fkey
  foreign key (account_id, vendor_id) references dict_account(id, vendor_id);

-- staging names the source by its three parts
alter table load_carrier_file rename column source_kind to vendor;

revoke insert, update on dict_source_type, dict_vendor, dict_account from archive_app;
grant select on dict_source_type, dict_vendor, dict_account to archive_app, archive_reader;

commit;

select s.id, t.name as type, v.name as vendor, a.name as account, s.method, count(c.id) as files
from dict_source s
join dict_source_type t on t.id = s.source_type_id join dict_vendor v on v.id = s.vendor_id
join dict_account a on a.id = s.account_id left join carrier_file c on c.source_id = s.id
group by s.id, t.name, v.name, a.name, t.ord, v.ord, a.ord order by t.ord, v.ord, a.ord;
