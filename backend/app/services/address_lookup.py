"""Lookup helpers for HCMC ward names and delivery zone references."""

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

WARD_PREFIX_PATTERN = re.compile(r"\b(?:phường|phuong|p\.?|p)\s+", re.IGNORECASE)
KHU_PHO_PATTERN = re.compile(r"\b(?:khu\s*pho|kp\.?)\s*(?:so\s*)?(\d{1,3})\b")

KHU_PHO_WARD_DISPLAY = {
    "gia dinh": "Gia Định",
    "binh thanh": "Bình Thạnh",
    "binh loi trung": "Bình Lợi Trung",
    "thanh my tay": "Thạnh Mỹ Tây",
    "binh quoi": "Bình Quới",
    "hiep binh": "Hiệp Bình",
    "tam binh": "Tam Bình",
    "thu duc": "Thủ Đức",
    "linh xuan": "Linh Xuân",
}

KhuPhoValidationStatus = Literal["ok", "missing", "out_of_range"]


@dataclass(frozen=True)
class WardDeliveryZoneMatch:
    """Resolved ward and its delivery zone reference."""

    ward: str
    delivery_zone: str


@dataclass(frozen=True)
class KhuPhoValidationResult:
    """Validation result for ward-specific khu phố ranges."""

    status: KhuPhoValidationStatus
    ward: str | None = None
    ward_display: str | None = None
    khu_pho_max: int | None = None
    khu_pho_number: int | None = None


@dataclass(frozen=True)
class _WardDeliveryZoneConfig:
    ward_display: str
    delivery_zone: str


def resolve_delivery_zone_from_ward(text: str) -> str | None:
    """Return the delivery zone for a known ward mention, or None when unknown."""
    match = resolve_ward_delivery_zone(text)
    return match.delivery_zone if match else None


def resolve_ward_delivery_zone(text: str) -> WardDeliveryZoneMatch | None:
    """Return the matched ward and delivery zone for a known ward mention."""
    normalized_text = _normalize_lookup_key(text)
    if not normalized_text:
        return None

    wards = _load_ward_delivery_zone_map()
    direct = wards.get(normalized_text)
    if direct:
        return WardDeliveryZoneMatch(
            ward=direct.ward_display,
            delivery_zone=direct.delivery_zone,
        )

    text_without_prefixes = _strip_ward_prefixes(normalized_text)
    direct_without_prefix = wards.get(text_without_prefixes)
    if direct_without_prefix:
        return WardDeliveryZoneMatch(
            ward=direct_without_prefix.ward_display,
            delivery_zone=direct_without_prefix.delivery_zone,
        )

    sorted_wards = sorted(
        wards.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for ward, config in sorted_wards:
        if ward.isdigit():
            if _contains_numbered_ward(normalized_text, ward):
                return WardDeliveryZoneMatch(
                    ward=config.ward_display,
                    delivery_zone=config.delivery_zone,
                )
    for ward, config in sorted_wards:
        if ward.isdigit():
            continue
        if _contains_phrase(text_without_prefixes, ward):
            return WardDeliveryZoneMatch(
                ward=config.ward_display,
                delivery_zone=config.delivery_zone,
            )
    return None


def extract_khu_pho_number(text: str) -> int | None:
    """Extract a khu phố number from free-form address text."""
    normalized_text = _normalize_lookup_key(text)
    match = KHU_PHO_PATTERN.search(normalized_text)
    if not match:
        return None
    return int(match.group(1))


def resolve_ward_khu_pho_max(text: str) -> int | None:
    """Return max khu phố for a resolved new ward, or None when not configured."""
    match = resolve_ward_delivery_zone(text)
    if match is None:
        return None
    ward_key = _normalize_lookup_key(match.ward)
    config = _load_ward_khu_pho_map().get(ward_key)
    if config is None:
        return None
    return config.khu_pho_max


def validate_khu_pho(text: str) -> KhuPhoValidationResult:
    """Validate khu phố number for the nine configured new wards."""
    match = resolve_ward_delivery_zone(text)
    if match is None:
        return KhuPhoValidationResult(status="ok")
    ward_key = _normalize_lookup_key(match.ward)
    config = _load_ward_khu_pho_map().get(ward_key)
    if config is None:
        return KhuPhoValidationResult(status="ok")

    khu_pho_number = extract_khu_pho_number(text)
    if khu_pho_number is None:
        return KhuPhoValidationResult(
            status="missing",
            ward=ward_key,
            ward_display=config.ward_display,
            khu_pho_max=config.khu_pho_max,
        )
    if khu_pho_number < 1 or khu_pho_number > config.khu_pho_max:
        return KhuPhoValidationResult(
            status="out_of_range",
            ward=ward_key,
            ward_display=config.ward_display,
            khu_pho_max=config.khu_pho_max,
            khu_pho_number=khu_pho_number,
        )
    return KhuPhoValidationResult(
        status="ok",
        ward=ward_key,
        ward_display=config.ward_display,
        khu_pho_max=config.khu_pho_max,
        khu_pho_number=khu_pho_number,
    )


@lru_cache(maxsize=1)
def _load_ward_delivery_zone_map() -> dict[str, _WardDeliveryZoneConfig]:
    path = Path(__file__).resolve().parents[1] / "data" / "hcmc_ward_district.json"
    raw_data = json.loads(path.read_text(encoding="utf-8"))
    return {
        _normalize_lookup_key(key): _WardDeliveryZoneConfig(
            ward_display=str(key),
            delivery_zone=str(value),
        )
        for key, value in raw_data.items()
    }


@dataclass(frozen=True)
class _WardKhuPhoConfig:
    zone: str
    khu_pho_max: int
    ward_display: str


@lru_cache(maxsize=1)
def _load_ward_khu_pho_map() -> dict[str, _WardKhuPhoConfig]:
    path = Path(__file__).resolve().parents[1] / "data" / "ward_khu_pho.json"
    raw_data = json.loads(path.read_text(encoding="utf-8"))
    configs: dict[str, _WardKhuPhoConfig] = {}
    for key, value in raw_data.items():
        if not isinstance(value, dict):
            continue
        ward_key = _normalize_lookup_key(key)
        configs[ward_key] = _WardKhuPhoConfig(
            zone=str(value["zone"]),
            khu_pho_max=int(value["khu_pho_max"]),
            ward_display=KHU_PHO_WARD_DISPLAY.get(ward_key, key),
        )
    return configs


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).lower().strip()
    return re.sub(r"\s+", " ", normalized)


def _normalize_lookup_key(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text).lower().strip()
    without_marks = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    without_marks = without_marks.replace("đ", "d")
    return re.sub(r"\s+", " ", without_marks)


def _strip_ward_prefixes(text: str) -> str:
    return re.sub(r"\s+", " ", WARD_PREFIX_PATTERN.sub(" ", text)).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _contains_numbered_ward(text: str, ward_number: str) -> bool:
    return (
        re.search(rf"\bphường\s+{re.escape(ward_number)}\b", text) is not None
        or re.search(rf"\bp\.?\s*{re.escape(ward_number)}\b", text) is not None
    )
