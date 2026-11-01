"""The annotation pass on the seeded letters and documents, with a stub in place of the model."""
import io
import os
import sys
import zipfile

import psycopg
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'annotator'))
import annotate  # noqa: E402

APP = {'user': 'archive_app', 'password': 'test'}
STUB_TEXT = 'Это выдуманное письмо. В нём ничего настоящего.'


def stub(text):
    return STUB_TEXT, 10, 5


def run(model, size):
    with psycopg.connect(autocommit=True, **APP) as db:
        return annotate.annotate(db, stub, model, 'stub', size)


def annotated(model):
    with psycopg.connect() as db:
        return sorted(db.execute(
            """select left(a.sha256, 1), i.ext, n.text, n.selected from archive.annotation n
               join archive.artifact a on a.id = n.artifact_id join archive.item i on i.artifact_id = a.id
               join archive.method m on m.id = n.method_id where m.tool_version = %s""", (model,)).fetchall())


@pytest.fixture(scope='module')
def sample():
    run('claude-test-1', 6)
    return annotated('claude-test-1')


def test_sample_mixes_letters_and_documents_of_different_kinds(sample):
    exts = [ext for _, ext, _, _ in sample]
    assert exts.count('msg') == 3 and len(set(exts) - {'msg'}) == 3


def test_sample_takes_only_selected_text_without_skip(sample):
    run('claude-test-all', 50)
    keys = {k for k, _, _, _ in annotated('claude-test-all')}
    assert keys == set('bcdefijklnopqrtuvw')   # a, m skipped; h failed extraction; g has no text


def test_annotation_is_the_model_text_and_selected(sample):
    assert all(text == STUB_TEXT and selected for _, _, text, selected in sample)


def test_method_carries_model_version_prompt_and_code(sample):
    with psycopg.connect() as db:
        tool, version, description, code, platform = db.execute(
            """select m.tool, m.tool_version, m.description, m.code, p.name from archive.method m
               join dict.platform p on p.id = m.platform_id where m.tool_version = 'claude-test-1'""").fetchone()
    assert (tool, version, platform) == ('claude-test', 'claude-test-1', 'Anthropic API')
    assert f'промпт {annotate.PROMPT_VERSION}' in description
    assert zipfile.ZipFile(io.BytesIO(code)).namelist() == ['annotate.py']


def test_run_after_a_failure_keeps_the_sample_size():
    calls = []

    def failing(text):
        calls.append(text)
        if len(calls) > 2:
            raise RuntimeError('model is down')
        return stub(text)

    with psycopg.connect(autocommit=True, **APP) as db:
        with pytest.raises(RuntimeError):
            annotate.annotate(db, failing, 'claude-test-partial', 'stub', 6)
    run('claude-test-partial', 6)
    exts = [ext for _, ext, _, _ in annotated('claude-test-partial')]
    assert exts.count('msg') == 3 and len(exts) == 6


def test_second_run_adds_nothing(sample):
    assert run('claude-test-1', 6) == []
    assert annotated('claude-test-1') == sample
