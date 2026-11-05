from __future__ import annotations

import os

from app.parser.anthropic_parser import AnthropicParser
from app.parser.base import ObservationParser
from app.parser.fake import KeywordParser

DEFAULT_PARSER = "keyword"


def create_parser_from_env() -> ObservationParser:
    """Build the configured observation parser.

    ``ROOTA_PARSER`` is ``keyword`` (default) or ``anthropic``. When anthropic
    is selected, ``ANTHROPIC_API_KEY`` must already be set — fail at startup,
    not on the first request.
    """
    kind = os.environ.get("ROOTA_PARSER", DEFAULT_PARSER).strip().lower() or DEFAULT_PARSER
    if kind == "keyword":
        return KeywordParser()
    if kind == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is required when ROOTA_PARSER=anthropic"
            )
        return AnthropicParser(api_key=api_key)
    raise RuntimeError(
        f"Unknown ROOTA_PARSER '{kind}'. Valid values: keyword, anthropic"
    )
