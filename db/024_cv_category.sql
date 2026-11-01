-- The owner's CVs: every version holds the career path. A verdict of the CV rules, under career_related.
begin;

insert into dict.category (name, caption, description, ord, parent_id)
select 'cv', 'Резюме', 'Резюме владельца, любая версия: из него берётся карьерный путь.', 2,
       (select id from dict.category where name = 'career_related');

commit;
