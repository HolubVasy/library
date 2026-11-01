"""Pure text readers of the extractor: no database, no files, no tools. Tested in CI (tests/test_readers.py)."""
import html
import re


def html_text(raw):
    """HTML -> plain text: line breaks kept at block ends, tags dropped, entities decoded."""
    if isinstance(raw, bytes):
        cs = re.search(rb'charset=["\']?([\w-]+)', raw[:4000])
        try:
            raw = raw.decode(cs.group(1).decode() if cs else 'utf-8', 'replace')
        except LookupError:
            raw = raw.decode('utf-8', 'replace')
    raw = re.sub(r'(?is)<(script|style|head).*?</\1>', ' ', raw)
    raw = re.sub(r'(?i)<br\s*/?>|</(p|div|tr|li|h\d|table)>', '\n', raw)
    text = html.unescape(re.sub(r'<[^>]+>', '', raw)).replace('\xa0', ' ')
    return '\n'.join(re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()).strip()


RTF_CHARSETS = {0: 'cp1252', 77: 'mac_roman', 128: 'cp932', 129: 'cp949', 134: 'gbk', 136: 'cp950', 161: 'cp1253',
                162: 'cp1254', 163: 'cp1258', 177: 'cp1255', 178: 'cp1256', 186: 'cp1257', 204: 'cp1251', 222: 'cp874',
                238: 'cp1250'}
RTF_SKIP = {'fonttbl', 'colortbl', 'stylesheet', 'info', 'pict', 'header', 'footer', 'headerl', 'headerr', 'footerl',
            'footerr', 'object', 'listtable', 'listoverridetable', 'rsidtbl', 'generator', 'xmlnstbl', 'themedata'}
RTF_TOKEN = re.compile(rb"\\'([0-9a-fA-F]{2})|\\([a-zA-Z]+)(-?\d+)? ?|\\([^a-zA-Z])|([{}])|([^\\{}\r\n]+)|[\r\n]+")


def rtf_text(raw):
    """RTF -> plain text. Bytes written as \\'hh are decoded by the code page of the font they are in, so a Cyrillic
    font (fcharset204) gives cp1251 even when the document is declared cp1252."""
    default = 'cp' + (re.search(rb'\\ansicpg(\d+)', raw[:2000]) or [b'', b'1252'])[1].decode()
    fonts = {int(n): RTF_CHARSETS.get(int(c), default)
             for n, c in re.findall(rb'\\f(\d+)[^;{}]*?\\fcharset(\d+)', raw.split(b'\\colortbl')[0])}
    out, pending = [], bytearray()
    state = {'font': None, 'skip': False, 'uc': 1}
    stack, skip_chars, first_in_group = [], 0, False

    def flush():
        if pending:
            out.append(pending.decode(fonts.get(state['font'], default), 'replace'))
            pending.clear()

    for m in RTF_TOKEN.finditer(raw):
        hexbyte, word, num, symbol, brace, text = m.groups()
        if brace == b'{':
            flush()
            stack.append(dict(state))
            first_in_group = True
            continue
        if brace == b'}':
            flush()
            state = stack.pop() if stack else state
            continue
        starts_group, first_in_group = first_in_group, False
        if word is not None:
            w = word.decode()
            if starts_group and w in RTF_SKIP:
                state['skip'] = True
            elif w == 'f' and num is not None:
                flush()
                state['font'] = int(num)
            elif w == 'uc' and num is not None:
                state['uc'] = int(num)
            elif w == 'u' and num is not None and not state['skip']:
                flush()
                out.append(chr(int(num) % 65536))
                skip_chars = state['uc']
            elif w in ('par', 'line') and not state['skip']:
                flush()
                out.append('\n')
            elif w == 'tab' and not state['skip']:
                flush()
                out.append('\t')
            continue
        if symbol is not None:
            if symbol == b'*' and starts_group:
                state['skip'] = True
            elif symbol in (b'\\', b'{', b'}') and not state['skip']:
                pending.extend(symbol)
            continue
        if state['skip']:
            continue
        if hexbyte is not None:
            if skip_chars:
                skip_chars -= 1
            else:
                pending.extend(bytes.fromhex(hexbyte.decode()))
        elif text is not None:
            if skip_chars:
                n = min(skip_chars, len(text))
                text, skip_chars = text[n:], skip_chars - n
            pending.extend(text)
    flush()
    # \u escapes give emoji as two surrogate halves: join the pairs, replace a half left alone
    text = ''.join(out).encode('utf-16', 'surrogatepass').decode('utf-16', 'replace')
    return '\n'.join(line.rstrip() for line in text.splitlines()).strip()
