"""Tests for HCMC ward to delivery zone lookup."""

from app.services.address_lookup import (
    extract_khu_pho_number,
    resolve_delivery_zone_from_ward,
    resolve_ward_khu_pho_max,
    validate_khu_pho,
)


def test_resolve_binh_thanh_numbered_ward_returns_binh_thanh() -> None:
    assert resolve_delivery_zone_from_ward("phường 25, quận Bình Thạnh") == "Bình Thạnh"


def test_resolve_thu_duc_wards_return_thu_duc() -> None:
    assert resolve_delivery_zone_from_ward("Hiệp Bình Chánh") == "Thủ Đức"
    assert resolve_delivery_zone_from_ward("Linh Đông") == "Thủ Đức"


def test_linh_chieu_in_thu_duc() -> None:
    assert resolve_delivery_zone_from_ward("linh chiểu") == "Thủ Đức"
    assert resolve_delivery_zone_from_ward("phường linh chiểu") == "Thủ Đức"


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


def test_removed_thu_duc_wards_are_out_of_area() -> None:
    # Thủ Đức delivery wards were narrowed to the real served set; the wards below
    # were dropped and must no longer resolve to a delivery zone.
    for ward in (
        "Thảo Điền",
        "An Phú",
        "Cát Lái",
        "Thủ Thiêm",
        "Tăng Nhơn Phú A",
    ):
        assert resolve_delivery_zone_from_ward(ward) is None


def test_kept_thu_duc_wards_still_resolve() -> None:
    for ward in ("Bình Thọ", "Trường Thọ", "Linh Tây", "Tam Phú", "Hiệp Bình Phước"):
        assert resolve_delivery_zone_from_ward(ward) == "Thủ Đức"


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


def test_numbered_ward_with_binh_thanh_context_in() -> None:
    assert resolve_delivery_zone_from_ward("12 Nguyễn X, Phường 12, Bình Thạnh") == "Bình Thạnh"


def test_inline_numbered_ward_binh_thanh_in() -> None:
    assert (
        resolve_delivery_zone_from_ward("15 Điện Biên Phủ, P. 25, quận Bình Thạnh") == "Bình Thạnh"
    )


def test_numbered_ward_conflicting_district_out() -> None:
    assert resolve_delivery_zone_from_ward("Phường 7, Quận 7") is None
    assert resolve_delivery_zone_from_ward("Phường 12, Gò Vấp") is None


def test_bare_numbered_ward_no_district_not_binh_thanh() -> None:
    assert resolve_delivery_zone_from_ward("Phường 12") is None
