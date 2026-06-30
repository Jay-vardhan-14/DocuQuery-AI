"""Prompt injection detection guardrails.

Uses regex-based pattern matching for fast, deterministic detection.
Patterns are extensible — can be loaded from config or a patterns file.
"""

import logging
import re
from typing import Tuple

logger = logging.getLogger(__name__)

# Prompt injection patterns to detect
# Each tuple: (pattern_name, compiled_regex)
INJECTION_PATTERNS: list[Tuple[str, re.Pattern]] = [
    ("ignore_previous", re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|context)", re.IGNORECASE)),
    ("ignore_all_prior", re.compile(r"ignore\s+all\s+prior", re.IGNORECASE)),
    ("new_persona", re.compile(r"you\s+are\s+now", re.IGNORECASE)),
    ("system_prompt_leak", re.compile(r"(show|reveal|print|display|output)\s+(me\s+)?(the\s+|your\s+)?(system\s+prompt|internal\s+instructions|instructions)", re.IGNORECASE)),
    ("disregard", re.compile(r"disregard\s+(all\s+)?(previous|prior|above|earlier)", re.IGNORECASE)),
    ("new_instructions", re.compile(r"new\s+instructions?\s*:", re.IGNORECASE)),
    ("act_as", re.compile(r"act\s+as\s+(a|an|if)", re.IGNORECASE)),
    ("pretend", re.compile(r"pretend\s+(you\s+are|to\s+be)", re.IGNORECASE)),
    ("override_rules", re.compile(r"(override|bypass|skip|forget)\s+(the\s+)?(rules|safety|restrictions|filters|guidelines)", re.IGNORECASE)),
    ("jailbreak", re.compile(r"(DAN|do\s+anything\s+now|jailbreak)", re.IGNORECASE)),
    ("encoding_attack", re.compile(r"(base64|hex|rot13|encode|decode)\s*(this|the|my)", re.IGNORECASE)),
    ("excessive_special_chars", re.compile(r"[{}<>]{5,}")),
    ("prompt_delimiter_injection", re.compile(r"(```|###|---)\s*(system|assistant|user)\s*:", re.IGNORECASE)),
]

# Maximum allowed query length
MAX_QUERY_LENGTH = 500


def detect_prompt_injection(text: str) -> Tuple[bool, str]:
    """Detect prompt injection attempts in user input.

    Args:
        text: The user's query text.

    Returns:
        Tuple of (is_injection: bool, reason: str).
        If not an injection, reason is an empty string.
    """
    # Check query length
    if len(text) > MAX_QUERY_LENGTH:
        logger.warning("Query exceeds maximum length: %d chars", len(text))
        return True, "query_too_long"

    # Check empty or whitespace-only
    if not text.strip():
        return True, "empty_query"

    # Check against all patterns
    for pattern_name, pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning(
                "Prompt injection detected: pattern=%s, text_preview=%s",
                pattern_name,
                text[:100],
            )
            return True, pattern_name

    return False, ""
