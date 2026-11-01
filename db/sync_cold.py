"""Brings the cold archive into layers 1-2 and onto the VPS with one command.

1. Finds files in Cold that layer 1 does not know yet, hashes them and names their source by folder rules.
2. Loads them as archive_app through load_layer1.sql; a source seen for the first time joins the dictionary.
3. Uploads every artifact the VPS does not hold yet to objects/<aa>/<sha256> (archive_files encrypts it there),
   copies the service logs to service/, and checks that every artifact in the DB is on the server with its size.
Service files (names starting with "_" in the archive root and in Mail_Outlook) are collection logs and catalogs,
not carriers: they skip layers 1-2.
Usage: python -I sync_cold.py [--dry-run]
"""
import csv, datetime, hashlib, io, os, shutil, stat, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # -I drops the script folder from the import path
from vps import PSQL, query, ssh, store

sys.stdout.reconfigure(encoding='utf-8')
DRY = '--dry-run' in sys.argv
COLD = r'C:\Work\Search\CV\Cold'
STAGING = r'C:\Work\Search\CV\Tools\_upload_staging'  # hard links only, same volume as Cold
WORK = '/root/archive_app/work'

DRIVES = {'Drive_dkhj459878': 'dkhj459878@gmail.com', 'Drive_holubvasy': 'holubvasy@gmail.com',
          'Drive_family': 'vasili.holub.family@gmail.com'}
CONTACTS = {'Mail.ru': ('Mail.ru', 'vasiliygolub@mail.ru'), 'Yandex.ru': ('Яндекс', 'vasiliygolub@yandex.ru')}
MAIL_VENDORS = {'gmail.com': 'Google', 'mail.ru': 'Mail.ru', 'yandex.ru': 'Яндекс', 'jaydevs.dev': 'JayDevs'}


def lp(p):
    return '\\\\?\\' + os.path.abspath(p)


SERVICE_DIRS = {os.path.normcase(lp(COLD)), os.path.normcase(lp(os.path.join(COLD, 'Mail_Outlook')))}


def fix(v):
    # Windows hands back emoji in file names as lone surrogate halves; join them into real characters for UTF-8
    return v.encode('utf-16', 'surrogatepass').decode('utf-16', 'replace')


def source(rel):
    """Location -> (source_type, vendor, account, method), or None when no rule covers the folder.
    The names must exist in dict.source_type, dict.vendor and dict.account; the loader stops on an unknown one."""
    parts = rel.split('/')
    top = parts[0]
    if top in DRIVES:
        return 'Облако', 'Google', DRIVES[top], 'rclone'
    if top == 'Cloud_Mailru':
        return 'Облако', 'Mail.ru', 'vasiliygolub@mail.ru', 'rclone'
    if top == 'Mail_Outlook' and len(parts) > 2:
        domain = parts[1].lower().split('@')[-1]
        return 'Почта', MAIL_VENDORS.get(domain, domain), parts[1], 'Outlook'
    if top == 'Takeout' and len(parts) > 2:
        return 'Аккаунт', 'Google', parts[1] + '@gmail.com', 'Takeout'
    if top == 'LinkedIn':
        return 'Профиль', 'LinkedIn', 'vasili-holub', 'вручную'
    if top == 'Contacts' and parts[-1].endswith('_contacts.vcf'):
        acc = parts[-1][:-len('_contacts.vcf')]
        vendor, account = CONTACTS.get(acc, ('Google', acc))
        return 'Контакты', vendor, account, 'вручную'
    return None


