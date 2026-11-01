-- Vendor and account are linked through their own table instead of a vendor column on the account:
-- the same address can be an account at several vendors (an email used to sign in to LinkedIn, say).
-- A source may only combine a vendor and an account that are linked here.
begin;

alter table dict_source drop constraint if exists dict_source_account_vendor_fkey;

create table vendor_account (
    id          smallint generated always as identity primary key,
    vendor_id   smallint not null references dict_vendor(id),
    account_id  smallint not null references dict_account(id),
    description text not null default '',
    comment     text not null default '',
    ord         smallint,
    created_at  timestamptz not null default now(),
    unique (vendor_id, account_id)
);
comment on table vendor_account is 'Связка: аккаунт у вендора. Источник может сочетать только связанные вендор и аккаунт.';

insert into vendor_account (vendor_id, account_id, ord)
select vendor_id, id, ord from dict_account order by ord;

alter table dict_account drop constraint if exists dict_account_id_vendor_key;
alter table dict_account drop column vendor_id;

alter table dict_source add constraint dict_source_vendor_account_fkey
  foreign key (vendor_id, account_id) references vendor_account(vendor_id, account_id);

revoke insert, update on vendor_account from archive_app;
grant select on vendor_account to archive_app, archive_reader;

commit;

select v.name as vendor, a.name as account from vendor_account va
join dict_vendor v on v.id = va.vendor_id join dict_account a on a.id = va.account_id order by va.ord;
