"""Annotation pass: a model writes in two or three sentences what a document is about.

Runs on the VPS as archive_app. Takes a fixed sample: artifacts with selected extracted text and without an active
skip tag, half letters and half documents, documents spread over their extensions, each group in the order of
md5 of sha256. Each half counts what the method already wrote, so the method never holds more than the sample. Writes only archive.annotation, every row signed with its
method: model family and version, prompt version, code version, the code itself zipped.
Re-runnable: an artifact already annotated by this method is skipped. Prints tokens and cost per document.

Usage: annotate.py --model claude-haiku-5-5 --price-in USD --price-out USD [--size 50]
       (prices per million input and output tokens)
"""
import argparse, hashlib, io, os, re, zipfile

import psycopg

PROMPT_VERSION = '1'
PROMPT = ('Ты читаешь документ из личного архива: письмо, резюме, договор, справку или другой файл. '
          'Напиши по-русски два или три предложения о том, что это за документ и о чём он. '
          'Только эти предложения, без вступления, списков и оценок. Не добавляй того, чего нет в тексте.')
MAX_CHARS = 20_000                 # the start of a long text is enough to say what it is about
MAX_TOKENS = 2000                  # the model thinks first, and its thinking counts against this limit
SCRIPT = os.path.abspath(__file__)
SCRIPT_VERSION = hashlib.sha256(open(SCRIPT, 'rb').read()).hexdigest()[:12]

SAMPLE = '''
with pool as (
  select a.id, a.sha256, c.body, min(lower(i.ext)) ext, bool_or(lower(i.ext) = 'msg') is_letter
  from archive.artifact a
  join archive.content c on c.artifact_id = a.id and c.selected and c.body is not null
  join archive.item i on i.artifact_id = a.id
  where not exists (select 1 from archive.artifact_tag t join dict.tag g on g.id = t.tag_id
                    where t.artifact_id = a.id and g.name = 'skip' and t.removed_at is null)
  group by a.id, a.sha256, c.body
),
done as (
  select d.is_letter, count(*) n from (
    select bool_or(lower(i.ext) = 'msg') is_letter from archive.annotation x
    join archive.item i on i.artifact_id = x.artifact_id
    where x.method_id = %(method)s group by x.artifact_id) d
  group by d.is_letter
),
spread as (
  select *, row_number() over (partition by is_letter, ext order by md5(sha256)) turn from pool p
  where not exists (select 1 from archive.annotation x where x.artifact_id = p.id and x.method_id = %(method)s)
),
ranked as (
  select *, row_number() over (partition by is_letter order by turn, md5(sha256)) n from spread
)
select r.id, r.body from ranked r left join done d on d.is_letter = r.is_letter
where r.n <= case when r.is_letter then %(letters)s else %(documents)s end - coalesce(d.n, 0)
order by r.is_letter, r.n
'''


def zipped_code():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(SCRIPT, os.path.basename(SCRIPT))
    return buf.getvalue()


def method(db, model, sdk_version):
    """Id of the method for this model, prompt and code; registered on first use."""
    keys = ('Недетерминированная', 'Низкий уровень', 'Anthropic API', sdk_version,
            re.sub(r'[-\d.]+$', '', model), model,
            f'Аннотация, промпт {PROMPT_VERSION}, код {SCRIPT_VERSION}, до {MAX_CHARS} знаков текста: {PROMPT}')
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


def sample(db, method_id, size):
    """(artifact id, text) of the sample not yet annotated by the method."""
    return db.execute(SAMPLE, {'letters': size // 2, 'documents': size - size // 2, 'method': method_id}).fetchall()


def save(db, artifact_id, method_id, text):
    db.execute('''insert into archive.annotation (artifact_id, method_id, text, selected)
                  values (%s, %s, %s, not exists (select 1 from archive.annotation
                                                  where artifact_id = %s and selected))''',
               (artifact_id, method_id, text, artifact_id))


def annotate(db, ask, model, sdk_version, size):
    """Annotates the sample with ask(text) -> (annotation, input tokens, output tokens).
    Returns [(artifact id, input tokens, output tokens)] of what was written in this run."""
    method_id = method(db, model, sdk_version)
    done = []
    for artifact_id, body in sample(db, method_id, size):
        text, tokens_in, tokens_out = ask(body[:MAX_CHARS])
        if not text.strip():
            raise ValueError(f'artifact {artifact_id}: the model returned no text')
        save(db, artifact_id, method_id, text.strip())
        done.append((artifact_id, tokens_in, tokens_out))
    return done


def claude(model):
    """ask() over the Anthropic API and the SDK version; the key comes from ANTHROPIC_API_KEY."""
    import anthropic
    client = anthropic.Anthropic(timeout=60)

    def ask(text):
        r = client.messages.create(model=model, max_tokens=MAX_TOKENS, system=PROMPT,
                                   messages=[{'role': 'user', 'content': text}])
        if r.stop_reason != 'end_turn':
            raise RuntimeError(f'the model stopped with {r.stop_reason}, the annotation would be cut')
        answer = ''.join(b.text for b in r.content if b.type == 'text')
        return answer, r.usage.input_tokens, r.usage.output_tokens
    return ask, anthropic.__version__


def report(done, price_in, price_out):
    total = 0.0
    for artifact_id, tokens_in, tokens_out in done:
        cost = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
        total += cost
        print(f'annotation: artifact {artifact_id}, tokens {tokens_in} in, {tokens_out} out, ${cost:.5f}', flush=True)
    per_doc = total / len(done) if done else 0.0
    print(f'annotation: {len(done)} written, ${total:.4f} in total, ${per_doc:.5f} per document', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--price-in', type=float, required=True)
    ap.add_argument('--price-out', type=float, required=True)
    ap.add_argument('--size', type=int, default=50)
    args = ap.parse_args()
    ask, sdk_version = claude(args.model)
    with psycopg.connect(autocommit=True) as db:
        done = annotate(db, ask, args.model, sdk_version, args.size)
    report(done, args.price_in, args.price_out)


if __name__ == '__main__':
    main()
