-- job_platform is a plain fact, not a decision: the letter came from a job platform. What to work on first is
-- decided when choosing what to look at, not written into the category.
update dict_category
set caption = 'Карьерная площадка',
    description = 'Письмо пришло с карьерной площадки: все письма LinkedIn и автоматические письма остальных площадок.'
where name = 'job_platform';
