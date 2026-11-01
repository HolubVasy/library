-- The staging table for the layer 1-2 load is the inbox: incoming, not yet checked against the dictionaries.
alter table load_item rename to inbox;
comment on table inbox is 'Входящие: строки досинхронизации до проверки по справочникам; после загрузки пусто.';
