"""The CV reading pass on the seeded CVs, with a stub in place of the model."""
import datetime
import json
import os
import sys

import psycopg
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cv_reader'))
import read_cv  # noqa: E402
from test_cv_rules import run_rules  # noqa: E402

APP = {'user': 'archive_app', 'password': 'test'}
ROLES = [
    {'organization': 'Example Ltd', 'country': 'Poland', 'position': 'Developer', 'start': '2018-03', 'end': '2020'},
    {'organization': 'Sample Inc', 'country': None, 'position': 'Lead', 'start': '2020-06-15', 'end': None},
]
calls = []


def stub(text):
    calls.append(text)
    return '```json\n' + json.dumps(ROLES) + '\n```', 100, 50


def run(model, ask):
    with psycopg.connect(autocommit=True, **APP) as db:
        return read_cv.read(db, ask, model, 'stub')


def records(model):
    with psycopg.connect() as db:
        return sorted(db.execute(
            """select left(a.sha256, 1), o.name, coalesce(c.name, ''), r.position, r.start_date, r.end_date
               from career.record r join archive.method m on m.id = r.method_id
               join career.record_artifact ra on ra.record_id = r.id join archive.artifact a on a.id = ra.artifact_id
               join dict.organization o on o.id = r.organization_id left join dict.country c on c.id = o.country_id
               where m.tool_version = %s""", (model,)).fetchall())


@pytest.fixture(scope='module')
def read():
    run_rules('test')
    done = run('claude-sonnet-test', stub)
    return done, records('claude-sonnet-test')


def test_each_text_is_read_once(read):
    done, _ = read
    assert len(done) == 3 and len(calls) == 3   # n and o share a text; q and w have their own


def test_records_link_every_cv_with_the_text_and_skip_the_bots(read):
    _, rows = read
    assert {doc for doc, *_ in rows} == set('noqw')   # v, x, y were made by the bot


def test_record_holds_the_role_as_written(read):
    _, rows = read
    assert ('n', 'Example Ltd', 'Poland', 'Developer', datetime.date(2018, 3, 1), datetime.date(2020, 1, 1)) in rows
    assert ('n', 'Sample Inc', '', 'Lead', datetime.date(2020, 6, 15), None) in rows


def test_organization_joins_the_dictionary_once(read):
    with psycopg.connect() as db:
        assert db.execute("select count(*) from dict.organization where name = 'Example Ltd'").fetchone()[0] == 1


def test_method_carries_model_prompt_and_code(read):
    with psycopg.connect() as db:
        tool, step, description = db.execute(
            """select m.tool, s.name, m.description from archive.method m
               join dict.escalation_step s on s.id = m.escalation_step_id
               where m.tool_version = 'claude-sonnet-test'""").fetchone()
    assert (tool, step) == ('claude-sonnet', 'Средний уровень')
    assert f'промпт {read_cv.PROMPT_VERSION}' in description


def test_answer_that_is_not_roles_stops_and_writes_nothing():
    with pytest.raises(ValueError):
        run('claude-sonnet-broken', lambda text: ('[]', 1, 1))
    assert records('claude-sonnet-broken') == []


def test_second_run_adds_nothing(read):
    _, rows = read
    assert run('claude-sonnet-test', stub) == []
    assert records('claude-sonnet-test') == rows
