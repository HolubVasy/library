-- dict.format ran out of smallint ids: "on conflict do nothing" took a sequence number on every artifact.
-- The extractor now checks before inserting; the id widens to integer so the burnt range does not matter.
-- The 290 "not in the store" rows were not results about artifacts but files not uploaded yet: removed,
-- so those artifacts are read again once they are in the store.
begin;
alter table archive.artifact alter column format_id type integer;
alter table dict.format alter column id type integer;
alter table dict.format alter column id set maxvalue 2147483647;
delete from archive.content c using archive.method m
where m.id = c.method_id and m.tool = 'archive-extractor' and c.error_message = 'not in the store';
commit;
select max(id), pg_get_serial_sequence('dict.format', 'id') from dict.format;
