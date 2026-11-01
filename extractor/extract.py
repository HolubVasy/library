"""Level 3 extractor: step 1 of the technology ladder, deterministic tools only.

Runs on the VPS inside archive_net as archive_app. Artifacts are copied decrypted from the cold store into /work,
a RAM-only area, read, and removed. Passes:
  format   artifact.format_id from Siegfried (PRONOM), new formats join dict.format
  meta     properties written inside the file, by exiftool (letters get theirs from extract-msg in the content pass)
  content  text as taken out, by kind: letters, documents, text, images, other (no step 1 method: an error row)
  rtf      letters whose text lost Cyrillic ('????'), read again from their RTF body
Every meta and content row is signed with its method; methods are registered with the real tool versions.
Re-runnable: a pass takes only artifacts that have no result yet.

Usage: extract.py format|meta|content|rtf [--kind letters|documents|text|images|other] [--limit N] [--shard K/N]
"""
import argparse, datetime, email.header, email.utils, glob, hashlib, html, json, os, re, shutil, subprocess, sys

import extract_msg
import psycopg
from charset_normalizer import from_bytes
from psycopg.types.json import Jsonb

from readers import html_text, rtf_text

WORK = '/work'
MAX_SIZE = 1_500_000_000          # larger files do not fit the RAM-only work area: reported, not read
BATCH_BYTES = 1_000_000_000
SF = ['sf', '-home', '/opt/siegfried']
SCRIPT_VERSION = hashlib.sha256(open(__file__, 'rb').read()).hexdigest()[:12]

WRITER = {'doc', 'docx', 'rtf', 'odt', 'wps'}
CALC = {'xls', 'xlsx', 'ods'}
SLIDES = {'ppt', 'pptx', 'odp', 'pps', 'ppsx'}
KINDS = {
    'letters': {'msg'},
    'documents': {'pdf'} | WRITER | CALC | SLIDES,
    'text': {'txt', 'csv', 'htm', 'html', 'xml', 'json', 'md', 'log', 'eml'},
    'images': {'jpg', 'jpeg', 'png', 'tif', 'tiff', 'bmp', 'gif', 'webp'},
}
KNOWN = set().union(*KINDS.values())

# properties not kept in meta: the copy on disk, tool bookkeeping, camera internals, location, embedded pictures
DROP_GROUPS = {'File', 'System', 'ExifTool', 'MakerNotes', 'Composite'}
TITLE_KEYS = ['XMP:Title', 'PDF:Title', 'XML:Title', 'FlashPix:Title', 'QuickTime:Title', 'RIFF:Title', 'ID3:Title']
DATE_KEYS = ['EXIF:DateTimeOriginal', 'XMP:DateTimeOriginal', 'XML:CreateDate', 'PDF:CreateDate', 'XMP:CreateDate',
             'FlashPix:CreateDate', 'EXIF:CreateDate', 'QuickTime:CreateDate']

ap = argparse.ArgumentParser()
ap.add_argument('pass_', choices=['format', 'meta', 'content', 'rtf'])
ap.add_argument('--kind', choices=list(KINDS) + ['other'])
ap.add_argument('--limit', type=int, default=0)
ap.add_argument('--shard', default='0/1')
args = ap.parse_args()
SHARD_K, SHARD_N = map(int, args.shard.split('/'))
SHARD = f'and a.id %% {SHARD_N} = {SHARD_K}'   # %% because the queries also carry parameters

db = psycopg.connect(autocommit=True)


def q(sql, *params):
    return db.execute(sql, params).fetchall()


def one(sql, *params):
    row = db.execute(sql, params).fetchone()
    return row[0] if row else None


def dict_id(table, name):
    found = one(f'select id from {table} where name = %s', name)
    if found is None:
        sys.exit(f'{name} is missing in {table}')
    return found


OUTCOME = {n: dict_id('dict.outcome', n) for n in ('Вынуто', 'Пусто', 'Ошибка')}
ERROR = {n: dict_id('dict.error', n) for n in
         ('Формат не поддерживается', 'Файл повреждён', 'Защищён паролем', 'Превышено время', 'Сбой инструмента')}


def run(cmd, timeout=180):
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def version(cmd, pattern):
    r = run(cmd, timeout=60)
    m = re.search(pattern, (r.stdout + r.stderr).decode('utf-8', 'replace'))
    return m.group(1) if m else '?'


