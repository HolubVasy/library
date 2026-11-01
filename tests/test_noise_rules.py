"""The noise rules on the seeded letters: who gets which category, and that a second run adds nothing."""
import base64
import io
import os
import subprocess
import zipfile

import psycopg
import pytest

RULES = os.path.join(os.path.dirname(__file__), '..', 'db', 'noise_rules.sql')
APP = {**os.environ, 'PGUSER': 'archive_app', 'PGPASSWORD': 'test'}


def run_rules(version):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.write(RULES, 'noise_rules.sql')
    code = base64.b64encode(buf.getvalue()).decode()
    r = subprocess.run(['psql', '-X', '-q', '-v', f'code={code}', '-v', f'version={version}', '-f', RULES],
                       env=APP, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def categories(version):
    with psycopg.connect() as db:
        rows = db.execute(
            """select left(a.sha256, 1), c.name from archive.artifact_category ac
               join archive.artifact a on a.id = ac.artifact_id join dict.category c on c.id = ac.category_id
               join archive.method m on m.id = ac.method_id where m.tool = 'noise-rules' and m.tool_version = %s""",
            (version,)).fetchall()
    return dict(rows)


@pytest.fixture(scope='module')
def marks():
    run_rules('test')
    return categories('test')


@pytest.mark.parametrize('letter, category', [
    ('a', 'notification'),   # noreply@ of a service
    ('b', 'newsletter'),     # newsletter domain
    ('c', 'job_platform'),   # anything from LinkedIn
    ('e', 'newsletter'),     # News Letters folder
    ('g', 'spam'),           # spam domain
    ('h', 'job_platform'),   # automated letter of a career platform is not noise
])
def test_category(marks, letter, category):
    assert marks.get(letter) == category


@pytest.mark.parametrize('letter', ['d', 'f'])   # own address; a live person on a career domain
def test_left_alone(marks, letter):
    assert letter not in marks


def test_second_run_adds_nothing(marks):
    run_rules('test')
    assert categories('test') == marks


def test_method_keeps_its_code(marks):
    with psycopg.connect() as db:
        code = db.execute("select code from archive.method where tool = 'noise-rules' and tool_version = 'test'").fetchone()[0]
    assert zipfile.ZipFile(io.BytesIO(code)).namelist() == ['noise_rules.sql']
