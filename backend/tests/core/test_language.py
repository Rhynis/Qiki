"""Tests for message language detection."""

from app.core.language import detect_language


def test_detects_english() -> None:
    assert detect_language("Hello, how much is a 12kg gas bottle?") == "en"
    assert detect_language("Can you deliver to Thu Duc today?") == "en"


def test_detects_vietnamese_with_diacritics() -> None:
    assert detect_language("Chào bạn, giá bình gas 12kg bao nhiêu?") == "vi"


def test_accentless_vietnamese_stays_vietnamese() -> None:
    # Accent-less Vietnamese without any English marker is treated as Vietnamese.
    assert detect_language("gia binh gas 12kg bao nhieu") == "vi"


def test_ambiguous_or_empty_defaults_to_vietnamese() -> None:
    assert detect_language("12kg") == "vi"
    assert detect_language("") == "vi"
