"""Tests for HCMC ward to delivery zone lookup."""

from app.services.address_lookup import resolve_delivery_zone_from_ward


def test_resolve_binh_thanh_numbered_ward_returns_binh_thanh() -> None:
    assert resolve_delivery_zone_from_ward("phường 25") == "Bình Thạnh"


def test_resolve_thu_duc_wards_return_thu_duc() -> None:
    assert resolve_delivery_zone_from_ward("Hiệp Bình Chánh") == "Thủ Đức"
    assert resolve_delivery_zone_from_ward("Linh Đông") == "Thủ Đức"


def test_resolve_with_phuong_prefix() -> None:
    assert resolve_delivery_zone_from_ward("Phường Hiệp Bình Chánh") == "Thủ Đức"
    assert resolve_delivery_zone_from_ward("P. Hiệp Bình Chánh") == "Thủ Đức"


def test_outside_delivery_zone_returns_none() -> None:
    assert resolve_delivery_zone_from_ward("Bến Nghé") is None


def test_unknown_ward_returns_none() -> None:
    assert resolve_delivery_zone_from_ward("Phường Không Có Trong Bảng") is None
