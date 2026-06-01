"""Tests for HCMC ward to old district lookup."""

from app.services.address_lookup import resolve_district_from_ward


def test_resolve_hiep_binh_chanh_returns_thu_duc() -> None:
    assert resolve_district_from_ward("Hiệp Bình Chánh") == "Thủ Đức"


def test_resolve_with_phuong_prefix() -> None:
    assert resolve_district_from_ward("Phường Hiệp Bình Chánh") == "Thủ Đức"
    assert resolve_district_from_ward("P. Hiệp Bình Chánh") == "Thủ Đức"


def test_resolve_case_insensitive() -> None:
    assert resolve_district_from_ward("phường hiệp bình chánh") == "Thủ Đức"


def test_unknown_ward_returns_none() -> None:
    assert resolve_district_from_ward("Phường Không Có Trong Bảng") is None
