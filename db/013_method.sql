-- methodology -> method: a fixed recipe (tool, versions, parameters), not a theory of methods. Tool stays free text.
alter table methodology rename to method;
alter sequence if exists methodology_id_seq rename to method_id_seq;
do $$ declare r record; begin
  for r in select conname from pg_constraint where conrelid = 'method'::regclass and conname like 'methodology%' loop
    execute format('alter table method rename constraint %I to %I', r.conname, replace(r.conname, 'methodology', 'method'));
  end loop;
end $$;
comment on table method is 'Методика: как получена производная. Ступени лестниц, платформа, инструмент (текст), версии, описание.';