def method(tool, tool_version, formats, description):
    """Id of the method with exactly these tool, versions and description; registered on first use."""
    keys = (dict_id('dict.tech_step', 'Детерминированная'), dict_id('dict.escalation_step', 'Правило'),
            dict_id('dict.platform', 'Python'), '.'.join(map(str, sys.version_info[:3])), tool, tool_version, description)
    found = one('select id from method where tech_step_id = %s and escalation_step_id = %s and platform_id = %s '
                'and platform_version = %s and tool = %s and tool_version = %s and description = %s', *keys)
    return found or one('insert into method (tech_step_id, escalation_step_id, platform_id, platform_version, tool, '
                        'tool_version, description, formats) values (%s, %s, %s, %s, %s, %s, %s, %s) returning id',
                        *keys, sorted(formats))


def batches(sql, *params):
    """Yields rows (id, sha256, size, ...) of the query page by page, each page small enough for /work."""
    last, done = 0, 0
    while True:
        rows = q(sql, last, *params, 500)
        if not rows:
            return
        chunk, total = [], 0
        for r in rows:
            if chunk and total + r[2] > BATCH_BYTES:
                break
            chunk.append(r)
            total += r[2]
        if args.limit:
            chunk = chunk[:max(0, args.limit - done)]
            if not chunk:
                return
        last = chunk[-1][0]
        done += len(chunk)
        yield chunk


def fetch(shas):
    """Copies the artifacts decrypted into /work/batch/<aa>/<sha>; returns {sha: path} of those that arrived."""
    batch = os.path.join(WORK, 'batch')
    shutil.rmtree(batch, ignore_errors=True)
    os.makedirs(batch)
    listing = os.path.join(WORK, 'list.txt')
    with open(listing, 'w') as fh:
        fh.write(''.join(f'{s[:2]}/{s}\n' for s in shas))
    run(['rclone', 'copy', 'cold:objects', batch, '--files-from', listing, '--transfers', '4', '-q'], timeout=7200)
    return {s: p for s in shas if os.path.exists(p := os.path.join(batch, s[:2], s))}


def parse_date(value):
    m = re.search(r'(\d{4})[:-](\d{2})[:-](\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?(Z|[+-]\d{2}:?\d{2})?', str(value))
    if not m or m.group(1) == '0000':
        return None
    y, mo, d, h, mi, s, tz = m.groups()
    tzinfo = datetime.timezone.utc
    if tz and tz != 'Z':
        sign = 1 if tz[0] == '+' else -1
        tzinfo = datetime.timezone(sign * datetime.timedelta(hours=int(tz[1:3]), minutes=int(tz[-2:])))
    try:
        return datetime.datetime(int(y), int(mo), int(d), int(h), int(mi), int(s or 0), tzinfo=tzinfo)
    except ValueError:
        return None


def error_kind(message):
    m = message.lower()
    if 'password' in m or 'encrypt' in m:
        return 'Защищён паролем'
    if any(w in m for w in ('damaged', 'corrupt', 'xref', 'syntax error', 'not a valid', 'trailer', 'bad zip',
                            'truncated', 'invalid')):
        return 'Файл повреждён'
    return 'Сбой инструмента'


def save_content(artifact_id, method_id, body=None, error=None, message=None):
    body = (body or '').replace('\x00', '')
    outcome = 'Ошибка' if error else 'Вынуто' if body.strip() else 'Пусто'
    db.execute('insert into content (artifact_id, method_id, outcome_id, error_id, error_message, body, body_hash, selected) '
               'values (%s, %s, %s, %s, %s, %s, %s, not exists (select 1 from content where artifact_id = %s and selected)) '
               'on conflict (artifact_id, method_id) do nothing',
               (artifact_id, method_id, OUTCOME[outcome], ERROR.get(error), (message or '')[:2000] or None,
                body if body.strip() else None, hashlib.sha256(body.encode()).hexdigest() if body.strip() else None,
                artifact_id))
    return outcome


def save_meta(artifact_id, method_id, title, dated_at, data):
    db.execute('insert into meta (artifact_id, method_id, title, dated_at, data) values (%s, %s, %s, %s, %s) '
               'on conflict (artifact_id, method_id) do nothing',
               (artifact_id, method_id, (title or '').replace('\x00', '') or None, dated_at, Jsonb(data)))


