"""Tests for the serving benchmark harness (mock provider only, no GPU/network)."""

from pathlib import Path

from app.core.config import Settings
from bench.mock_provider import MockLLMProvider
from bench.serving_benchmark import (
    RESULTS_HEADER,
    RESULTS_SEPARATOR,
    BenchmarkSummary,
    append_result_row,
    build_provider,
    derive_self_hosted_cost_per_1m_tokens,
    main,
    percentile,
    run_benchmark,
)


def test_percentile_empty_list_returns_zero() -> None:
    assert percentile([], 95) == 0.0


def test_percentile_single_value_returns_that_value() -> None:
    assert percentile([42.0], 50) == 42.0


def test_percentile_p50_of_known_distribution() -> None:
    assert percentile([10.0, 20.0, 30.0], 50) == 20.0


def test_percentile_p100_returns_max() -> None:
    assert percentile([1.0, 5.0, 9.0], 100) == 9.0


def test_build_provider_mock_returns_mock_provider() -> None:
    provider = build_provider("mock", Settings())

    assert isinstance(provider, MockLLMProvider)
    assert provider.provider_name == "mock"


async def test_run_benchmark_against_mock_provider_produces_summary() -> None:
    provider = MockLLMProvider(chunk_delay_s=0.0, first_token_delay_s=0.0)

    summary = await run_benchmark(
        provider=provider,
        prompt="test prompt",
        requests=6,
        concurrency=3,
        max_tokens=64,
    )

    assert summary.provider == "mock"
    assert summary.requests == 6
    assert summary.concurrency == 3
    assert len(summary.results) == 6
    assert summary.throughput_tokens_per_s > 0
    assert summary.p50_latency_ms >= 0
    assert summary.p95_latency_ms >= summary.p50_latency_ms
    assert summary.cost_per_1m_tokens_usd == 0.0  # mock is priced free


def test_derive_self_hosted_cost_scales_inversely_with_throughput() -> None:
    slow_cost = derive_self_hosted_cost_per_1m_tokens(10.0)
    fast_cost = derive_self_hosted_cost_per_1m_tokens(100.0)

    assert slow_cost is not None
    assert fast_cost is not None
    assert fast_cost < slow_cost


def test_derive_self_hosted_cost_is_none_when_throughput_is_zero() -> None:
    assert derive_self_hosted_cost_per_1m_tokens(0.0) is None


def _summary(**overrides: object) -> BenchmarkSummary:
    defaults: dict[str, object] = {
        "provider": "mock",
        "model": "mock-model",
        "requests": 10,
        "concurrency": 2,
        "p50_latency_ms": 100.0,
        "p95_latency_ms": 150.0,
        "p99_latency_ms": 180.0,
        "ttft_p50_ms": 20.0,
        "throughput_tokens_per_s": 42.0,
        "cost_per_1m_tokens_usd": 0.0,
    }
    defaults.update(overrides)
    return BenchmarkSummary(**defaults)  # type: ignore[arg-type]


def test_append_result_row_seeds_file_when_missing(tmp_path: Path) -> None:
    results_path = tmp_path / "RESULTS.md"

    append_result_row(results_path, _summary())

    text = results_path.read_text(encoding="utf-8")
    assert RESULTS_HEADER in text
    assert RESULTS_SEPARATOR in text
    assert "mock" in text


def test_append_result_row_inserts_newest_row_under_existing_header(tmp_path: Path) -> None:
    results_path = tmp_path / "RESULTS.md"
    results_path.write_text(
        f"## Serving benchmark\n\n{RESULTS_HEADER}\n{RESULTS_SEPARATOR}\n",
        encoding="utf-8",
    )

    append_result_row(results_path, _summary(model="first-run"))
    append_result_row(results_path, _summary(model="second-run"))

    lines = results_path.read_text(encoding="utf-8").splitlines()
    header_index = lines.index(RESULTS_HEADER)
    separator_index = lines.index(RESULTS_SEPARATOR)
    assert separator_index == header_index + 1
    assert "second-run" in lines[separator_index + 1]
    assert "first-run" in lines[separator_index + 2]
    # Exactly one header/separator pair — rows were inserted, not re-seeded.
    assert lines.count(RESULTS_HEADER) == 1


async def test_main_runs_end_to_end_against_mock_provider(tmp_path: Path) -> None:
    results_path = tmp_path / "RESULTS.md"

    exit_code = await main(
        [
            "--provider",
            "mock",
            "--requests",
            "3",
            "--concurrency",
            "2",
            "--results-path",
            str(results_path),
        ]
    )

    assert exit_code == 0
    assert results_path.exists()
    assert "mock" in results_path.read_text(encoding="utf-8")
