-- CVs made by the owner's bot from the master CV: a verdict of the CV rules, kept apart from the hand-made ones.
begin;

insert into dict.category (name, caption, description, ord, parent_id)
select 'cv_generated', 'Резюме от бота', 'Резюме, собранное ботом владельца из мастер-резюме под вакансию: новых фактов нет.', 3,
       (select id from dict.category where name = 'career_related');

commit;
