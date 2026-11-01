-- Level 4, categorization. One tree of categories with two fixed roots: career related or not.
--   dict_category      the tree: name is the English key code and models use, caption the Russian label shown
--   artifact_category  one row per verdict of a method on an artifact, with the reason; nothing is overwritten
--   method.code        the method's code as it ran, zipped, kept in the method row itself
begin;

alter table method add column code bytea;
comment on column method.code is 'Код методики в том виде, в каком он работал, архивом zip.';

insert into dict_platform (name, description, ord) values ('PostgreSQL', 'Правила на SQL, выполняются в самой базе.', 4);

create table dict_category (like dict_tech_step including all);
alter table dict_category add column caption text not null default '';
alter table dict_category add column parent_id smallint references dict_category(id);
comment on table dict_category is 'Дерево категорий. Корни: career_related и not_career_related. name — английский ключ, caption — подпись.';

insert into dict_category (name, caption, description, ord) values
  ('career_related', 'Про карьеру', 'Всё, что вызвано карьерными действиями или о них: работа, поиск работы, обучение, проекты.', 1),
  ('not_career_related', 'Не про карьеру', 'Всё остальное: личное и шум.', 2);
insert into dict_category (name, caption, description, ord, parent_id) values
  ('personal', 'Личное', 'Личная переписка и документы, не связанные с карьерой.', 1,
   (select id from dict_category where name = 'not_career_related')),
  ('noise', 'Шум', 'Пришло не из-за карьерных действий: рассылки, уведомления сервисов, реклама, спам.', 2,
   (select id from dict_category where name = 'not_career_related'));
insert into dict_category (name, caption, description, ord, parent_id)
select v.name, v.caption, v.description, v.ord, (select id from dict_category where name = 'noise')
from (values
  ('newsletter', 'Рассылка', 'Регулярная рассылка: новости, дайджесты, статьи.', 1),
  ('notification', 'Уведомление сервиса', 'Автоматическое письмо сервиса, не связанного с карьерой.', 2),
  ('advertising', 'Реклама', 'Реклама и маркетинговые предложения.', 3),
  ('spam', 'Спам', 'Спам и сомнительные рассылки.', 4)) v(name, caption, description, ord);

create table artifact_category (
    id          bigserial primary key,
    artifact_id bigint not null references artifact(id),
    category_id smallint not null references dict_category(id),
    method_id   int not null references method(id),
    reason      text,                                -- which rule fired and on what value
    created_at  timestamptz not null default now(),
    unique (artifact_id, category_id, method_id)
);
create index artifact_category_artifact_idx on artifact_category (artifact_id);
comment on table artifact_category is 'Категории артефакта: вердикт методики с причиной. Каждый проход добавляет свои строки. Уровень 4.';

grant select on dict_category, artifact_category to archive_app, archive_reader;
grant insert on artifact_category to archive_app;
grant usage, select on all sequences in schema public to archive_app;

commit;

select c.name, c.caption, p.name parent from dict_category c left join dict_category p on p.id = c.parent_id order by c.id;
