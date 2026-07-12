"""Lightweight message language detection (Vietnamese vs English).

The shop is Vietnamese-first, so detection is conservative: a message is only
treated as English when it carries a clear English signal and no Vietnamese
diacritics. Ambiguous ASCII (e.g. accent-less Vietnamese) stays Vietnamese.
"""

import re
from typing import Literal

Language = Literal["vi", "en"]

# Vietnamese-specific letters (a message containing any of these is Vietnamese).
_VIETNAMESE_CHARS = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệ" "ìíỉĩịòóỏõọôồốổỗộơờớởỡợ" "ùúủũụưừứửữựỳýỷỹỵđ")

# Distinctly-English tokens that rarely appear in Vietnamese text.
_ENGLISH_MARKERS = {
    "the",
    "is",
    "are",
    "hello",
    "hi",
    "hey",
    "please",
    "thanks",
    "thank",
    "you",
    "your",
    "how",
    "what",
    "where",
    "when",
    "which",
    "much",
    "cost",
    "price",
    "delivery",
    "deliver",
    "order",
    "available",
    "today",
    "need",
    "want",
    "can",
    "could",
    "does",
    "bottle",
    "buy",
    "refill",
    "hours",
    "have",
    "near",
    "open",
}

_WORD_RE = re.compile(r"[a-z]+")


def detect_language(text: str) -> Language:
    """Return 'en' for clearly-English text, otherwise 'vi'."""
    lowered = text.lower()
    if any(char in _VIETNAMESE_CHARS for char in lowered):
        return "vi"
    tokens = set(_WORD_RE.findall(lowered))
    if tokens & _ENGLISH_MARKERS:
        return "en"
    return "vi"
