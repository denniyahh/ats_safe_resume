"""ATS typography normalization."""

# Character normalization table: Unicode → ASCII
_NORMALIZE_TABLE = str.maketrans({
    '\u2014': '-',   # em dash
    '\u2013': '-',   # en dash
    '\u2018': "'",   # left single quote
    '\u2019': "'",   # right single quote
    '\u201c': '"',   # left double quote
    '\u201d': '"',   # right double quote
    '\u2022': '*',   # bullet
    '\u00b7': '|',   # middle dot
    '\u2026': '...', # ellipsis
})


def normalize(text: str) -> str:
    """Normalize typographic characters to ASCII for ATS-safe output."""
    return text.translate(_NORMALIZE_TABLE)
