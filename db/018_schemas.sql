-- Three schemas: archive (the library), dict (dictionaries shared by archive and career), career (the working
-- extract, later). In dict the dict_ prefix is dropped: the schema already says it. Roles find tables without a
-- schema name through their search_path.
begin;

create schema archive;
create schema dict;
create schema career;

alter table artifact set schema archive;
alter table artifact_category set schema archive;
alter table content set schema archive;
alter table inbox set schema archive;
alter table item set schema archive;
alter table meta set schema archive;
alter table method set schema archive;

alter table dict_account set schema dict;
alter table dict_category set schema dict;
alter table dict_error set schema dict;
alter table dict_escalation_step set schema dict;
alter table dict_format set schema dict;
alter table dict_item_type set schema dict;
alter table dict_outcome set schema dict;
alter table dict_platform set schema dict;
alter table dict_source set schema dict;
alter table dict_source_type set schema dict;
alter table dict_tech_step set schema dict;
alter table dict_vendor set schema dict;
alter table vendor_account set schema dict;

alter table dict.dict_account rename to account;
alter table dict.dict_category rename to category;
alter table dict.dict_error rename to error;
alter table dict.dict_escalation_step rename to escalation_step;
alter table dict.dict_format rename to format;
alter table dict.dict_item_type rename to item_type;
alter table dict.dict_outcome rename to outcome;
alter table dict.dict_platform rename to platform;
alter table dict.dict_source rename to source;
alter table dict.dict_source_type rename to source_type;
alter table dict.dict_tech_step rename to tech_step;
alter table dict.dict_vendor rename to vendor;

comment on schema archive is 'Библиотека: носители, артефакты, содержание, мета, методики, категории. Пополняется, не меняется.';
comment on schema dict is 'Справочники, общие для архива и карьеры.';
comment on schema career is 'Рабочая выжимка о карьере со ссылками на артефакты архива.';

grant usage on schema archive, dict, career to archive_app, archive_reader;
alter role archive_app set search_path = archive, dict, career, public;
alter role archive_reader set search_path = archive, dict, career, public;
alter role archive set search_path = archive, dict, career, public;

commit;

select table_schema, string_agg(table_name, ', ' order by table_name)
from information_schema.tables where table_schema in ('archive', 'dict', 'career', 'public') group by 1;
