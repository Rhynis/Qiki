"""Tests for the quantization-quality harness (mock mode only, no GPU/network)."""

import argparse
from pathlib import Path

import pytest

from app.evaluation.schemas import TestCase
from bench.mock_provider import MockLLMProvider
from bench.quality_quantization import (
    RESULTS_HEADER,
    RESULTS_SEPARATOR,
    QualitySummary,
    append_result_row,
    build_providers,
    keyword_recall,
    load_cases,
    main,
    score_provider,
)


def test_keyword_recall_all_keywords_present() -> None:
    assert keyword_recall("Petrolimex 12kg giá 450000 đồng", ["Petrolimex", "12kg"]) == 1.0


def test_keyword_recall_partial_match() -> None:
    assert keyword_recall("Petrolimex 12kg", ["Petrolimex", "6kg"]) == 0.5


def test_keyword_recall_no_keywords_is_trivially_full_recall() -> None:
    assert keyword_recall("anything", []) == 1.0


def test_keyword_recall_is_case_insensitive() -> None:
    assert keyword_recall("PETROLIMEX 12KG", ["petrolimex", "12kg"]) == 1.0


def test_load_cases_reads_rag_test_suite() -> None:
    cases = load_cases(Path("data/eval/rag_test_suite.json"))

    assert len(cases) > 0
    assert all(isinstance(case, TestCase) for case in cases)
    assert all(case.expected_keywords for case in cases)


def test_build_providers_mock_mode_returns_two_mock_providers() -> None:
    args = argparse.Namespace(mode="mock")

    base, awq = build_providers(args)

    assert isinstance(base, MockLLMProvider)
    assert isinstance(awq, MockLLMProvider)
    assert base.response_text != awq.response_text


async def test_score_provider_averages_keyword_recall_across_cases() -> None:
    provider = MockLLMProvider(response_text="Petrolimex 12kg giá 450000 đồng, còn hàng.")
    cases = [
        TestCase(id="c1", query="q1", expected_keywords=["Petrolimex", "12kg"]),
        TestCase(id="c2", query="q2", expected_keywords=["6kg"]),
    ]

    summary = await score_provider(provider, cases)

    assert summary.cases == 2
    # c1: 2/2 keywords hit, c2: 0/1 -> mean = (1.0 + 0.0) / 2
    assert summary.mean_keyword_recall == pytest.approx(0.5)


async def test_awq_mock_scores_lower_than_base_mock_on_real_case_set() -> None:
    args = argparse.Namespace(mode="mock")
    base, awq = build_providers(args)
    cases = load_cases(Path("data/eval/rag_test_suite.json"))

    base_summary = await score_provider(base, cases)
    awq_summary = await score_provider(awq, cases)

    assert awq_summary.mean_keyword_recall <= base_summary.mean_keyword_recall


def test_append_result_row_seeds_file_when_missing(tmp_path: Path) -> None:
    results_path = tmp_path / "RESULTS.md"
    base = QualitySummary(label="mock", model="base-mock", cases=5, mean_keyword_recall=0.8)
    awq = QualitySummary(label="mock", model="awq-mock", cases=5, mean_keyword_recall=0.6)

    append_result_row(results_path, base, awq)

    text = results_path.read_text(encoding="utf-8")
    assert RESULTS_HEADER in text
    assert RESULTS_SEPARATOR in text
    assert "base-mock" in text
    assert "awq-mock" in text


def test_append_result_row_inserts_newest_row_under_existing_header(tmp_path: Path) -> None:
    results_path = tmp_path / "RESULTS.md"
    results_path.write_text(
        f"## Quality-after-quantization\n\n{RESULTS_HEADER}\n{RESULTS_SEPARATOR}\n",
        encoding="utf-8",
    )
    base = QualitySummary(label="mock", model="base-mock", cases=5, mean_keyword_recall=0.8)
    awq_1 = QualitySummary(label="mock", model="awq-run-1", cases=5, mean_keyword_recall=0.6)
    awq_2 = QualitySummary(label="mock", model="awq-run-2", cases=5, mean_keyword_recall=0.5)

    append_result_row(results_path, base, awq_1)
    append_result_row(results_path, base, awq_2)

    lines = results_path.read_text(encoding="utf-8").splitlines()
    separator_index = lines.index(RESULTS_SEPARATOR)
    assert "awq-run-2" in lines[separator_index + 1]
    assert "awq-run-1" in lines[separator_index + 2]
    assert lines.count(RESULTS_HEADER) == 1


async def test_main_runs_end_to_end_in_mock_mode(tmp_path: Path) -> None:
    results_path = tmp_path / "RESULTS.md"

    exit_code = await main(
        [
            "--mode",
            "mock",
            "--results-path",
            str(results_path),
        ]
    )

    assert exit_code == 0
    assert results_path.exists()
    assert "base-mock" in results_path.read_text(encoding="utf-8")
