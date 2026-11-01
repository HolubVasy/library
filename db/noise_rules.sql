-- Noise rules for letters, step 1 (deterministic). Every rule is one field compared with an explicit list;
-- rules are checked in order and the first that fires gives the category. Letters from the owner's own addresses
-- are never marked; letters from career platforms are never noise: all of LinkedIn and the automated ones of the
-- other platforms are set aside as job_platform (career related, not taken into work yet).
-- Re-runnable: a letter already marked by this method is skipped.
-- Run as archive_app: psql -v code=<this file zipped, base64> -v version=<sha256 of this file, 12 chars> -f noise_rules.sql
\set ON_ERROR_STOP on

create temp table rule (n int, field text, value text, category text);
insert into rule
select 0, 'own', v, null from unnest(array[
  'vasiliygolub@mail.ru', 'holubvasy@gmail.com', 'dkhj459878@gmail.com', 'vasili.holub.family@gmail.com',
  'vasili.holub@gmail.com', 'vasiliygolub@yandex.ru', 'vasiliygolub@yandex.by']) v
union all
select 0, 'career_domain', v, null from unnest(array[
  'linkedin.com', 'github.com', 'myworkday.com', 'us.greenhouse-mail.io', 'greenhouse.io', 'smartrecruiters.com',
  'erecruiter.pl', 'stage.erecruiter.pl', 'konto.erecruiter.pl', 'successfactors.eu', 'successfactors.com',
  'ashbyhq.com', 'talent.icims.com', 'candidates.workablemail.com', 'app.bamboohr.com', 'apexsystems.com',
  'epam.com', 'exadel.com', 'dxc.com', 'jacobs.com', 'ey.com', 'primusglobal.com', 'intuition-it.com',
  'meniga.com', 'workflow.email.eu-frankfurt-1.ocs.oraclecloud.com', 'djinni.co', 'hh.ru', 'rabota.by',
  'pracuj.pl', 'justjoin.it', 'nofluffjobs.com', 'jaydevs.dev', 'jaydevs.com']) v
union all
select 1, 'folder', v, 'spam' from unnest(array['Спам', 'Spam', 'Junk', 'Нежелательная почта']) v
union all
select 2, 'domain', v, 'spam' from unnest(array[
  'email.seduce-her-tonight.ru', 'seduce-her-tonight.ru', 'textsex.ru', 'smart-dating.ru', 'seduction-guru.ru',
  'news.sexualmastery.ru', 'soblazniteli.ru', 'pickup.ru']) v
union all
select 3, 'folder', v, 'newsletter' from unnest(array['News Letters', 'Subsriptions']) v
union all
select 4, 'domain', v, 'newsletter' from unnest(array[
  'substack.com', 'maillist.codeproject.com', 'codemag.com', 'theinformation.com', 'mail.hungryminds.dev',
  'milanjovanovic.tech', 'dev.by', 'e-xecutive.ru']) v
union all
select 5, 'folder', v, 'notification' from unnest(array['Notifications']) v
union all
select 6, 'local', v, 'notification' from unnest(array[
  'noreply', 'no-reply', 'donotreply', 'do-not-reply', 'mailer-daemon', 'postmaster', 'notifications',
  'notification', 'mailout']) v
union all
select 7, 'local', v, 'advertising' from unnest(array['marketing', 'promo', 'promotions']) v
union all
select 8, 'domain', v, 'notification' from unnest(array['zomro.com', 'todoist.com', 'tpay.com', 'stripe.com',
  'google.com', 'pkobp.pl', 'altvpnnetwork.zendesk.com', 'cluely.com']) v
union all
select 9, 'domain', v, 'advertising' from unnest(array['gora4o.ru', 'tlc7.ru', 'vojevatov.ru', 'm1.email.samsung.com',
  'aprelskii-kot.ru', 'karandash.by']) v
union all
select 10, 'domain', v, 'job_platform' from unnest(array['linkedin.com']) v
union all
select 11, 'career_local', v, 'job_platform' from unnest(array[
  'noreply', 'no-reply', 'donotreply', 'notifications', 'notification', 'system', 'mail', 'noreply-zf-recruiting',
  'noreply.interview', 'auto_epam_web_notification', 'auto_epm-rdpt_mailer', 'no-reply-ciklumcareer']) v;

insert into method (tech_step_id, escalation_step_id, platform_id, platform_version, tool, tool_version, formats, description, code)
select (select id from dict.tech_step where name = 'Детерминированная'), (select id from dict.escalation_step where name = 'Правило'),
       (select id from dict.platform where name = 'PostgreSQL'), current_setting('server_version'), 'noise-rules', :'version', '{msg}',
       'Шум в письмах по явным спискам. Вход: адрес отправителя (meta, поле From письма), папки из пути item. '
       || 'Правила по порядку, срабатывает первое: '
       || (select string_agg(format('R%s %s ∈ {%s} → %s', n, field, vals, category), '; ' order by n, field)
           from (select n, field, category, string_agg(value, ', ' order by value) vals from rule where n > 0 group by 1, 2, 3) r)
       || '. Не трогает письма с собственных адресов {' || (select string_agg(value, ', ') from rule where field = 'own')
       || '}. Письма карьерных площадок {' || (select string_agg(value, ', ') from rule where field = 'career_domain')
       || '} в шум не попадают, им ставится только job_platform (правила R10, R11; career_local — адрес до @ при домене площадки). '
       || 'Пишет категорию и причину (правило и совпавшее значение). Текст не читает, ничего не угадывает.',
       decode(:'code', 'base64')
where not exists (select 1 from method where tool = 'noise-rules' and tool_version = :'version');

create temp table letter as
select a.id artifact_id, lower(substring(m.data->>'From' from '([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+)')) addr
from artifact a
join meta m on m.artifact_id = a.id
join method mm on mm.id = m.method_id and mm.tool = 'extract-msg';

with this as (select id from method where tool = 'noise-rules' and tool_version = :'version'),
hit as (
  select l.artifact_id, r.n, r.category, format('R%s %s: %s', r.n, r.field, r.value) reason
  from letter l join rule r on r.n > 0 and (
       (r.field = 'domain' and split_part(l.addr, '@', 2) = r.value)
    or (r.field = 'local' and split_part(l.addr, '@', 1) = r.value)
    or (r.field = 'career_local' and split_part(l.addr, '@', 1) = r.value
        and split_part(l.addr, '@', 2) in (select value from rule where field = 'career_domain'))
    or (r.field = 'folder' and exists (select 1 from item i where i.artifact_id = l.artifact_id
                                       and r.value = any(string_to_array(i.location, '/')))))
  where l.addr is null or (l.addr not in (select value from rule where field = 'own')
                           and (r.category = 'job_platform'
                                or split_part(l.addr, '@', 2) not in (select value from rule where field = 'career_domain')))
),
first as (select distinct on (artifact_id) * from hit order by artifact_id, n)
insert into artifact_category (artifact_id, category_id, method_id, reason)
select f.artifact_id, c.id, (select id from this), f.reason
from first f join dict.category c on c.name = f.category
on conflict do nothing;

select c.caption, count(*) from artifact_category ac join dict.category c on c.id = ac.category_id
join method m on m.id = ac.method_id and m.tool = 'noise-rules' and m.tool_version = :'version' group by 1 order by 2 desc;
