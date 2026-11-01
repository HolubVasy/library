-- Automated letters of job platforms: career related, but set aside for now (not taken into work yet).
insert into dict_category (name, caption, description, ord, parent_id)
values ('job_platform', 'Карьерная площадка (отложено)',
        'Автоматические письма карьерных площадок и все письма LinkedIn: про карьеру, но пока не берём в работу.', 1,
        (select id from dict_category where name = 'career_related'));
