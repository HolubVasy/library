"""The CV rules on the seeded documents: which are the owner's CVs, identical texts once, a second run adds nothing."""
import base64
import io
import os
import subprocess
import zipfile

import psycopg
import pytest

RULES = os.path.join(os.path.dirname(__file__), '..', 'db', 'cv_rules.sql')
APP = {**os.environ, 'PGUSER': 'archive_app', 'PGPASSWORD': 'test'}


def run_rules(version):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.write(RULES, 'cv_rules.sql')
    code = base64.b64encode(buf.getvalue()).decode()
    r = subprocess.run(['psql', '-X', '-q', '-A', '-t', '-v', f'code={code}', '-v', f'version={version}', '-f', RULES],
                       env=APP, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def marked(version):
    with psycopg.connect() as db:
        rows = db.execute(
            """select left(a.sha256, 1), ac.reason from archive.artifact_category ac
               join archive.artifact a on a.id = ac.artifact_id join dict.category c on c.id = ac.category_id
               join archive.method m on m.id = ac.method_id
               where c.name = 'cv' and m.tool = 'cv-rules' and m.tool_version = %s""", (version,)).fetchall()
    return sorted(rows)


@pytest.fixture(scope='module')
def summary():
    return run_rules('test')


@pytest.fixture(scope='module')
def by_doc(summary):
    return dict(marked('test'))


@pytest.mark.parametrize('doc, rule', [
    ('n', 'R1'),   # CV word and the owner in the name
    ('o', 'R1'),   # a copy of n
    ('q', 'R2'),   # the owner and a role in the name, experience in the text
])
def test_owner_cv_is_found(by_doc, doc, rule):
    assert by_doc.get(doc, '').startswith(rule)


@pytest.mark.parametrize('doc', ['p', 'r', 't', 'i'])   # someone else's CV, a cover letter, a letter, a plain document
def test_not_a_cv(by_doc, doc):
    assert doc not in by_doc


def test_identical_texts_count_once(summary):
    assert summary == '3|2'   # three CVs, n and o share one text


def test_second_run_adds_nothing(by_doc):
    run_rules('test')
    assert dict(marked('test')) == by_doc


def test_method_keeps_its_code(summary):
    with psycopg.connect() as db:
        code = db.execute("select code from archive.method where tool = 'cv-rules' and tool_version = 'test'").fetchone()[0]
    assert zipfile.ZipFile(io.BytesIO(code)).namelist() == ['cv_rules.sql']