# --- format ------------------------------------------------------------------------------------------------------
def pass_format():
    sf_version = version(SF + ['-version'], r'siegfried (\S+)')
    signature = version(SF + ['-version'], r'\.sig \(([^)]+)\)')
    note = f'Siegfried {sf_version}, сигнатуры {signature}'
    sql = f'''select a.id, a.sha256, a.size_bytes from artifact a
              where a.id > %s and a.format_id is null and a.size_bytes <= {MAX_SIZE} {SHARD} order by a.id limit %s'''
    for chunk in batches(sql):
        files = fetch([r[1] for r in chunk])
        out = run(SF + ['-json', '-multi', '8', os.path.join(WORK, 'batch')], timeout=3600).stdout
        found = {os.path.basename(f['filename']): f['matches'][0] for f in json.loads(out).get('files', []) if f.get('matches')}
        for artifact_id, sha, _ in chunk:
            m = found.get(sha)
            if not m:
                continue
            puid = m.get('id') or 'UNKNOWN'
            desc = ', '.join(x for x in (m.get('format'), m.get('version')) if x) or 'Не опознан'
            # checked first: "on conflict do nothing" would still take a number from the id sequence on every call
            db.execute('insert into dict.format (name, description, mime, comment) select %s, %s, %s, %s '
                       'where not exists (select 1 from dict.format where name = %s)',
                       (puid, desc, m.get('mime') or '', note, puid))
            db.execute('update artifact set format_id = (select id from dict.format where name = %s) where id = %s',
                       (puid, artifact_id))
        print(f'format: {len(files)} read, up to artifact {chunk[-1][0]}', flush=True)


# --- meta --------------------------------------------------------------------------------------------------------
def pass_meta():
    method_id = method('exiftool', version(['exiftool', '-ver'], r'(\S+)'), KNOWN - {'msg'},
                       'Свойства, записанные внутри файла; без координат, встроенных картинок, служебного про копию '
                       'и заметок камер. Заголовок и дата документа — из первых найденных ключей')
    sql = f'''select a.id, a.sha256, a.size_bytes from artifact a
              where a.id > %s and a.size_bytes <= {MAX_SIZE} {SHARD}
                and not exists (select 1 from meta m where m.artifact_id = a.id and m.method_id = {method_id})
                and not exists (select 1 from item i where i.artifact_id = a.id and lower(i.ext) = 'msg')
              order by a.id limit %s'''
    for chunk in batches(sql):
        files = fetch([r[1] for r in chunk])
        out = run(['exiftool', '-j', '-G', '-r', '-ext', '*', '-charset', 'filename=utf8', '-api', 'largefilesupport=1',
                   os.path.join(WORK, 'batch')], timeout=3600).stdout
        tags = {os.path.basename(t.pop('SourceFile', '')): t for t in json.loads(out or b'[]')}
        for artifact_id, sha, _ in chunk:
            if sha not in files:
                continue
            data = {k: v for k, v in tags.get(sha, {}).items()
                    if k.split(':')[0] not in DROP_GROUPS and 'GPS' not in k
                    and not (isinstance(v, str) and v.startswith('(Binary data'))}
            title = next((str(data[k]) for k in TITLE_KEYS if str(data.get(k, '')).strip()), None)
            dated = next((d for k in DATE_KEYS if (d := parse_date(data.get(k, '')))), None)
            save_meta(artifact_id, method_id, title, dated, data)
        print(f'meta: {len(files)} read, up to artifact {chunk[-1][0]}', flush=True)


# --- content -----------------------------------------------------------------------------------------------------
def tool_text(cmd, timeout=180):
    """Runs a tool that prints text; returns (text, error, message)."""
    try:
        r = run(cmd, timeout)
    except subprocess.TimeoutExpired:
        return None, 'Превышено время', f'{cmd[0]}: no result in {timeout} s'
    err = r.stderr.decode('utf-8', 'replace').strip()
    if r.returncode:
        return None, error_kind(err), err or f'{cmd[0]} exit {r.returncode}'
    return r.stdout.decode('utf-8', 'replace'), None, None


def office(path, ext, target):
    """LibreOffice conversion into /work/out; returns (paths of the results, error, message)."""
    out = os.path.join(WORK, 'out')
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    src = os.path.join(WORK, 'in.' + ext)   # the filter is chosen by extension
    shutil.copyfile(path, src)
    try:
        r = run(['soffice', '--headless', f'-env:UserInstallation=file://{WORK}/lo{SHARD_K}', '--convert-to', target,
                 '--outdir', out, src], timeout=240)
    except subprocess.TimeoutExpired:
        return [], 'Превышено время', 'soffice: no result in 240 s'
    finally:
        os.remove(src)
    results = sorted(glob.glob(os.path.join(out, '*')))
    if not results:
        msg = (r.stderr + r.stdout).decode('utf-8', 'replace').strip()
        return [], error_kind(msg), msg or 'soffice produced no file'
    return results, None, None


