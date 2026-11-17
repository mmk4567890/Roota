"""Display metadata for known manuals (short UI name vs full citation)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ManualMeta:
    short_name: str
    full_title: str
    document_number: str | None = None


# Keys are graph / evidence ``doc_id`` values.
MANUALS: dict[str, ManualMeta] = {
    "abb_acs580_fw": ManualMeta(
        short_name="ABB ACS580 firmware manual",
        full_title="ABB ACS580 standard control program firmware manual",
        document_number="3AXD50000016097 Rev J",
    ),
}


def short_doc_name(doc_id: str, fallback_title: str | None = None) -> str:
    meta = MANUALS.get(doc_id)
    if meta is not None:
        return meta.short_name
    if fallback_title:
        return fallback_title
    return doc_id


def full_doc_citation(doc_id: str, fallback_title: str | None = None) -> str:
    """Full title and document number for an expanded passage."""
    meta = MANUALS.get(doc_id)
    if meta is None:
        return fallback_title or doc_id
    if meta.document_number:
        return f"{meta.full_title}, {meta.document_number}"
    return meta.full_title


def section_short_label(section: str) -> str:
    """Strip 'Fault tracing:' / printed-page suffixes for compact citations."""
    text = section.strip()
    for prefix in ("Fault tracing: ", "Fault tracing:"):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
            break
    # Drop trailing "(printed p. N)" / "(p. N)".
    if " (printed p." in text:
        text = text[: text.index(" (printed p.")].strip()
    elif " (p." in text:
        text = text[: text.index(" (p.")].strip()
    return text
