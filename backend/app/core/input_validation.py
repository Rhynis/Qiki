"""Input validation utilities for defense against injection attacks."""

import re
from typing import Any, ClassVar


class VietnamesePhoneValidator:
    """Validate and normalize Vietnamese phone numbers."""

    PATTERN = re.compile(r"^(\+84[35789][0-9]{8}|0[35789][0-9]{8})$")

    @classmethod
    def validate(cls, value: str) -> str:
        """Validate and normalize a Vietnamese phone number."""
        normalized = value.strip().replace(" ", "").replace("-", "")
        if not cls.PATTERN.match(normalized):
            raise ValueError(f"Invalid Vietnamese phone number: {normalized}")
        if normalized.startswith("0"):
            return "+84" + normalized[1:]
        return normalized


class VietnameseTaxCodeValidator:
    """Validate Vietnamese business tax code."""

    PATTERN = re.compile(r"^[0-9]{10}(-[0-9]{3})?$")

    @classmethod
    def validate(cls, value: str) -> str:
        """Validate Vietnamese tax code format."""
        normalized = value.strip()
        if not cls.PATTERN.match(normalized):
            raise ValueError(f"Invalid Vietnamese tax code: {normalized}")
        return normalized


class PromptInjectionDetector:
    """Detect common prompt injection patterns in user input."""

    SUSPICIOUS_PATTERNS: ClassVar[list[str]] = [
        r"ignore (all )?previous instructions",
        r"disregard.*system prompt",
        r"you are now [a-zA-Z]",
        r"pretend to be",
        r"act as if",
        r"forget your training",
        r"\n\nHuman:",
        r"\n\nAssistant:",
        r"</?(system|instruction|prompt)>",
    ]

    COMPILED_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(pattern, re.IGNORECASE) for pattern in SUSPICIOUS_PATTERNS
    ]

    @classmethod
    def is_safe(cls, text: str) -> tuple[bool, str | None]:
        """Check whether text contains suspicious prompt injection patterns."""
        for pattern, raw in zip(cls.COMPILED_PATTERNS, cls.SUSPICIOUS_PATTERNS, strict=False):
            if pattern.search(text):
                return False, raw
        return True, None

    @classmethod
    def sanitize(cls, text: str) -> str:
        """Replace suspicious patterns with a redaction marker."""
        sanitized = text
        for pattern in cls.COMPILED_PATTERNS:
            sanitized = pattern.sub("[REDACTED]", sanitized)
        return sanitized


class PIIMasker:
    """Mask personally identifiable information in logs and outputs."""

    PHONE_PATTERN = re.compile(r"(\+?84|0)([0-9]{2})([0-9]{3,4})([0-9]{4})")
    EMAIL_PATTERN = re.compile(r"([a-zA-Z0-9._-]+)@([a-zA-Z0-9.-]+)")

    SENSITIVE_KEYS: ClassVar[set[str]] = {
        "password",
        "password_hash",
        "hashed_password",
        "secret",
        "api_key",
        "token",
        "access_token",
        "refresh_token",
        "credit_card",
        "card_number",
        "cvv",
    }

    @classmethod
    def mask_phone(cls, text: str) -> str:
        """Mask middle digits of phone numbers."""
        return cls.PHONE_PATTERN.sub(r"\1\2****\4", text)

    @classmethod
    def mask_email(cls, text: str) -> str:
        """Mask local part of email addresses."""

        def replace(match: re.Match[str]) -> str:
            local = match.group(1)
            domain = match.group(2)
            masked_local = local[0] + "***" + (local[-1] if len(local) > 1 else "")
            return f"{masked_local}@{domain}"

        return cls.EMAIL_PATTERN.sub(replace, text)

    @classmethod
    def mask_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively mask sensitive keys in a dictionary."""
        result: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in cls.SENSITIVE_KEYS:
                result[key] = "***REDACTED***"
            elif isinstance(value, dict):
                result[key] = cls.mask_dict(value)
            elif isinstance(value, str):
                result[key] = cls.mask_email(cls.mask_phone(value))
            else:
                result[key] = value
        return result
