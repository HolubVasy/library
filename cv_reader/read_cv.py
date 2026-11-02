"""CV reading pass: a model lists the roles in each of the owner's hand-made CVs.

Runs on the VPS as archive_app. Takes the artifacts the latest CV rules marked cv (not cv_generated), one text per
content.body_hash, so a copy is read once. For each role the model gives organization, country, position, start and
end; the pass adds career.record rows signed with its method and links each to every artifact holding that text.
Organizations and countries join their dictionaries on first use. Re-runnable: a text already read by this method
is not read again, and a copy of it that reached the archive later is linked to its records without the model.
Prints tokens and cost per text and the number of copies linked.

Usage: read_cv.py --model claude-sonnet-5-5 --price-in USD --price-out USD   (prices per million tokens)
"""
import argparse, datetime, hashlib, io, json, os, re, zipfile

import psycopg

PROMPT_VERSION = '1'
PROMPT = ('You read a CV. List every job in it as a JSON array, one object per role, in the order of the CV: '
          '{"organization": the employer as written, "country": the country in English or null, '
          '"position": the title as written, "start": "YYYY-MM-DD", "YYYY-MM" or "YYYY", as precise as the CV gives, '
          '"end": the same, or null when the job is current}. Education, courses and projects without an employer '
          'are not jobs. Copy names and titles exactly, do not translate, merge or guess. '
          'Return only the JSON array.')
MAX_TOKENS = 16_000                # the model thinks first, and its thinking counts against this limit
SCRIPT = os.path.abspath(__file__)
SCRIPT_VERSION = hashlib.sha256(open(SCRIPT, 'rb').read()).hexdigest()[:12]

TEXTS = '''
with rules as (select max(id) id from archive.method where tool = 'cv-rules'),
cv as (
  select c.body_hash, c.body, ac.artifact_id from archive.artifact_category ac
  join dict.category g on g.id = ac.category_id and g.name = 'cv'
  join archive.content c on c.artifact_id = ac.artifact_id and c.selected and c.body_hash is not null
  where ac.method_id = (select id from rules)
)
select cv.body_hash, min(cv.body), array_agg(cv.artifact_id order by cv.artifact_id) from cv
where not exists (select 1 from career.record r join career.record_artifact ra on ra.record_id = r.id
                  join cv done on done.artifact_id = ra.artifact_id
                  where r.method_id = %(method)s and done.body_hash = cv.body_hash)
group by cv.body_hash order by min(cv.artifact_id)
'''

# A text already read has records of this method linked to some of its copies; every copy not yet linked to such a
# record gets the link. Only additions: no record is written again and no model is asked.
LATER_COPIES = '''
with rules as (select max(id) id from archive.method where tool = 'cv-rules'),
cv as (
  select c.body_hash, ac.artifact_id from archive.artifact_category ac
  join dict.category g on g.id = ac.category_id and g.name = 'cv'
  join archive.content c on c.artifact_id = ac.artifact_id and c.selected and c.body_hash is not null
  where ac.method_id = (select id from rules)
),
read_text as (
  select distinct cv.body_hash, ra.record_id from career.record r
  join career.record_artifact ra on ra.record_id = r.id
  join cv on cv.artifact_id = ra.artifact_id
  where r.method_id = %(method)s
)
insert into career.record_artifact (record_id, artifact_id)
select rt.record_id, cv.artifact_id from read_text rt join cv on cv.body_hash = rt.body_hash
where not exists (select 1 from career.record_artifact x where x.record_id = rt.record_id and x.artifact_id = cv.artifact_id)
returning artifact_id
'''


def zipped_code():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(SCRIPT, os.path.basename(SCRIPT))
    return buf.getvalue()


def method(db, model, sdk_version):
    """Id of the method for this model, prompt and code; registered on first use."""
    keys = ('Недетерминированная', 'Средний уровень', 'Anthropic API', sdk_version,
            re.sub(r'[-\d.]+$', '', model), model,
            f'Должности из резюме, промпт {PROMPT_VERSION}, код {SCRIPT_VERSION}: {PROMPT}')
    sql = '''select m.id from archive.method m
             where m.tech_step_id = (select id from dict.tech_step where name = %s)
               and m.escalation_step_id = (select id from dict.escalation_step where name = %s)
               and m.platform_id = (select id from dict.platform where name = %s)
               and m.platform_version = %s and m.tool = %s and m.tool_version = %s and m.description = %s'''
    found = db.execute(sql, keys).fetchone()
    if found:
        return found[0]
    return db.execute('''insert into archive.method (tech_step_id, escalation_step_id, platform_id, platform_version,
                                                     tool, tool_version, description, code)
                         select (select id from dict.tech_step where name = %s),
                                (select id from dict.escalation_step where name = %s),
                                (select id from dict.platform where name = %s), %s, %s, %s, %s, %s
                         returning id''', (*keys, zipped_code())).fetchone()[0]