def sha256(p):
    h = hashlib.sha256()
    with open(lp(p), 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


# --- 1. new carrier files -------------------------------------------------------------------------------------
known = {r[0] for r in query('select location from item')}
types = dict(query('select c.ext, mode() within group (order by t.name) from item c '
                   'join dict.item_type t on t.id = c.item_type_id group by c.ext'))
rows, unruled = [], []
local = {}  # location as stored in the DB -> real path on disk (they differ for names with lone surrogates)
for d, _, fs in os.walk(lp(COLD)):
    for f in fs:
        if f.startswith('_') and os.path.normcase(d) in SERVICE_DIRS:
            continue
        full = os.path.join(d, f)
        rel = fix(full[len(lp(COLD)) + 1:].replace('\\', '/'))
        local[rel] = full
        if rel in known:
            continue
        src = source(rel)
        if not src:
            unruled.append(rel)
            continue
        ext = os.path.splitext(f)[1].lstrip('.').lower()
        st = os.stat(full)
        rows.append([rel, *src, fix(f), ext, types.get(ext, 'Другое'), st.st_size,
                     datetime.date.fromtimestamp(st.st_mtime).isoformat(), sha256(full[4:])])
if unruled:
    sys.exit('no source rule for these files (add a rule to source()):\n  ' + '\n  '.join(unruled[:30]))
print(f'new carrier files: {len(rows)}')
for r in rows[:20]:
    print(f'  + {r[0]}  [{r[1]} / {r[2]} / {r[3]}]')

# --- 2. load layers 1-2 ---------------------------------------------------------------------------------------
if rows and not DRY:
    buf = io.StringIO()
    csv.writer(buf, lineterminator='\n').writerows(rows)  # ssh's text-mode stdin turns '\n' into '\r\n' itself
    ssh(f'mkdir -p {WORK} && cat > {WORK}/layer1.csv', buf.getvalue())
    with open(os.path.join(HERE, 'load_layer1.sql'), encoding='utf-8') as fh:
        ssh(f'cat > {WORK}/load_layer1.sql', fh.read())
    print(ssh(f'{PSQL} -f /work/load_layer1.sql && rm {WORK}/layer1.csv'))

# --- 3. upload missing artifacts by hash, then verify ----------------------------------------------------------
with store() as (exe, remote):
    def on_server():
        out = subprocess.run([exe, 'lsf', '-R', '--files-only', '--format', 'ps', remote + 'objects'],
                             capture_output=True, text=True, encoding='utf-8')
        if out.returncode and 'directory not found' not in out.stderr:
            sys.exit('listing the server failed:\n' + out.stderr[-1500:])
        return {p.split('/')[-1]: int(s) for p, s in (line.rsplit(';', 1) for line in out.stdout.splitlines())}

    artifacts = {}  # sha -> (size, a location of one of its carriers that exists on this PC, else any)
    for sha, size, loc in query('select a.sha256, a.size_bytes, c.location from artifact a join item c on c.artifact_id = a.id'):
        if sha not in artifacts or (loc in local and artifacts[sha][1] not in local):
            artifacts[sha] = (int(size), loc)
    def drop_staging():
        """Removes the hard links. A link shares the read-only flag with its original, so the flag is lifted to
        unlink and put back on the original in Cold."""
        for d, _, fs in os.walk(lp(STAGING)):
            for f in fs:
                p = os.path.join(d, f)
                ro = not os.access(p, os.W_OK)
                if ro:
                    os.chmod(p, stat.S_IWRITE)
                os.unlink(p)
                if ro and f in artifacts and artifacts[f][1] in local:
                    os.chmod(local[artifacts[f][1]], stat.S_IREAD)
        shutil.rmtree(lp(STAGING))

    have = on_server()
    missing = [sha for sha in artifacts if sha not in have]
    print(f'artifacts in DB: {len(artifacts)}, on server: {len(have)}, to upload: {len(missing)}')
    if missing and not DRY:
        if os.path.exists(STAGING):
            drop_staging()
        for sha in missing:
            loc = artifacts[sha][1]
            if loc not in local:
                print(f'  ! not on this PC, cannot upload: {loc}')
                continue
            os.makedirs(os.path.join(STAGING, sha[:2]), exist_ok=True)
            os.link(local[loc], lp(os.path.join(STAGING, sha[:2], sha)))
        subprocess.run([exe, 'copy', STAGING, remote + 'objects', '--size-only', '--transfers', '4',
                        '--retries', '5', '--low-level-retries', '20', '--stats-one-line', '--stats', '60s', '-v'])
        drop_staging()
    if not DRY:
        subprocess.run([exe, 'copy', COLD, remote + 'service', '--include', '/_*', '--include', '/Mail_Outlook/_*',
                        '--size-only', '-q'])
        have = on_server()
    bad = [sha for sha, (size, _) in artifacts.items() if have.get(sha) != size]
    print(f'check: {len(artifacts) - len(bad)} of {len(artifacts)} artifacts on the server with the right size')
    for sha in bad[:20]:
        print(f'  ! {artifacts[sha][1]}  ({"missing" if sha not in have else "size differs"})')
