"""Parse an admin instruction to Qiki into a structured catalog action.

Pure, deterministic helpers (no I/O, no LLM) so the admin-chat service resolves a
management command predictably. Determinism matters here because the command
mutates the live catalog; the confirmation step then lets the admin catch any
misparse before anything is written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.services.product_query import parse_price_value, strip_accents

AdminAction = Literal["update_price", "update_stock", "set_active"]

# Distinctive visibility verbs (accent-stripped): safe to match anywhere because
# they do not collide with brand/product names.
_HIDE_WORDS = ("hide", "ngung", "deactivate", "khoa", "dung ban")
_SHOW_WORDS = ("hien", "show", "kich hoat", "activate", "mo ban", "mo lai")
# Very short visibility verbs ("ẩn", "tắt", "bật") that DO collide with names
# (e.g. a brand "An"), so they only count as a command when they LEAD the message.
_HIDE_LEADING_WORDS = ("an", "tat")
_SHOW_LEADING_WORDS = ("bat",)
_PRICE_WORDS = ("gia", "price")
_STOCK_WORDS = ("ton", "kho", "stock", "quantity", "so luong")

_SIZE_KG_RE = re.compile(r"\b\d+\s*kg\b")
_SIZE_LITRE_RE = re.compile(r"\b\d+\s*(?:lit|l)\b")
_INT_AFTER_SEP_RE = re.compile(r"(?:thanh|con|sang|toi|to|=|->|→)\s*(-?\d+)")
_INT_RE = re.compile(r"-?\d+")


@dataclass(frozen=True)
class ParsedInstruction:
    """A resolved admin command: the action plus its target value."""

    action: AdminAction
    price_value: Decimal | None = None
    stock_value: int | None = None
    active_value: bool | None = None


def _has_word(normalized: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", normalized) is not None


def _is_leading_command(normalized: str, word: str) -> bool:
    """True when ``word`` leads the instruction (an imperative verb), not an
    incidental brand/name token further in the message. Allows one leading filler
    (e.g. "vui long", "hay") so polite phrasings still classify."""
    tokens = normalized.split()
    return word in tokens[:2]


def _strip_size_tokens(normalized: str) -> str:
    """Remove size tokens ('12kg', '5l') so they cannot be read as the new value."""
    without_kg = _SIZE_KG_RE.sub(" ", normalized)
    return _SIZE_LITRE_RE.sub(" ", without_kg)


def _extract_int(value_source: str) -> int | None:
    """Return the integer that follows a 'set to' separator, else the last integer."""
    after_separator = _INT_AFTER_SEP_RE.search(value_source)
    if after_separator:
        return int(after_separator.group(1))
    matches = _INT_RE.findall(value_source)
    return int(matches[-1]) if matches else None


def parse_admin_instruction(text: str) -> ParsedInstruction | None:
    """Classify an admin message into a catalog action, or None if unrecognized.

    Price/stock commands are classified BEFORE the visibility toggles: they carry a
    distinctive keyword ("giá"/"tồn"...) plus a value, so a brand like "An"/"Bật"
    inside such a command is never misread as a hide/show verb. A price command wins
    over a stock command when both cue words appear.
    """
    normalized = strip_accents(text)
    value_source = _strip_size_tokens(normalized)

    if any(_has_word(normalized, word) for word in _PRICE_WORDS):
        price_value = parse_price_value(value_source)
        if price_value is not None:
            return ParsedInstruction(action="update_price", price_value=price_value)

    if any(_has_word(normalized, word) for word in _STOCK_WORDS):
        stock_value = _extract_int(value_source)
        if stock_value is not None:
            return ParsedInstruction(action="update_stock", stock_value=stock_value)

    # Visibility toggles: distinctive verbs match anywhere; the short ambiguous
    # verbs (ẩn/tắt/bật) only count when they lead the command.
    if any(_has_word(normalized, word) for word in _SHOW_WORDS) or any(
        _is_leading_command(normalized, word) for word in _SHOW_LEADING_WORDS
    ):
        return ParsedInstruction(action="set_active", active_value=True)
    if any(_has_word(normalized, word) for word in _HIDE_WORDS) or any(
        _is_leading_command(normalized, word) for word in _HIDE_LEADING_WORDS
    ):
        return ParsedInstruction(action="set_active", active_value=False)

    return None
