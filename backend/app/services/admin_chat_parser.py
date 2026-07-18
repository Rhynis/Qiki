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

# Verb cues (accent-stripped, whole-word) for toggling product visibility.
_HIDE_WORDS = ("an", "hide", "tat", "ngung", "deactivate", "khoa", "dung ban")
_SHOW_WORDS = ("hien", "show", "bat", "kich hoat", "activate", "mo ban", "mo lai")
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

    Toggling visibility is checked first (it needs no numeric value); a price
    command wins over a stock command when both cue words appear.
    """
    normalized = strip_accents(text)

    if any(_has_word(normalized, word) for word in _SHOW_WORDS):
        return ParsedInstruction(action="set_active", active_value=True)
    if any(_has_word(normalized, word) for word in _HIDE_WORDS):
        return ParsedInstruction(action="set_active", active_value=False)

    value_source = _strip_size_tokens(normalized)

    if any(_has_word(normalized, word) for word in _PRICE_WORDS):
        price_value = parse_price_value(value_source)
        if price_value is not None:
            return ParsedInstruction(action="update_price", price_value=price_value)

    if any(_has_word(normalized, word) for word in _STOCK_WORDS):
        stock_value = _extract_int(value_source)
        if stock_value is not None:
            return ParsedInstruction(action="update_stock", stock_value=stock_value)

    return None
