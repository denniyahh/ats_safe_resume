"""Inline markdown conversion utility.

Converts **bold** and *italic* to native formatting for each renderer.
All renderers use this instead of duplicating regex.
"""

import re

def _tokenize(text: str) -> list[tuple[str, bool, bool, str]]:
    """Tokenize text into (text_fragment, is_bold, is_italic, link_url) tuples."""
    # Matches bold, italic, and links. For links, group 'link_text' and 'link_url'.
    pattern = r'(\*\*(?P<bold>.+?)\*\*)|((?<!\*)\*(?!\*)(?P<italic>.+?)(?<!\*)\*(?!\*))|(\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^\)]+)\))'
    tokens = []
    last_end = 0
    for m in re.finditer(pattern, text):
        if m.start() > last_end:
            tokens.append((text[last_end:m.start()], False, False, ""))
        if m.group('bold'):
            tokens.append((m.group('bold'), True, False, ""))
        elif m.group('italic'):
            tokens.append((m.group('italic'), False, True, ""))
        elif m.group('link_text'):
            tokens.append((m.group('link_text'), False, False, m.group('link_url')))
        last_end = m.end()
    if last_end < len(text):
        tokens.append((text[last_end:], False, False, ""))
    return tokens


def strip_markdown(text: str) -> str:
    """Remove markers and link URLs, return plain text."""
    return "".join(t[0] for t in _tokenize(text))


def to_typst(text: str) -> str:
    """Convert formatting to Typst markup."""
    out = []
    for txt, is_b, is_i, url in _tokenize(text):
        txt = txt.replace('*', r'\*').replace('_', r'\_').replace('[', r'\[').replace(']', r'\]')
        if url:
            safe_url = url.replace('\\', '\\\\').replace('"', '\\"')
            out.append(f'#link("{safe_url}")[{txt}]')
        elif is_b:
            out.append(f"#strong[{txt}]/**/")
        elif is_i:
            out.append(f"#emph[{txt}]/**/")
        else:
            out.append(txt)
    return "".join(out)


def to_html(text: str) -> str:
    """Convert formatting to HTML markup."""
    out = []
    for txt, is_b, is_i, url in _tokenize(text):
        if url:
            out.append(f'<a href="{url}">{txt}</a>')
        elif is_b:
            out.append(f"<strong>{txt}</strong>")
        elif is_i:
            out.append(f"<em>{txt}</em>")
        else:
            out.append(txt)
    return "".join(out)


def to_docx_runs(text: str) -> list[tuple[str, bool, bool, str]]:
    """Tokenize text into (text_fragment, is_bold, is_italic, link_url) tuples for python-docx."""
    return _tokenize(text)