def header(m, name):
    """A transport header decoded from its MIME words; None when the letter has no headers."""
    value = m.header.get(name) if m.header else None
    if not value:
        return None
    try:
        return str(email.header.make_header(email.header.decode_header(value))).strip()
    except Exception:
        return value.strip()


def read_letter(path):
    # The letters were saved from Outlook as ANSI .msg on a Polish Windows: plain string fields are cp1250 and lost
    # what cp1250 cannot hold (Cyrillic became '?'). The HTML body and the transport headers kept everything,
    # so they come first; the plain fields, read as cp1250, are the fallback.
    m = extract_msg.openMsg(path, overrideEncoding='cp1250')
    try:
        body = html_text(m.htmlBody) if m.htmlBody else (m.body or '')
        data = {'From': header(m, 'from') or m.sender, 'To': header(m, 'to') or m.to, 'Cc': header(m, 'cc') or m.cc,
                'Message-ID': header(m, 'message-id'), 'In-Reply-To': header(m, 'in-reply-to')}
        dated = None
        if header(m, 'date'):
            try:
                dated = email.utils.parsedate_to_datetime(header(m, 'date'))
            except (TypeError, ValueError):
                pass
        if dated is None:
            dated = m.date if isinstance(m.date, datetime.datetime) else parse_date(m.date or '')
        if dated and dated.tzinfo is None:
            dated = dated.replace(tzinfo=datetime.timezone.utc)
        return header(m, 'subject') or m.subject, dated, {k: v for k, v in data.items() if v}, body
    finally:
        m.close()


def pass_content():
    pdftotext = version(['pdftotext', '-v'], r'version (\S+)')
    soffice = version(['soffice', '--version'], r'LibreOffice (\S+)')
    methods = {
        'letters': method('extract-msg', extract_msg.__version__, KINDS['letters'],
                          'Письма Outlook (ANSI .msg, cp1250): текст из HTML-версии, иначе простой текст; тема, дата, '
                          'отправитель и получатели — из почтовых заголовков, иначе из полей письма; в meta'),
        'pdf': method('pdftotext', pdftotext, {'pdf'}, 'Текстовый слой PDF'),
        'writer': method('LibreOffice', soffice, WRITER, 'Документ → текст UTF-8'),
        'calc': method('LibreOffice', soffice, CALC, 'Таблица → CSV по всем листам'),
        'slides': method('LibreOffice + pdftotext', f'{soffice}; {pdftotext}', SLIDES, 'Презентация → PDF → текстовый слой'),
        'text': method('charset-normalizer', version(['pip', 'show', 'charset-normalizer'], r'Version: (\S+)'),
                       KINDS['text'], 'Чтение текста с определением кодировки, как есть'),
        'images': method('tesseract', version(['tesseract', '--version'], r'tesseract (\S+)'), KINDS['images'],
                         'Распознавание текста, языки rus+eng+pol'),
        'other': method('archive-extractor', SCRIPT_VERSION, set(), 'Для формата нет методики ступени 1'),
    }
    kinds = [args.kind] if args.kind else list(KINDS) + ['other']
    for kind in kinds:
        exts = sorted(KNOWN) if kind == 'other' else sorted(KINDS[kind])
        cond = 'not (lower(i.ext) = any(%s))' if kind == 'other' else 'lower(i.ext) = any(%s)'
        sql = f'''select a.id, a.sha256, a.size_bytes, min(lower(i.ext)) from artifact a join item i on i.artifact_id = a.id
                  where a.id > %s and {cond} {SHARD}
                    and not exists (select 1 from content c where c.artifact_id = a.id)
                  group by a.id order by a.id limit %s'''
        for chunk in batches(sql, exts):
            counts = {}
            if kind == 'other':
                for artifact_id, _, _, ext in chunk:
                    o = save_content(artifact_id, methods['other'], error='Формат не поддерживается', message=f'.{ext}')
                    counts[o] = counts.get(o, 0) + 1
                print(f'content other: {counts}, up to artifact {chunk[-1][0]}', flush=True)
                continue
            files = fetch([r[1] for r in chunk if r[2] <= MAX_SIZE])
            for artifact_id, sha, size, ext in chunk:
                path = files.get(sha)
                if not path and size <= MAX_SIZE:
                    o = 'не в хранилище, пропущено'   # not uploaded yet: no result is written, a later run takes it
                elif not path:
                    o = save_content(artifact_id, methods['other'], error='Сбой инструмента',
                                     message=f'larger than {MAX_SIZE} bytes, not read')
                elif kind == 'letters':
                    try:
                        title, dated, data, body = read_letter(path)
                        save_meta(artifact_id, methods['letters'], title, dated, data)
                        o = save_content(artifact_id, methods['letters'], body)
                    except Exception as e:
                        o = save_content(artifact_id, methods['letters'], error=error_kind(str(e)), message=repr(e))
                elif ext == 'pdf':
                    body, err, msg = tool_text(['pdftotext', '-enc', 'UTF-8', path, '-'])
                    o = save_content(artifact_id, methods['pdf'], body, err, msg)
                elif ext in WRITER or ext in CALC:
                    target = 'txt:Text (encoded):UTF8' if ext in WRITER else \
                        'csv:Text - txt - csv (StarCalc):44,34,76,1,,0,false,true,false,false,false,-1'
                    results, err, msg = office(path, ext, target)
                    body = '\n\n'.join(open(p, encoding='utf-8', errors='replace').read() for p in results)
                    o = save_content(artifact_id, methods['writer' if ext in WRITER else 'calc'], body, err, msg)
                elif ext in SLIDES:
                    results, err, msg = office(path, ext, 'pdf')
                    body = None
                    if results:
                        body, err, msg = tool_text(['pdftotext', '-enc', 'UTF-8', results[0], '-'])
                    o = save_content(artifact_id, methods['slides'], body, err, msg)
                elif kind == 'text':
                    raw = open(path, 'rb').read()
                    best = from_bytes(raw).best()
                    o = save_content(artifact_id, methods['text'], str(best) if best else raw.decode('utf-8', 'replace'))
                else:
                    body, err, msg = tool_text(['tesseract', path, 'stdout', '-l', 'rus+eng+pol'], timeout=300)
                    o = save_content(artifact_id, methods['images'], body, err, msg)
                counts[o] = counts.get(o, 0) + 1
            print(f'content {kind}: {counts}, up to artifact {chunk[-1][0]}', flush=True)
    shutil.rmtree(os.path.join(WORK, 'batch'), ignore_errors=True)


