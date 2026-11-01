-- A handful of made-up letters, enough for the rules to have something to decide. No real data.
-- Each artifact is named by its sha256 prefix so the tests can find it: 'a' * 64, 'b' * 64 and so on.
\set ON_ERROR_STOP on

insert into archive.method (tech_step_id, escalation_step_id, platform_id, platform_version, tool, tool_version, description)
select (select id from dict.tech_step where name = 'Детерминированная'), (select id from dict.escalation_step where name = 'Правило'),
       (select id from dict.platform where name = 'Python'), '3.12', 'extract-msg', 'test', 'Test letters';

create temp table letter (k text, sender text, folder text);
insert into letter values
  ('a', 'noreply@service.example', 'Inbox'),          -- R6 local part → notification
  ('b', 'news@substack.com', 'Inbox'),                -- R4 domain → newsletter
  ('c', 'jobalerts-noreply@linkedin.com', 'Inbox'),   -- R10 LinkedIn → job_platform
  ('d', 'vasiliygolub@mail.ru', 'Notifications'),     -- own address → nothing, even in Notifications
  ('e', 'friend@gmail.com', 'News Letters'),          -- R3 folder → newsletter
  ('f', 'hr.person@epam.com', 'Inbox'),               -- a live person on a career domain → nothing
  ('g', 'promo@textsex.ru', 'Inbox'),                 -- R2 spam domain → spam
  ('h', 'notifications@github.com', 'Notifications'); -- career domain, automated → job_platform, not notification

insert into archive.artifact (sha256, size_bytes) select repeat(k, 64), 100 from letter;

insert into archive.item (artifact_id, location, name, ext, size_bytes, source_id, item_type_id)
select a.id, format('Mail_Outlook/vasiliygolub@mail.ru/_eml/%s/%s.msg', l.folder, l.k), l.k || '.msg', 'msg', 100,
       (select min(id) from dict.source), (select id from dict.item_type where name = 'Письмо')
from letter l join archive.artifact a on a.sha256 = repeat(l.k, 64);

insert into archive.meta (artifact_id, method_id, title, data)
select a.id, (select id from archive.method where tool = 'extract-msg'), 'Letter ' || l.k, jsonb_build_object('From', 'Someone <' || l.sender || '>')
from letter l join archive.artifact a on a.sha256 = repeat(l.k, 64);

-- Documents next to the letters, and the selected text of both, for the annotation sample.
create temp table document (k text, ext text);
insert into document values ('i', 'pdf'), ('j', 'pdf'), ('k', 'docx'), ('l', 'xlsx'), ('m', 'pdf');

insert into archive.artifact (sha256, size_bytes) select repeat(k, 64), 100 from document;

insert into archive.item (artifact_id, location, name, ext, size_bytes, source_id, item_type_id)
select a.id, format('Documents/%s.%s', d.k, d.ext), d.k || '.' || d.ext, d.ext, 100,
       (select min(id) from dict.source), (select id from dict.item_type where name = 'Документ')
from document d join archive.artifact a on a.sha256 = repeat(d.k, 64);

insert into archive.content (artifact_id, method_id, outcome_id, body, selected)
select a.id, (select id from archive.method where tool = 'extract-msg'),
       (select id from dict.outcome where name = case when k = 'h' then 'Ошибка' else 'Вынуто' end),
       case when k <> 'h' then 'Made-up text of ' || k end, true   -- h: the tool failed, no text
from archive.artifact a cross join lateral (select left(a.sha256, 1) k) s
where k in ('a', 'b', 'c', 'd', 'e', 'f', 'h', 'i', 'j', 'k', 'l', 'm');   -- g has no text yet

insert into archive.artifact_tag (artifact_id, tag_id, reason)
select a.id, (select id from dict.tag where name = 'skip'), 'test'
from archive.artifact a where left(a.sha256, 1) in ('a', 'm');

-- Candidates for the CV rules: the owner's CVs, a copy with the same text, someone else's CV, a cover letter.
create temp table cv (k text, name text, ext text, body text);
insert into cv values
  ('n', 'CV Holub 2020.docx', 'docx', 'Made-up CV. Experience: Example Ltd, developer, 2018-2020.'),      -- R1
  ('o', 'CV Holub copy.pdf', 'pdf', 'Made-up CV. Experience: Example Ltd, developer, 2018-2020.'),       -- R1, same text as n
  ('p', 'Other Person CV.docx', 'docx', 'Made-up CV of someone else. Experience: Sample Inc.'),          -- not the owner
  ('q', 'Vasili_Holub_Senior_Developer.pdf', 'pdf', 'Made-up. Work experience: Example Ltd.'),          -- R2
  ('r', 'Cover_Letter_Vasili_Holub_Developer.pdf', 'pdf', 'Made-up cover letter. My experience: many'), -- never a CV
  ('t', 'CV Holub.msg', 'msg', 'Made-up letter with a CV attached. Experience inside.');                -- a letter, not a CV

insert into archive.artifact (sha256, size_bytes) select repeat(k, 64), 100 from cv;

insert into archive.item (artifact_id, location, name, ext, size_bytes, source_id, item_type_id)
select a.id, 'Documents/' || c.name, c.name, c.ext, 100, (select min(id) from dict.source),
       (select id from dict.item_type where name = case when c.ext = 'msg' then 'Письмо' else 'Документ' end)
from cv c join archive.artifact a on a.sha256 = repeat(c.k, 64);

insert into archive.content (artifact_id, method_id, outcome_id, body, body_hash, selected)
select a.id, (select id from archive.method where tool = 'extract-msg'), (select id from dict.outcome where name = 'Вынуто'),
       c.body, md5(c.body), true
from cv c join archive.artifact a on a.sha256 = repeat(c.k, 64);
