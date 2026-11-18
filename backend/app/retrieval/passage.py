"""Normalize verbatim PDF extracts for technician display."""

from __future__ import annotations

import re

# The fault-table header "Code (hex) Fault / Aux. code Cause What to do" that
# pypdf leaves at the end of an entry chunk when the next table page starts.
# Any leading part of it (down to a bare "Code (hex)"), or the part from
# "Fault" to the end, is a fragment when it ends the passage.
_TRAILING_TABLE_HEADER_RE = re.compile(
    r"(?:^|\s)(?:"
    r"Code\s+\(hex\)"
    r"(?:\s+Fault(?:\s*/\s*Aux\.(?:\s+code(?:\s+Cause(?:\s+What(?:\s+to(?:\s+do)?)?)?)?)?)?)?"
    r"|Fault\s*/\s*Aux\.\s+code\s+Cause\s+What\s+to\s+do"
    r")\s*$"
)

_LIST_ITEM_RE = re.compile(
    r"^(?:"
    r"[-*•]\s+"
    r"|\d+[.)]\s+"
    r"|[a-zA-Z][.)]\s+"
    r")"
)


def reflow_passage(text: str) -> str:
    """Reflow soft PDF line breaks into paragraphs; keep real list items.

    Also drops trailing fault-table header fragments that pypdf leaves at the
    end of an entry chunk.
    """
    cleaned = _drop_table_header_fragments(text.replace("\r\n", "\n").replace("\r", "\n"))
    if not cleaned.strip():
        return ""

    paragraphs: list[str] = []
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        paragraphs.append(_join_soft_breaks(current))
        current = []

    for raw_line in cleaned.split("\n"):
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if _LIST_ITEM_RE.match(line):
            flush()
            paragraphs.append(line)
            continue
        current.append(line)
    flush()
    return "\n\n".join(paragraphs)


def _drop_table_header_fragments(text: str) -> str:
    """Strip a trailing fault-table header fragment, on its own line or not."""
    return _TRAILING_TABLE_HEADER_RE.sub("", text.rstrip()).rstrip()


def _join_soft_breaks(lines: list[str]) -> str:
    if not lines:
        return ""
    parts: list[str] = [lines[0]]
    for line in lines[1:]:
        prev = parts[-1]
        if prev.endswith("-") and len(prev) > 1 and not prev.endswith(" -"):
            # PDF hyphenation at line end: join without the hyphen or a space.
            parts[-1] = prev[:-1] + line
        else:
            parts[-1] = f"{prev} {line}"
    return parts[-1]
