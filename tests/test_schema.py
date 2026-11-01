"""The schema after all migrations: where tables live, key types, and what the code role may not do."""
import os

import psycopg
import pytest

APP = {'user': 'archive_app', 'password': 'test'}


def test_schemas_hold_their_tables():
    with psycopg.connect() as db:
        rows = dict(db.execute("""select table_schema, count(*) from information_schema.tables
                                  where table_schema in ('archive', 'dict', 'public') group by 1""").fetchall())
    assert rows.get('archive', 0) >= 8 and rows.get('dict', 0) >= 12 and 'public' not in rows


def test_every_key_is_bigint():
    with psycopg.connect() as db:
        bad = db.execute("""select table_schema || '.' || table_name || '.' || column_name from information_schema.columns
                            where table_schema in ('archive', 'dict', 'career')
                              and (column_name = 'id' or column_name like '%%\\_id') and data_type <> 'bigint'""").fetchall()
    assert bad == []


def test_annotation_is_shaped_like_content():
    with psycopg.connect() as db:
        cols = {r[0] for r in db.execute("""select column_name from information_schema.columns
                                            where table_schema = 'archive' and table_name = 'annotation'""")}
    assert {'artifact_id', 'method_id', 'text', 'selected'} <= cols


@pytest.mark.parametrize('sql', [
    'delete from archive.content',
    'delete from archive.artifact_tag',
    'update archive.content set body = null',
    'delete from archive.annotation',
    'update archive.annotation set text = \'x\'',
    'insert into dict.category (name) values (\'x\')',
])
def test_code_role_cannot_rewrite(sql):
    # only on top: the code adds rows, it never deletes or edits what is there
    with psycopg.connect(**APP) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(sql)
