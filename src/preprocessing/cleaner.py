"""Conservative text cleaning before chunking."""

import re


def clean_text(text: str | None) -> str:
    """Normalize whitespace without removing meaningful document content.

    The cleaner keeps paragraph boundaries, normalizes Windows/Mac newlines,
    trims line edges, compresses repeated inline spaces/tabs, and collapses
    runs of blank lines to a single paragraph break.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u3000", " ")

    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", line).strip()
        lines.append(line)

    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
