"""Tests for the deterministic admin-instruction parser (admin_action parsing)."""

from decimal import Decimal

from app.services.admin_chat_parser import parse_admin_instruction


def test_admin_action_parse_update_price_plain_number() -> None:
    parsed = parse_admin_instruction("đổi giá Elf 12kg thành 460000")
    assert parsed is not None
    assert parsed.action == "update_price"
    assert parsed.price_value == Decimal("460000")


def test_admin_action_parse_update_price_grouped_and_k_forms() -> None:
    grouped = parse_admin_instruction("cập nhật giá Elf 12kg = 460.000")
    k_form = parse_admin_instruction("đổi giá Elf 12kg thành 460k")
    assert grouped is not None and grouped.price_value == Decimal("460000")
    assert k_form is not None and k_form.price_value == Decimal("460000")


def test_admin_action_parse_update_stock() -> None:
    parsed = parse_admin_instruction("cập nhật tồn Petrolimex 12kg thành 20")
    assert parsed is not None
    assert parsed.action == "update_stock"
    assert parsed.stock_value == 20


def test_admin_action_parse_ignores_size_token_as_value() -> None:
    # "12kg" must not be read as the new stock value.
    parsed = parse_admin_instruction("đặt tồn kho Gas 12kg còn 8")
    assert parsed is not None
    assert parsed.action == "update_stock"
    assert parsed.stock_value == 8


def test_admin_action_parse_hide_and_show_toggle() -> None:
    hide = parse_admin_instruction("ẩn sản phẩm Gas Đại Hải 12kg")
    show = parse_admin_instruction("hiện lại sản phẩm Gas Đại Hải 12kg")
    assert hide is not None and hide.action == "set_active" and hide.active_value is False
    assert show is not None and show.action == "set_active" and show.active_value is True


def test_admin_action_parse_negative_stock_is_captured_for_validation() -> None:
    parsed = parse_admin_instruction("đặt tồn Petrolimex 12kg thành -5")
    assert parsed is not None
    assert parsed.action == "update_stock"
    assert parsed.stock_value == -5


def test_admin_action_parse_unrecognized_returns_none() -> None:
    assert parse_admin_instruction("chào bạn, hôm nay thế nào?") is None
    # A price cue with no parseable amount is not actionable.
    assert parse_admin_instruction("đổi giá Elf 12kg") is None


def test_admin_action_price_command_with_brand_an_is_not_hide() -> None:
    # "An" is a brand token, not the hide verb "ẩn": a price command must win.
    parsed = parse_admin_instruction("cập nhật giá An Gas 12kg thành 460000")
    assert parsed is not None
    assert parsed.action == "update_price"
    assert parsed.price_value == Decimal("460000")


def test_admin_action_stock_command_with_brand_an_is_not_hide() -> None:
    parsed = parse_admin_instruction("cập nhật tồn An Gas 12kg thành 8")
    assert parsed is not None
    assert parsed.action == "update_stock"
    assert parsed.stock_value == 8


def test_admin_action_leading_hide_verb_still_toggles() -> None:
    # "ẩn" leading the command is still a hide toggle.
    parsed = parse_admin_instruction("ẩn An Gas 12kg")
    assert parsed is not None
    assert parsed.action == "set_active"
    assert parsed.active_value is False


def test_admin_action_non_leading_short_verb_does_not_toggle() -> None:
    # A short verb token that only appears mid-message (as a name) is not a command.
    assert parse_admin_instruction("cho xem An Gas 12kg") is None