def parse_date(value):
    """A date from 'YYYY-MM-DD', 'YYYY-MM' or 'YYYY'; the missing parts become the first day."""
    if value is None:
        return None
    m = re.fullmatch(r'(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?', str(value).strip())
    if not m:
        raise ValueError(f'not a date: {value!r}')
    return datetime.date(int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1))


def parse_roles(answer):
    """The roles of the model's JSON answer; raises on anything that is not a non-empty list of roles."""
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', answer.strip())
    roles = json.loads(text)
    if not isinstance(roles, list) or not roles:
        raise ValueError(f'expected a non-empty JSON array of roles, got: {answer[:200]!r}')
    return [{'organization': required(r, 'organization'), 'country': (r.get('country') or '').strip() or None,
             'position': required(r, 'position'), 'start': parse_date(r.get('start')),
             'end': parse_date(r.get('end'))} for r in roles]


def required(role, key):
    value = role.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'a role without {key}: {role!r}')
    return value.strip()


def country_id(db, name):
    """Id of the country; added on first use (checked first: a conflict would still take a number)."""
    found = db.execute('select id from dict.country where name = %s', (name,)).fetchone()
    return found[0] if found else \
        db.execute('insert into dict.country (name) values (%s) returning id', (name,)).fetchone()[0]


def organization_id(db, name, country):
    """Id of the organization with this name in this country; added on first use."""
    found = db.execute('select id from dict.organization where name = %s and country_id is not distinct from %s',
                       (name, country)).fetchone()
    return found[0] if found else \
        db.execute('insert into dict.organization (name, country_id) values (%s, %s) returning id',
                   (name, country)).fetchone()[0]


def save(db, method_id, role, artifact_ids):
    country = country_id(db, role['country']) if role['country'] else None
    organization = organization_id(db, role['organization'], country)
    record_id = db.execute('''insert into career.record (organization_id, position, start_date, end_date, method_id)
                              values (%s, %s, %s, %s, %s) returning id''',
                           (organization, role['position'], role['start'], role['end'], method_id)).fetchone()[0]
    for artifact_id in artifact_ids:
        db.execute('insert into career.record_artifact (record_id, artifact_id) values (%s, %s)', (record_id, artifact_id))


def read(db, ask, model, sdk_version):
    """Links the later copies of texts already read, then reads every CV text not yet read with
    ask(text) -> (answer, input tokens, output tokens).
    Returns ([(body hash, roles, input tokens, output tokens)] of what the model read in this run,
    the number of copies linked without the model)."""
    method_id = method(db, model, sdk_version)
    with db.transaction():
        linked = len({row[0] for row in db.execute(LATER_COPIES, {'method': method_id}).fetchall()})
    done = []
    for body_hash, body, artifact_ids in db.execute(TEXTS, {'method': method_id}).fetchall():
        answer, tokens_in, tokens_out = ask(body)
        roles = parse_roles(answer)
        with db.transaction():
            for role in roles:
                save(db, method_id, role, artifact_ids)
        done.append((body_hash, len(roles), tokens_in, tokens_out))
    return done, linked


def claude(model):
    """ask() over the Anthropic API and the SDK version; the key comes from ANTHROPIC_API_KEY."""
    import anthropic
    client = anthropic.Anthropic(timeout=300)

    def ask(text):
        r = client.messages.create(model=model, max_tokens=MAX_TOKENS, system=PROMPT,
                                   messages=[{'role': 'user', 'content': text}])
        if r.stop_reason != 'end_turn':
            raise RuntimeError(f'the model stopped with {r.stop_reason}, the answer would be cut')
        answer = ''.join(b.text for b in r.content if b.type == 'text')
        return answer, r.usage.input_tokens, r.usage.output_tokens
    return ask, anthropic.__version__


def report(done, linked, price_in, price_out):
    print(f'cv: {linked} later copies linked to texts already read, without the model', flush=True)
    total = 0.0
    for body_hash, roles, tokens_in, tokens_out in done:
        cost = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
        total += cost
        print(f'cv: text {body_hash[:12]}, {roles} roles, tokens {tokens_in} in, {tokens_out} out, ${cost:.4f}',
              flush=True)
    per_text = total / len(done) if done else 0.0
    print(f'cv: {len(done)} texts read, ${total:.4f} in total, ${per_text:.4f} per text', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--price-in', type=float, required=True)
    ap.add_argument('--price-out', type=float, required=True)
    args = ap.parse_args()
    ask, sdk_version = claude(args.model)
    with psycopg.connect(autocommit=True) as db:
        done, linked = read(db, ask, args.model, sdk_version)
    report(done, linked, args.price_in, args.price_out)


if __name__ == '__main__':
    main()
