"""Risk detection keywords (T010).

Keyword sets for identifying business-critical code per FR-004.
"""

# Keywords indicating business-critical code (payment, auth, security)
CRITICAL_KEYWORDS: set[str] = {
    # Payment/Financial
    "payment",
    "billing",
    "invoice",
    "transaction",
    "money",
    "price",
    "amount",
    "currency",
    "refund",
    "charge",
    "credit",
    "debit",
    "balance",
    "wallet",
    "account",
    "fee",
    "tax",
    "discount",
    "coupon",
    "subscription",
    "checkout",
    "cart",
    "purchase",
    "order",
    # Authentication/Authorization
    "auth",
    "login",
    "logout",
    "password",
    "credential",
    "token",
    "session",
    "permission",
    "role",
    "access",
    "oauth",
    "jwt",
    "sso",
    "mfa",
    "2fa",
    "otp",
    # Security
    "security",
    "encrypt",
    "decrypt",
    "secret",
    "key",
    "certificate",
    "ssl",
    "tls",
    "hash",
    "salt",
    "sanitize",
    "escape",
    "validate",
    "csrf",
    "xss",
    "injection",
    # Data Protection
    "pii",
    "gdpr",
    "hipaa",
    "privacy",
    "personal",
    "sensitive",
    "confidential",
}

# Keywords indicating non-critical code
NON_CRITICAL_KEYWORDS: set[str] = {
    # Logging
    "log",
    "logger",
    "logging",
    "debug",
    "trace",
    "info",
    "warn",
    "error",
    "audit",
    # Formatting
    "format",
    "pretty",
    "display",
    "render",
    "view",
    "template",
    "style",
    "css",
    "layout",
    # Documentation
    "doc",
    "comment",
    "readme",
    "changelog",
    "license",
    "copyright",
    # Testing
    "test",
    "mock",
    "stub",
    "fixture",
    "spec",
    "assert",
}

# File path patterns for critical areas
CRITICAL_PATH_PATTERNS: list[str] = [
    "payment",
    "billing",
    "auth",
    "security",
    "checkout",
    "order",
    "transaction",
    "account",
    "user",
    "session",
    "token",
    "credential",
]

# File path patterns for non-critical areas
NON_CRITICAL_PATH_PATTERNS: list[str] = [
    "test",
    "mock",
    "fixture",
    "log",
    "util",
    "helper",
    "constant",
    "config",
    "doc",
    "readme",
]


def contains_critical_keyword(text: str) -> bool:
    """
    Check if text contains any critical keywords.

    Args:
        text: Text to search (case-insensitive)

    Returns:
        True if any critical keyword is found
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in CRITICAL_KEYWORDS)


def contains_non_critical_keyword(text: str) -> bool:
    """
    Check if text contains any non-critical keywords.

    Args:
        text: Text to search (case-insensitive)

    Returns:
        True if any non-critical keyword is found
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in NON_CRITICAL_KEYWORDS)


def score_risk_from_keywords(text: str) -> tuple[int, int]:
    """
    Score text based on keyword presence.

    Args:
        text: Text to analyze

    Returns:
        Tuple of (critical_score, non_critical_score)
    """
    text_lower = text.lower()
    critical_score = sum(1 for kw in CRITICAL_KEYWORDS if kw in text_lower)
    non_critical_score = sum(1 for kw in NON_CRITICAL_KEYWORDS if kw in text_lower)
    return (critical_score, non_critical_score)


def is_critical_path(file_path: str) -> bool:
    """
    Check if a file path indicates business-critical code.

    Args:
        file_path: Relative file path

    Returns:
        True if path matches critical patterns
    """
    path_lower = file_path.lower()
    return any(pattern in path_lower for pattern in CRITICAL_PATH_PATTERNS)


def is_non_critical_path(file_path: str) -> bool:
    """
    Check if a file path indicates non-critical code.

    Args:
        file_path: Relative file path

    Returns:
        True if path matches non-critical patterns
    """
    path_lower = file_path.lower()
    return any(pattern in path_lower for pattern in NON_CRITICAL_PATH_PATTERNS)
