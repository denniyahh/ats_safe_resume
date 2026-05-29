"""Inline markdown conversion utility.

Converts **bold** and *italic* to native formatting for each renderer.
All renderers use this instead of duplicating regex.
"""

import re

def _tokenize(text: str) -> list[tuple[str, bool, bool]]:
    """Tokenize text into (text_fragment, is_bold, is_italic) tuples."""
    pattern = r'(\*\*(?P<bold>.+?)\*\*)|((?<!\*)\*(?!\*)(?P<italic>.+?)(?<!\*)\*(?!\*))'
    tokens = []
    last_end = 0
    for m in re.finditer(pattern, text):
        if m.start() > last_end:
            tokens.append((text[last_end:m.start()], False, False))
        if m.group('bold'):
            tokens.append((m.group('bold'), True, False))
        elif m.group('italic'):
            tokens.append((m.group('italic'), False, True))
        last_end = m.end()
    if last_end < len(text):
        tokens.append((text[last_end:], False, False))
    return tokens


def strip_markdown(text: str) -> str:
    """Remove ** and * markers, return plain text."""
    return "".join(t[0] for t in _tokenize(text))


def to_typst(text: str) -> str:
    """Convert **bold** → #strong[bold], *italic* → #emph[italic] for Typst markup.
    Also escapes stray * and _ to prevent unclosed delimiter errors.
    """
    out = []
    for txt, is_b, is_i in _tokenize(text):
        txt = txt.replace('*', r'\*').replace('_', r'\_')
        if is_b:
            out.append(f"#strong[{txt}]/**/")
        elif is_i:
            out.append(f"#emph[{txt}]/**/")
        else:
            out.append(txt)
    return "".join(out)


def to_html(text: str) -> str:
    """Convert **bold** → <strong>bold</strong>, *italic* → <em>italic</em>."""
    out = []
    for txt, is_b, is_i in _tokenize(text):
        if is_b:
            out.append(f"<strong>{txt}</strong>")
        elif is_i:
            out.append(f"<em>{txt}</em>")
        else:
            out.append(txt)
    return "".join(out)


def to_docx_runs(text: str) -> list[tuple[str, bool, bool]]:
    """Tokenize text into (text_fragment, is_bold, is_italic) tuples for python-docx.

    Returns a list of (text, bold, italic) tuples that can be added as
    individual runs to a python-docx paragraph.
    """
    return _tokenize(text)
