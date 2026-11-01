"""Full check of layer 1 against the cold archive on this PC: every file re-hashed and compared with the DB.

Reports files the DB does not know, DB rows with no file, and size or SHA-256 mismatches.
Service files (names starting with "_" in the archive root and in Mail_Outlook) are not carriers and are skipped,
as in sync_cold.py.
Usage: python -I verify_layer1.py
"""
import csv, hashlib, io, os, subprocess, sys

sys.stdout.reconfigure(encoding='utf-8')
COLD = r'C:\Work\Search\CV\Cold'


def lp(p):
    return '\\\\?\\' + os.path.abspath(p)


SERVICE_DIRS = {os.path.normcase(lp(COLD)), os.path.normcase(lp(os.path.join(COLD, 'Mail_Outlook')))}


def fix(v):
    return v.encode('utf-16', 'surrogatepass').decode('utf-16', 'replace')


sql = ('copy (select c.location, c.size_bytes, a.sha256, a.size_bytes from item c '
       'join artifact a on a.id = c.artifact_id) to stdout with csv;')
out = subprocess.run(['ssh', '-o', 'BatchMode=yes', 'jobsearch-vps', '/root/archive_app/psql.sh -At'],
                     input=sql, capture_output=True, text=True, encoding='utf-8', check=True).stdout
db = {loc: (int(size), sha, int(asize)) for loc, size, sha, asize in csv.reader(io.StringIO(out))}

unknown, size_bad, hash_bad, artifact_size_bad = [], [], [], []
seen = set()
done = 0
for d, _, fs in os.walk(lp(COLD)):
    for f in fs:
        if f.startswith('_') and os.path.normcase(d) in SERVICE_DIRS:
            continue
        full = os.path.join(d, f)
        rel = fix(full[len(lp(COLD)) + 1:].replace('\\', '/'))
        seen.add(rel)
        if rel not in db:
            unknown.append(rel)
            continue
        size, sha, asize = db[rel]
        if size != asize:
            artifact_size_bad.append(rel)
        if os.path.getsize(full) != size:
            size_bad.append(rel)
            continue
        h = hashlib.sha256()
        with open(full, 'rb') as fh:
            for b in iter(lambda: fh.read(1 << 20), b''):
                h.update(b)
        if h.hexdigest() != sha:
            hash_bad.append(rel)
        done += 1
        if done % 5000 == 0:
            print(f'  hashed {done}', flush=True)

no_file = sorted(set(db) - seen)
print(f'files on PC: {len(seen)}, rows in layer 1: {len(db)}, re-hashed: {done}')
for title, items in [('on PC but not in layer 1', unknown), ('in layer 1 but not on PC', no_file),
                     ('size differs from layer 1', size_bad), ('SHA-256 differs from layer 1', hash_bad),
                     ('carrier size differs from its artifact', artifact_size_bad)]:
    print(f'{title}: {len(items)}')
    for x in items[:10]:
        print('   ', x)
