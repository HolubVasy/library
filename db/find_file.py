"""Finds a file in the archive by words in its name or path, and fetches it from the VPS to open.

  python -I find_file.py контракт andersen          list matching artifacts (all words must occur)
  python -I find_file.py контракт andersen --get 2  download match no. 2 (decrypted) and open it
  --type Документ                                    only one carrier type (Документ, Письмо, Изображение ...)

One line per artifact: a file kept in several places is listed once, with how many copies and from where.
Downloads go to C:\\Work\\Search\\CV\\Downloads under the file's own name.
"""
import argparse, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # -I drops the script folder from the import path
from vps import query, store

sys.stdout.reconfigure(encoding='utf-8')
DOWNLOADS = r'C:\Work\Search\CV\Downloads'

ap = argparse.ArgumentParser()
ap.add_argument('words', nargs='+')
ap.add_argument('--get', type=int)
ap.add_argument('--type')
args = ap.parse_args()


def lit(s):
    return "'" + s.replace("'", "''") + "'"


where = ' and '.join(f'c.location ilike {lit("%" + w + "%")}' for w in args.words)
if args.type:
    where += f' and t.name = {lit(args.type)}'
rows = query(f'''
    select a.sha256, min(c.name), min(t.name), max(c.modified_at), count(*),
           string_agg(distinct st.name || ' ' || v.name || ' ' || acc.name, '; '), min(c.location), a.size_bytes
    from item c join artifact a on a.id = c.artifact_id join dict.source s on s.id = c.source_id
    join dict.source_type st on st.id = s.source_type_id join dict.vendor v on v.id = s.vendor_id
    join dict.account acc on acc.id = s.account_id
    join dict.item_type t on t.id = c.item_type_id
    where {where}
    group by a.id order by max(c.modified_at) desc nulls last, a.id limit 50''')

if not rows:
    sys.exit('nothing found')
if not args.get:
    for n, (sha, name, kind, date, copies, sources, loc, size) in enumerate(rows, 1):
        print(f'{n:>3}. {date or "    ?     "}  {kind:<11} {int(size) // 1024:>7} KB  {name}')
        print(f'       {loc}' + (f'   (+{int(copies) - 1} copies)' if int(copies) > 1 else '') + f'   [{sources}]')
    if len(rows) == 50:
        print('... first 50 shown; add a word to narrow down')
    sys.exit()

sha, name = rows[args.get - 1][0], rows[args.get - 1][1]
os.makedirs(DOWNLOADS, exist_ok=True)
target = os.path.join(DOWNLOADS, name)
with store() as (exe, remote):
    r = subprocess.run([exe, 'copyto', f'{remote}objects/{sha[:2]}/{sha}', target], capture_output=True, text=True)
if r.returncode:
    sys.exit('download failed:\n' + r.stderr[-1500:])
print(f'saved: {target}')
os.startfile(target)
