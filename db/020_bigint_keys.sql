-- Every key is bigint: ids and references in all schemas, and the sequences behind them. No more running out.
begin;
do $$
declare r record;
begin
  for r in select table_schema, table_name, column_name from information_schema.columns
           where table_schema in ('archive', 'dict', 'career') and (column_name = 'id' or column_name like '%\_id')
             and data_type <> 'bigint'
  loop
    execute format('alter table %I.%I alter column %I type bigint', r.table_schema, r.table_name, r.column_name);
  end loop;
  for r in select table_schema, table_name, column_name from information_schema.columns
           where table_schema in ('archive', 'dict', 'career') and is_identity = 'YES'
  loop
    execute format('alter table %I.%I alter column %I set maxvalue 9223372036854775807', r.table_schema, r.table_name, r.column_name);
  end loop;
  for r in select s.oid::regclass seq from pg_class s join pg_namespace n on n.oid = s.relnamespace
           where s.relkind = 'S' and n.nspname in ('archive', 'dict', 'career')
             and not exists (select 1 from pg_depend d where d.objid = s.oid and d.deptype = 'i')
  loop
    execute format('alter sequence %s as bigint maxvalue 9223372036854775807', r.seq);
  end loop;
end $$;
commit;

select table_schema, data_type, count(*) from information_schema.columns
where table_schema in ('archive', 'dict', 'career') and (column_name = 'id' or column_name like '%\_id') group by 1, 2;
select seqrelid::regclass, seqtypid::regtype, seqmax from pg_sequence order by 1;
