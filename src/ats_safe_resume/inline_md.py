"""Inline markdown conversion utility.

Converts **bold** and *italic* to native formatting for each renderer.
All renderers use this instead of duplicating regex.
"""

import re


def strip_markdown(text: str) -> str:
    """Remove ** and * markers, return plain text."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    return text


def to_typst(text: str) -> str:
    """Convert **bold** → *bold*, *italic* → _italic_ for Typst markup."""
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'_\1_', text)
    return text


def to_html(text: str) -> str:
    """Convert **bold** → <strong>bold</strong>, *italic* → <em>italic</em>."""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    return text


def to_docx_runs(text: str) -> list[tuple[str, bool, bool]]:
    """Tokenize text into (text_fragment, is_bold, is_italic) tuples for python-docx.

    Returns a list of (text, bold, italic) tuples that can be added as
    individual runs to a python-docx paragraph.
    """
    tokens = []
    pos = 0
    while pos < len(text):
        # Try bold: **text**
        bm = re.match(r'\*\*(.+?)\*\*', text[pos:])
        if bm:
            tokens.append((bm.group(1), True, False))
            pos += bm.end()
            continue
        # Try italic: *text*
        im = re.match(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', text[pos:])
        if im:
            tokens.append((im.group(1), False, True))
            pos += im.end()
            continue
        # Plain text
        j = pos
        while j < len(text):
            if text[j:j+1] == '*':
                break
            j += 1
        tokens.append((text[pos:j], False, False))
        pos = j

    return tokens
