"""Tests for HCMC ward to delivery zone lookup."""

from app.services.address_lookup import (
    extract_khu_pho_number,
    resolve_delivery_zone_from_ward,
    resolve_ward_khu_pho_max,
    validate_khu_pho,
)


def test_resolve_binh_thanh_numbered_ward_returns_binh_thanh() -> None:
    assert resolve_delivery_zone_from_ward("phường 25") == "Bình Thạnh"


def test_resolve_thu_duc_wards_return_thu_duc() -> None:
    assert resolve_delivery_zone_from_ward("Hiệp Bình Chánh") == "Thủ Đức"
    assert resolve_delivery_zone_from_ward("Linh Đông") == "Thủ Đức"


def test_resolve_new_hiep_binh_ward_returns_thu_duc() -> None:
    assert resolve_delivery_zone_from_ward("Hiệp Bình") == "Thủ Đức"
    assert resolve_delivery_zone_from_ward("Phường Hiệp Bình") == "Thủ Đức"
    assert resolve_delivery_zone_from_ward("phuong hiep binh") == "Thủ Đức"


def test_new_ward_names_resolve_zone() -> None:
    assert resolve_delivery_zone_from_ward("Thạnh Mỹ Tây") == "Bình Thạnh"
    assert resolve_delivery_zone_from_ward("Linh Xuân") == "Thủ Đức"
    assert resolve_ward_khu_pho_max("P. Thạnh Mỹ Tây") == 76
    assert resolve_ward_khu_pho_max("phuong linh xuan") == 63


def test_resolve_with_phuong_prefix() -> None:
    assert resolve_delivery_zone_from_ward("Phường Hiệp Bình Chánh") == "Thủ Đức"
    assert resolve_delivery_zone_from_ward("P. Hiệp Bình Chánh") == "Thủ Đức"


def test_outside_delivery_zone_returns_none() -> None:
    assert resolve_delivery_zone_from_ward("Bến Nghé") is None


def test_unknown_ward_returns_none() -> None:
    assert resolve_delivery_zone_from_ward("Phường Không Có Trong Bảng") is None


def test_extract_khu_pho_number_variants() -> None:
    assert extract_khu_pho_number("Khu phố 36, Phường Hiệp Bình") == 36
    assert extract_khu_pho_number("kp.12 P. Linh Xuân") == 12
    assert extract_khu_pho_number("kp5 Phường Tam Bình") == 5


def test_validate_khu_pho_range() -> None:
    valid = validate_khu_pho("15 đường số 5, khu phố 36, P. Hiệp Bình")
    assert valid.status == "ok"
    assert valid.khu_pho_number == 36

    missing = validate_khu_pho("15 đường số 5, P. Hiệp Bình")
    assert missing.status == "missing"
    assert missing.khu_pho_max == 91

    out_of_range = validate_khu_pho("15 đường số 5, kp 95, P. Hiệp Bình")
    assert out_of_range.status == "out_of_range"
    assert out_of_range.khu_pho_max == 91


def test_old_ward_alias_skips_khu_pho_validation() -> None:
    assert validate_khu_pho("15 đường số 5, Phường Hiệp Bình Chánh").status == "ok"