def pass_rtf():
    """Letters whose selected text lost Cyrillic ('????') are read again from the RTF body; the new version becomes
    the selected one only when it holds fewer lost characters."""
    method_id = method('extract-msg + RTF', extract_msg.__version__, KINDS['letters'],
                       'Письма Outlook, где кириллица в тексте стала «????»: текст заново из RTF-версии письма, '
                       'байты расшифрованы по кодовой странице своего шрифта (fcharset)')
    lost = re.compile(r'\?{4,}')
    sql = f'''select a.id, a.sha256, a.size_bytes from artifact a join content c on c.artifact_id = a.id and c.selected
              where a.id > %s and c.body ~ '\\?{{4,}}' {SHARD}
                and exists (select 1 from item i where i.artifact_id = a.id and lower(i.ext) = 'msg')
                and not exists (select 1 from content n where n.artifact_id = a.id and n.method_id = {method_id})
              order by a.id limit %s'''
    for chunk in batches(sql):
        files = fetch([r[1] for r in chunk])
        counts = {}
        for artifact_id, sha, _ in chunk:
            if sha not in files:
                continue
            m = extract_msg.openMsg(files[sha], overrideEncoding='cp1250')
            try:
                raw = m.rtfBody
            except Exception:
                raw = None
            finally:
                m.close()
            if not raw:
                o = save_content(artifact_id, method_id, error='Формат не поддерживается', message='no RTF body')
            else:
                body = rtf_text(raw)
                old = one('select body from content where artifact_id = %s and selected', artifact_id) or ''
                better = len(''.join(lost.findall(body))) < len(''.join(lost.findall(old)))
                if better:
                    db.execute('update content set selected = false where artifact_id = %s and selected', (artifact_id,))
                o = save_content(artifact_id, method_id, body)
                o += ', выбрано' if better else ''
            counts[o] = counts.get(o, 0) + 1
        print(f'rtf: {counts}, up to artifact {chunk[-1][0]}', flush=True)
    shutil.rmtree(os.path.join(WORK, 'batch'), ignore_errors=True)


{'format': pass_format, 'meta': pass_meta, 'content': pass_content, 'rtf': pass_rtf}[args.pass_]()
