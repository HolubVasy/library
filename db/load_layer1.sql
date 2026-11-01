-- Loads layer 1 (item) and layer 2 (artifact) from /work/layer1.csv (written by sync_cold.py).
-- Re-runnable: existing locations are skipped.
-- Each row names its source by type, vendor and account, all three from closed dictionaries: an unknown name
-- stops the load. A combination seen for the first time becomes a new source with its method and today's date
-- (completeness is filled in by hand).
truncate inbox;
\copy inbox (location, source_type, vendor, account, method, name, ext, item_type, size_bytes, modified_at, sha256) from '/work/layer1.csv' with (format csv)

do $$ begin
  if exists (select 1 from inbox l
             left join dict.source_type t on t.name = l.source_type
             left join dict.vendor v on v.name = l.vendor
             left join dict.account a on a.name = l.account
             left join dict.item_type ct on ct.name = l.item_type
             where t.id is null or v.id is null or a.id is null or ct.id is null) then
    raise exception 'names not in the dictionaries (add them first): %', (
      select string_agg(distinct concat_ws(' / ', l.source_type, l.vendor, l.account, l.item_type), '; ')
      from inbox l
      left join dict.source_type t on t.name = l.source_type
      left join dict.vendor v on v.name = l.vendor
      left join dict.account a on a.name = l.account
      left join dict.item_type ct on ct.name = l.item_type
      where t.id is null or v.id is null or a.id is null or ct.id is null);
  end if;
end $$;

create temporary table load_source as
select l.location, t.id as source_type_id, v.id as vendor_id, a.id as account_id, l.method
from inbox l
join dict.source_type t on t.name = l.source_type
join dict.vendor v on v.name = l.vendor
join dict.account a on a.name = l.account;

insert into dict.source (source_type_id, vendor_id, account_id, method, collected_on)
select distinct source_type_id, vendor_id, account_id, method, current_date from load_source
on conflict (source_type_id, vendor_id, account_id) do nothing;

-- artifacts only for carriers not yet in layer 1, so a re-sent known location never leaves an artifact without a carrier
insert into artifact (sha256, size_bytes)
select l.sha256, max(l.size_bytes) from inbox l
where not exists (select 1 from item c where c.location = l.location)
group by l.sha256
on conflict (sha256) do nothing;

insert into item (artifact_id, location, source_id, name, ext, item_type_id, size_bytes, modified_at)
select a.id, l.location, s.id, l.name, coalesce(l.ext, ''), ct.id, l.size_bytes, l.modified_at
from inbox l
join load_source ls on ls.location = l.location
join dict.source s on (s.source_type_id, s.vendor_id, s.account_id) = (ls.source_type_id, ls.vendor_id, ls.account_id)
join artifact a on a.sha256 = l.sha256
join dict.item_type ct on ct.name = l.item_type
on conflict (location) do nothing;

truncate inbox;

select 'item' as layer, count(*) from item
union all select 'artifact', count(*) from artifact;
