"""One-off: re-lays the encrypted cold copy on the VPS from source paths to objects/<aa>/<sha256>.

Runs on the VPS. Reads location,sha256 pairs from the DB and drives a temporary rclone (same image and keys
as archive_files) over its remote-control API: the first copy of an artifact is moved to its object path,
further copies are removed. Paths it cannot find are counted; the sync script uploads those artifacts by hash.
Usage: python3 rehash_server.py [--apply]
"""
import csv, io, json, subprocess, sys, time, urllib.request

APPLY = '--apply' in sys.argv
RC = 'http://127.0.0.1:5572/'


def rc(method, **params):
    req = urllib.request.Request(RC + method, json.dumps(params).encode(), {'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{method} {params}: {e.read().decode()[:300]}')


def object_path(sha):
    return f'objects/{sha[:2]}/{sha}'


dump = subprocess.run(['docker', 'exec', 'archive_db', 'psql', '-U', 'archive', '-d', 'archive', '-c',
                       'copy (select c.location, a.sha256 from item c join artifact a on a.id = c.artifact_id order by c.id) to stdout with csv'],
                      capture_output=True, text=True, check=True).stdout
pairs = list(csv.reader(io.StringIO(dump)))

subprocess.run(['docker', 'run', '-d', '--rm', '--name', 'rehash', '--env-file', '/root/archive_files/.env',
                '-v', '/srv/cold_backup:/data', '-p', '127.0.0.1:5572:5572', 'rclone/rclone:1.68.2',
                'rcd', '--rc-addr', ':5572', '--rc-no-auth'], check=True, capture_output=True)
try:
    for _ in range(30):
        try:
            rc('rc/noop')
            break
        except Exception:
            time.sleep(1)

    # one listing of the whole store (stat per file would re-list each parent folder)
    listing = rc('operations/list', fs='cold:', remote='',
                 opt={'recurse': True, 'filesOnly': True, 'noModTime': True, 'noMimeType': True})['list']
    sizes = {i['Path']: i['Size'] for i in listing}
    print(f'files on server: {len(sizes)}', flush=True)

    moved = dropped = missing = already = 0
    placed = {}  # sha -> size of the copy that became the object (lets a dry run count duplicates too)
    for n, (loc, sha) in enumerate(pairs, 1):
        obj = object_path(sha)
        if sha not in placed and obj in sizes:
            placed[sha] = sizes[obj]
        src = {'Size': sizes[loc]} if loc in sizes else None
        if not src:
            if sha in placed:
                already += 1
            else:
                missing += 1
        elif sha in placed:
            if placed[sha] != src['Size']:
                sys.exit(f'size mismatch for {loc}')
            dropped += 1
            if APPLY:
                rc('operations/deletefile', fs='cold:', remote=loc)
        else:
            moved += 1
            placed[sha] = src['Size']
            if APPLY:
                rc('operations/movefile', srcFs='cold:', srcRemote=loc, dstFs='cold:', dstRemote=obj)
        if n % 5000 == 0:
            print(f'{n}/{len(pairs)}', flush=True)
finally:
    subprocess.run(['docker', 'stop', 'rehash'], capture_output=True)

print(f'{"applied" if APPLY else "dry run"}: moved {moved}, duplicate copies removed {dropped}, '
      f'already in place {already}, not on server {missing}')
