"""The pure text readers of the extractor, on small hand-made inputs."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'extractor'))
from readers import html_text, rtf_text  # noqa: E402


def test_rtf_cyrillic_font_is_read_as_cp1251():
    # the document says cp1252, but the font is Cyrillic (fcharset204): bytes must come out as Russian
    raw = (rb"{\rtf1\ansi\ansicpg1252{\fonttbl{\f0\fswiss\fcharset0 Arial;}{\f4\fswiss\fcharset204 Arial;}}"
           rb"\pard\f4 \'cf\'f0\'e8\'e2\'e5\'f2\par}")
    assert rtf_text(raw) == 'Привет'


def test_rtf_emoji_from_surrogate_pair():
    raw = rb"{\rtf1\ansi\uc1 Hi \u-10179?\u-8704?}"
    assert rtf_text(raw) == 'Hi \U0001F600'


def test_rtf_skips_font_table_and_keeps_paragraphs():
    raw = rb"{\rtf1\ansi{\fonttbl{\f0 Arial;}}\pard one\par two\par}"
    assert rtf_text(raw) == 'one\ntwo'


def test_html_keeps_lines_and_drops_tags():
    raw = '<html><head><title>x</title></head><body><p>Hello &amp; welcome</p><div>second<br>third</div></body></html>'
    assert html_text(raw) == 'Hello & welcome\nsecond\nthird'


def test_html_honours_declared_charset():
    raw = '<meta charset="windows-1251"><p>Привет</p>'.encode('cp1251')
    assert html_text(raw) == 'Привет'
