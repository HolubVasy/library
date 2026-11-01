-- Dictionaries carry the dict_ prefix so they stand apart from entities in any table list.
-- Links keep the entity name without the prefix: source_id, carrier_type_id, tech_step_id ...
alter table if exists source             rename to dict_source;
alter table if exists tech_step          rename to dict_tech_step;
alter table if exists escalation_step    rename to dict_escalation_step;
alter table if exists platform           rename to dict_platform;
alter table if exists extraction_outcome rename to dict_extraction_outcome;
alter table if exists extraction_error   rename to dict_extraction_error;
alter table if exists carrier_type       rename to dict_carrier_type;

select table_name from information_schema.tables where table_schema = 'public' order by table_name like 'dict\_%' desc, table_name;
