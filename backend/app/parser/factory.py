from __future__ import annotations

import os

from app.parser.anthropic_parser import AnthropicParser
from app.parser.base import ObservationParser
from app.parser.keyword_parser import KeywordParser

DEFAULT_PARSER = "keyword"


def create_parser_from_env() -> ObservationParser:
    """Build the configured observation parser.

    ``ROOTA_PARSER`` is ``keyword`` (default) or ``anthropic``. When anthropic
    is selected, ``ANTHROPIC_API_KEY`` must already be set — fail at startup,
    not on the first request.
    """
    kind = (os.environ.get("ROOTA_PARSER") or DEFAULT_PARSER).strip().lower()
    if kind == "keyword":
        return KeywordParser()
    if kind == "anthropic":
        # AnthropicParser raises RuntimeError itself when the key is missing.
        return AnthropicParser()
    raise RuntimeError(
        f"Unknown ROOTA_PARSER '{kind}'. Valid values: keyword, anthropic"
    )
