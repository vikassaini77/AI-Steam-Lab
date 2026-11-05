"""
Tutor Response Validation and Safety Sanitization
Ensures generated tutor content is safe, scientifically formatted,
and strictly free of leaked secrets, credentials, or internal configuration details.
"""
import re
from typing import Tuple


# Regex patterns for sensitive secrets that must NEVER leak to students
SECRET_PATTERNS = [
    (r"AIzaSy[A-Za-z0-9_-]{33}", "[REDACTED_API_KEY]"),
    (r"ey[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", "[REDACTED_JWT]"),
    (r"postgres(ql)?://[^\s\"']+", "[REDACTED_DB_URL]"),
    (r"redis://[^\s\"']+", "[REDACTED_REDIS_URL]"),
    (r"sbp_[a-zA-Z0-9]{20,}", "[REDACTED_SUPABASE_TOKEN]"),
    (r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_SECRET_KEY]"),
]


def redact_sensitive_tokens(text: str) -> str:
    """
    Scans text and replaces any detected API keys, database URLs, or tokens
    with safe redacted placeholders.
    """
    if not text:
        return ""

    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized


def validate_and_sanitize_response(content: str) -> Tuple[str, bool]:
    """
    Validates complete tutor response:
    - Redacts sensitive credentials
    - Balances unclosed LaTeX math delimiters if present
    - Returns (sanitized_text, is_clean)
    """
    if not content:
        return "", True

    cleaned = redact_sensitive_tokens(content)

    # Check for unclosed display math $$
    double_dollar_count = cleaned.count("$$")
    if double_dollar_count % 2 != 0:
        cleaned += "\n$$"

    # Check for unclosed inline math $ (excluding escaped \$)
    unescaped_dollars = len(re.findall(r"(?<!\\)\$", cleaned))
    if unescaped_dollars % 2 != 0:
        cleaned += "$"

    has_modifications = (cleaned != content)
    return cleaned, not has_modifications
