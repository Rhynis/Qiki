"""Tests for safety-critical query detection."""

import json
import time
from pathlib import Path

import pytest

from app.rag.safety import SAFETY_EMERGENCY_RESPONSE_VI, SafetyChecker


def safety_cases() -> list[dict[str, object]]:
    path = Path("data/eval/safety_test_suite.json")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("keyword", SafetyChecker.EMERGENCY_KEYWORDS_VI)
@pytest.mark.asyncio
async def test_keyword_detection_all_emergency_phrases(keyword: str) -> None:
    checker = SafetyChecker()

    result = await checker.check_query(f"Tôi cần hỗ trợ vì {keyword} trong bếp")

    assert result.is_emergency is True
    assert result.severity == "critical"
    assert result.suggested_action == "emergency_response"
    assert result.detected_via == "keyword"


@pytest.mark.parametrize(
    "query",
    [
        "Có gas thoát ra từ khu vực bếp",
        "Bình gas bị hỏng nặng sau khi giao",
        "Van gas khóa không được và khí vẫn ra",
        "Dây dẫn gas bị nứt ở đoạn gần bếp",
    ],
)
@pytest.mark.asyncio
async def test_pattern_detection_works(query: str) -> None:
    result = await SafetyChecker().check_query(query)

    assert result.is_emergency is True
    assert result.matched_pattern is not None


@pytest.mark.parametrize(
    "case",
    [case for case in safety_cases() if case["is_safety_critical"] is False],
    ids=lambda case: str(case["id"]),
)
@pytest.mark.asyncio
async def test_normal_queries_not_flagged(case: dict[str, object]) -> None:
    result = await SafetyChecker().check_query(str(case["query"]))

    assert result.is_emergency is False
    assert result.severity == "none"
    assert result.suggested_action == "normal_response"


def test_emergency_response_includes_official_and_store_hotlines() -> None:
    response = SafetyChecker().get_emergency_response()

    assert "114" in response
    assert "115" in response
    assert "090 3026306" in response


def test_emergency_response_is_consistent() -> None:
    checker = SafetyChecker()

    assert checker.get_emergency_response() == checker.get_emergency_response()
    assert checker.get_emergency_response() == SAFETY_EMERGENCY_RESPONSE_VI


def test_emergency_response_is_in_vietnamese() -> None:
    response = SafetyChecker().get_emergency_response()

    assert "CẢNH BÁO AN TOÀN" in response
    assert "KHÔNG tự xử lý" in response
    assert "Bạn có an toàn không?" in response


@pytest.mark.asyncio
async def test_emergency_detection_latency_under_100ms() -> None:
    start = time.monotonic()

    result = await SafetyChecker().check_query("Khẩn cấp, bình gas đang bốc lửa")

    assert result.is_emergency is True
    assert (time.monotonic() - start) * 1000 < 100
