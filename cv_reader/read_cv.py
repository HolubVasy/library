"""CV reading pass: a model lists the roles in each of the owner's hand-made CVs.

Runs on the VPS as archive_app. Takes the artifacts the latest CV rules marked cv (not cv_generated), one text per
content.body_hash, so a copy is read once. For each role the model gives organization, country, position, start and
end; the pass adds career.record rows signed with its method and links each to every artifact holding that text.
Organizations and countries join their dictionaries on first use. Re-runnable: a text already read by this method
is skipped. Prints tokens and cost per text.

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
    return [{'organization': str(r['organization']).strip(), 'country': (r.get('country') or '').strip() or None,
             'position': str(r['position']).strip(), 'start': parse_date(r.get('start')),
             'end': parse_date(r.get('end'))} for r in roles]


def dict_id(db, table, name, country_id=None):
    """Id of the name in a dictionary; added on first use (checked first: a conflict would still take a number)."""
    found = db.execute(f'select id from dict.{table} where name = %s', (name,)).fetchone()
    if found:
        return found[0]
    if table == 'organization':
        return db.execute('insert into dict.organization (name, country_id) values (%s, %s) returning id',
                          (name, country_id)).fetchone()[0]
    return db.execute(f'insert into dict.{table} (name) values (%s) returning id', (name,)).fetchone()[0]


def save(db, method_id, role, artifact_ids):
    country_id = dict_id(db, 'country', role['country']) if role['country'] else None
    organization_id = dict_id(db, 'organization', role['organization'], country_id)
    record_id = db.execute('''insert into career.record (organization_id, position, start_date, end_date, method_id)
                              values (%s, %s, %s, %s, %s) returning id''',
                           (organization_id, role['position'], role['start'], role['end'], method_id)).fetchone()[0]
    for artifact_id in artifact_ids:
        db.execute('insert into career.record_artifact (record_id, artifact_id) values (%s, %s)', (record_id, artifact_id))


def read(db, ask, model, sdk_version):
    """Reads every CV text not yet read with ask(text) -> (answer, input tokens, output tokens).
    Returns [(body hash, roles, input tokens, output tokens)] of what was written in this run."""
    method_id = method(db, model, sdk_version)
    done = []
    for body_hash, body, artifact_ids in db.execute(TEXTS, {'method': method_id}).fetchall():
        answer, tokens_in, tokens_out = ask(body)
        roles = parse_roles(answer)
        with db.transaction():
            for role in roles:
                save(db, method_id, role, artifact_ids)
        done.append((body_hash, len(roles), tokens_in, tokens_out))
    return done


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


def report(done, price_in, price_out):
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
        done = read(db, ask, args.model, sdk_version)
    report(done, args.price_in, args.price_out)


if __name__ == '__main__':
    main()
