"""Builds the layer 1 load file: every file of the cold archive with its SHA-256.

Non-mail files come from the stage 2 inventory (hashes already computed); mail messages (.msg) are hashed here.
"""
import os, sys, csv, hashlib, datetime
from openpyxl import load_workbook
sys.stdout.reconfigure(encoding='utf-8')

COLD = r'C:\Work\Search\CV\Cold'
INV = r'C:\Work\Search\CV\Этап2_Опись_холодного_архива_2026-10-30.xlsx'
OUT = r'C:\Work\Search\CV\Tools\db\layer1.csv'


def lp(p):
    return '\\\\?\\' + os.path.abspath(p)


def sha256(p):
    h = hashlib.sha256()
    with open(lp(p), 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


DRIVE = {'Google Drive dkhj459878': 'dkhj459878@gmail.com', 'Google Drive holubvasy': 'holubvasy@gmail.com',
         'Google Drive family': 'vasili.holub.family@gmail.com'}


def mail_system(store):
    s = store.lower()
    return ('Gmail' if s.endswith('@gmail.com') else 'Почта Mail.ru' if s.endswith('@mail.ru')
            else 'Почта Яндекс' if s.endswith('@yandex.ru') else 'Почта ' + s.split('@')[-1])


def split_source(source, rel):
    """Inventory 'Источник' -> (source_system, source_account)."""
    if source in DRIVE:
        return 'Google Drive', DRIVE[source]
    if source == 'Облако Mail.ru':
        return 'Облако Mail.ru', 'vasiliygolub@mail.ru'
    if source.startswith('Почта '):
        store = source[len('Почта '):]
        return mail_system(store), store
    # files placed in the archive root by hand: contact exports, LinkedIn profile
    name = os.path.basename(rel)
    if name.endswith('_contacts.vcf'):
        acc = name[:-len('_contacts.vcf')]
        return 'Экспорт контактов', acc
    if name.lower() == 'profile.pdf':
        return 'LinkedIn', 'профиль'
    return 'Экспорт вручную', ''


rows = []
ws = load_workbook(INV, read_only=True)['Файлы']
for r in ws.iter_rows(min_row=2, values_only=True):
    # Источник, Путь, Папка, Имя, Расширение, Категория, Размер КБ, Изменён, SHA-256, Копий
    p = os.path.join(COLD, r[1])
    rows.append([r[1].replace('\\', '/'), *split_source(r[0], r[1]), r[3], r[4] or '', r[5], os.stat(lp(p)).st_size, r[7], r[8]])

mail = 0
for d, _, fs in os.walk(os.path.join(COLD, 'Mail_Outlook')):
    for f in fs:
        if not f.lower().endswith('.msg'):
            continue
        p = os.path.join(d, f)
        rel = os.path.relpath(p, COLD)
        st = os.stat(lp(p))
        store = rel.split(os.sep)[1]
        rows.append([rel.replace('\\', '/'), mail_system(store), store, f, 'msg', 'Письмо', st.st_size,
                     datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d'), sha256(p)])
        mail += 1

def fix(v):
    # Windows hands back emoji in file names as lone surrogate halves; join them into real characters for UTF-8
    return v.encode('utf-16', 'surrogatepass').decode('utf-16', 'replace') if isinstance(v, str) else v


with open(OUT, 'w', encoding='utf-8', newline='') as fh:
    csv.writer(fh).writerows([[fix(v) for v in r] for r in rows])
print(f'rows {len(rows)} (files {len(rows) - mail}, mail {mail}), unique {len({r[8] for r in rows})} -> {OUT}')
