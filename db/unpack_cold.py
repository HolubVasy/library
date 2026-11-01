"""Unpacks the archives found in the cold archive next to themselves, so that their content becomes ordinary carriers.

An archive stays a carrier and an artifact of its own; what is inside it is unpacked beside it into
<archive>.unpacked/ and sync_cold.py then registers those files like any others. The folder name is the link
"inside": everything under X.rar.unpacked/ came from X.rar. Archives found inside are unpacked the same way.
An archive already having its .unpacked folder is skipped, so the script is re-runnable.
Zip names without the UTF-8 flag are in the code page of the Windows that packed them: Cyrillic (cp866) or
Polish (cp852); the one giving more letters of its alphabet is used.
Archives that 7-Zip cannot open (password, damage) are listed in _unpack.log and left packed.
Code repositories in KEEP_PACKED stay packed on purpose.
Usage: python -I unpack_cold.py [--dry-run]
"""
import datetime, os, re, shutil, subprocess, sys

sys.stdout.reconfigure(encoding='utf-8')
DRY = '--dry-run' in sys.argv
COLD = r'C:\Work\Search\CV\Cold'
SEVEN = r'C:\Program Files\7-Zip\7z.exe'
LOG = os.path.join(COLD, '_unpack.log')   # "_" in the archive root: a service file, not a carrier
ARCHIVES = ('.zip', '.rar', '.7z', '.tar', '.gz', '.tgz', '.bz2')
# code repositories and package caches: the archive itself is the evidence, its tens of thousands of files are not
KEEP_PACKED = {
    r'Cloud_Mailru\Repositories\Favorhealth\Favorhealth.zip',
    r'Drive_dkhj459878\Repositories\Siemens\Siemens.zip',
    r'Cloud_Mailru\Focus\Focus.Pro2.rar',
    r'Drive_dkhj459878\English207 — Attachments from Classic Sites\Документы\npm-cache.rar',
    r'Drive_dkhj459878\Focus.rar',
    r'Drive_dkhj459878\Angular.rar',
}
SUFFIX = '.unpacked'
CYRILLIC = re.compile('[А-яЁё]')
POLISH = re.compile('[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]')


def lp(p):
    return '\\\\?\\' + os.path.abspath(p)


def seven(*args, timeout=3600):
    return subprocess.run([SEVEN, *args], capture_output=True, timeout=timeout, encoding='utf-8', errors='replace')


def listing(path, cp=None):
    """Names inside the archive, or (None, reason) when 7-Zip cannot read it."""
    r = seven('l', '-slt', '-p', '-sccUTF-8', *([f'-mcp={cp}'] if cp else []), path, timeout=600)
    if r.returncode:
        reason = (r.stderr.strip() or r.stdout.strip().splitlines()[-1:] or ['7-Zip exit %d' % r.returncode])
        return None, reason if isinstance(reason, str) else reason[0]
    names = [l[7:] for l in r.stdout.splitlines() if l.startswith('Path = ')][1:]  # the first is the archive itself
    return names, None


def code_page(path):
    """For a zip: '866' or '852' by the alphabet the names come out in; None for other formats."""
    if not path.lower().endswith('.zip'):
        return None
    ru, _ = listing(path, '866')
    pl, _ = listing(path, '852')
    ru_score = sum(len(CYRILLIC.findall(n)) for n in ru or [])
    pl_score = sum(len(POLISH.findall(n)) for n in pl or [])
    return '866' if ru_score >= pl_score else '852'


def archives(root):
    for d, dirs, fs in os.walk(lp(root)):
        for f in fs:
            full = os.path.join(d, f)
            if f.lower().endswith(ARCHIVES) and not os.path.isdir(full + SUFFIX) \
                    and full[len(lp(COLD)) + 1:] not in KEEP_PACKED:
                yield full


log = []
queue = list(archives(COLD))
done = failed = files_out = 0
print(f'archives to unpack: {len(queue)}{" (dry run: nested ones show up only after a real run)" if DRY else ""}')
while queue:
    path = queue.pop(0)
    rel = path[len(lp(COLD)) + 1:]
    cp = code_page(path)
    names, reason = listing(path, cp)
    if names is None:
        failed += 1
        log.append(f'not unpacked\t{rel}\t{reason}')
        print(f'  ! {rel}: {reason}')
        continue
    print(f'  {rel}  [{len(names)} entries{", cp" + cp if cp else ""}]  e.g. {", ".join(names[:2])}')
    if DRY:
        continue
    target = path + SUFFIX
    r = seven('x', '-y', '-p', *([f'-mcp={cp}'] if cp else []), f'-o{target}', path)
    if r.returncode:
        shutil.rmtree(target, ignore_errors=True)
        failed += 1
        log.append(f'not unpacked\t{rel}\t{(r.stderr or r.stdout).strip()[-300:]}')
        print(f'  ! {rel}: 7-Zip exit {r.returncode}')
        continue
    done += 1
    count = sum(len(fs) for _, _, fs in os.walk(target))
    files_out += count
    log.append(f'unpacked\t{rel}\t{count} files')
    queue.extend(archives(target))   # archives inside archives

print(f'unpacked: {done}, files out: {files_out}, not unpacked: {failed}')
if not DRY and log:
    with open(lp(LOG), 'a', encoding='utf-8') as fh:
        fh.write(f'# {datetime.datetime.now().isoformat(timespec="seconds")}\n' + '\n'.join(log) + '\n')
