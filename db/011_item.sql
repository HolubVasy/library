-- Naming rule: one word = entity, two words = link table, dict_ = dictionary, load_ = staging.
-- The carrier (level 1) becomes item, the IFLA LRM term for one copy of a thing; carrier also read like career.
begin;

alter table carrier_file rename to item;
alter table item rename column carrier_type_id to item_type_id;
alter table dict_carrier_type rename to dict_item_type;
alter table load_carrier_file rename to load_item;
alter table load_item rename column carrier_type to item_type;
alter sequence if exists carrier_file_id_seq rename to item_id_seq;

-- constraint and index names follow the table
do $$ declare r record; begin
  for r in select conname from pg_constraint where conrelid = 'item'::regclass and conname like 'carrier\_file%' loop
    execute format('alter table item rename constraint %I to %I', r.conname,
                   replace(replace(r.conname, 'carrier_file', 'item'), 'carrier_type', 'item_type'));
  end loop;
  for r in select indexname from pg_indexes where tablename = 'item' and indexname like 'carrier\_file%' loop
    execute format('alter index %I rename to %I', r.indexname,
                   replace(replace(r.indexname, 'carrier_file', 'item'), 'carrier_type', 'item_type'));
  end loop;
end $$;

comment on table item is 'Носитель (уровень 1): экземпляр предмета в конкретном месте, с источником. IFLA LRM: Item.';
comment on table artifact is 'Предмет (уровень 2): уникальное содержимое по SHA-256. IFLA LRM: Manifestation.';

commit;

select table_name from information_schema.tables where table_schema = 'public' order by 1;
select indexname from pg_indexes where tablename = 'item' order by 1;
