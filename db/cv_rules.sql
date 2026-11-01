-- CV rules, step 1 (deterministic): marks the owner's CVs among documents with extracted text. Letters are not CVs.
-- R1: a CV word in the file name, and the owner in the name or the text (a text taken out of a .doc often lacks
-- the header that holds the name). R2: the owner and a role in the file name, and work experience in the text.
-- R0: of those, the PDFs made by the owner's bot from the master CV (dated from March 2026 and named after the owner
-- and the vacancy, or named by the owner) get cv_generated instead of cv: they hold no new facts.
-- Cover letters and offers are never CVs. Identical texts are counted once in the summary (content.body_hash).
-- Re-runnable: an artifact already marked by this method is skipped.
-- Run as archive_app: psql -v code=<this file zipped, base64> -v version=<sha256 of this file, 12 chars> -f cv_rules.sql
\set ON_ERROR_STOP on
\set cv_word '(^|[^a-z])(cv|resume)([^a-z]|$)|резюме|życiorys|lebenslauf'
\set owner_name '(^|[^[:alpha:]])(holub|golub|голуб|vasili)([^[:alpha:]]|$)'
\set owner_text '(^|[^[:alpha:]])(holub|golub|голуб)([^[:alpha:]]|$)'
\set role '(developer|engineer|architect|разработчик|программист)'
\set experience 'experience|employment|опыт работы|doświadczenie'
\set not_cv 'cover|letter|offer|курсов'
\set bot_name '^[0-9]{4}-[0-9]{2}-[0-9]{2}_[^@]+@[^_]+_(CV_Vasili_Holub_|Vasili[ _]Holub[ _])'
\set bot_since '2026-03-01'
\set bot_files '(^|_)(CV_Globaldots_Platform_Engineer[.]pdf|CV_Td_Synnex_Poland_Dotnet_Developer[.]pdf|CV_Itds_Solutions_Architect[.]pdf|CV_Vasili_Holub_LTIMindtree_[.]NET_Software_Engineer[.]docx|CV_Vasili_Holub_Senior Application Support Engineer – ASP[.]NET MVC Framework with[.]docx)$'

insert into method (tech_step_id, escalation_step_id, platform_id, platform_version, tool, tool_version, formats, description, code)
select (select id from dict.tech_step where name = 'Детерминированная'), (select id from dict.escalation_step where name = 'Правило'),
       (select id from dict.platform where name = 'PostgreSQL'), current_setting('server_version'), 'cv-rules', :'version', '{}',
       'Резюме владельца по явным образцам, без учёта регистра. Вход: имена файлов (item.name), выбранный текст (content). '
       || 'R1 имя ~ ' || :'cv_word' || ' и (имя ~ ' || :'owner_name' || ' или текст ~ ' || :'owner_text' || '). '
       || 'R2 имя ~ ' || :'owner_text' || ' и имя ~ ' || :'role' || ' и текст ~ ' || :'experience' || '. '
       || 'R0 из них PDF с именем ~ ' || :'bot_name' || ' и датой в имени от ' || :'bot_since' || ', или с именем ~ '
       || :'bot_files' || ' (названы владельцем): резюме от бота, категория cv_generated вместо cv. '
       || 'Никогда: письма (.msg) и имя ~ ' || :'not_cv' || '. Пишет категорию и сработавшее правило.',
       decode(:'code', 'base64')
where not exists (select 1 from method where tool = 'cv-rules' and tool_version = :'version');

create temp table doc as
select i.artifact_id, string_agg(i.name, ' | ') names, c.body,
       bool_or((lower(i.ext) = 'pdf' and i.name ~ :'bot_name' and left(i.name, 10) >= :'bot_since')
               or i.name ~ :'bot_files') by_bot
from item i join content c on c.artifact_id = i.artifact_id and c.selected and c.body is not null
group by i.artifact_id, c.body
having not bool_or(lower(i.ext) = 'msg') and not bool_or(i.name ~* :'not_cv');

with this as (select id from method where tool = 'cv-rules' and tool_version = :'version'),
hit as (
  select artifact_id, by_bot, case
           when names ~* :'cv_word' and (names ~* :'owner_name' or body ~* :'owner_text') then 'R1 CV word in the name, owner'
           when names ~* :'owner_text' and names ~* :'role' and body ~* :'experience' then 'R2 owner and role in the name, experience'
         end reason
  from doc
)
insert into artifact_category (artifact_id, category_id, method_id, reason)
select h.artifact_id, (select id from dict.category where name = case when h.by_bot then 'cv_generated' else 'cv' end),
       (select id from this), case when h.by_bot then 'R0 made by the bot; ' else '' end || h.reason
from hit h where h.reason is not null
  and not exists (select 1 from artifact_category ac where ac.artifact_id = h.artifact_id and ac.method_id = (select id from this));

select g.name, count(*) cvs, count(distinct c.body_hash) texts
from artifact_category ac join method m on m.id = ac.method_id and m.tool = 'cv-rules' and m.tool_version = :'version'
join dict.category g on g.id = ac.category_id
join content c on c.artifact_id = ac.artifact_id and c.selected
group by g.name order by g.name;
