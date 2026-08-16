"""Serving benchmark: concurrent load through the shared LLM provider abstraction.

Compares vLLM (self-hosted), Ollama (local), Gemini, and Groq (API) on the
same metrics — p50/p95/p99 latency, throughput, time-to-first-token, and cost
per 1M tokens — by driving each one through ``BaseLLMProvider.stream()``, the
exact method ``responder.py`` calls in production. No provider-specific
logic lives here; swapping ``--provider`` is the whole comparison.

Run against a live server:
    python -m bench.serving_benchmark --provider vllm --requests 50 --concurrency 5
    python -m bench.serving_benchmark --provider ollama --requests 20

Run in CI (no GPU, no live server):
    python -m bench.serving_benchmark --provider mock --requests 50
"""

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings  # noqa: E402
from app.llm.base import BaseLLMProvider  # noqa: E402
from app.llm.factory import LLMProviderFactory  # noqa: E402
from bench.mock_provider import MockLLMProvider  # noqa: E402

DEFAULT_PROMPT = "Bình gas 12kg giá bao nhiêu và giao trong bao lâu?"

# Illustrative public API rates (USD per 1M tokens, blended input+output), as
# of the writing of this harness — the owner should refresh these before
# treating RESULTS.md as authoritative. Self-hosted cost is *not* looked up
# here: it's derived per-run from GPU_HOUR_USD and the measured throughput,
# since it depends on the actual GPU rented and the actual tokens/s achieved.
API_COST_PER_1M_TOKENS_USD: dict[str, float] = {
    "gemini": 0.15,  # gemini-2.0-flash-exp blended estimate
    "groq": 0.59,  # llama-3.3-70b-versatile blended estimate
    "ollama": 0.0,  # local process, no per-token API charge (compute cost not modeled)
    "mock": 0.0,
}
# On-demand hourly rate for a single mid-tier inference GPU (e.g. RunPod L4).
# Used only to derive vLLM's cost/1M tokens from measured throughput below.
GPU_HOUR_USD = 0.79


@dataclass
class RequestResult:
    """Outcome of one benchmarked request."""

    latency_ms: float
    ttft_ms: float
    completion_tokens: int


@dataclass
class BenchmarkSummary:
    """Aggregated benchmark metrics for one provider run."""

    provider: str
    model: str
    requests: int
    concurrency: int
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    ttft_p50_ms: float
    throughput_tokens_per_s: float
    cost_per_1m_tokens_usd: float | None
    results: list[RequestResult] = field(default_factory=list, repr=False)


def percentile(values: list[float], p: float) -> float:
    """Return the p-th percentile (0-100) of a list using nearest-rank interpolation."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (p / 100) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def build_provider(name: str, settings: Settings) -> BaseLLMProvider:
    """Build the provider under test via the existing factory (or a mock)."""
    if name == "mock":
        return MockLLMProvider()
    return LLMProviderFactory.create(provider_name=name, settings=settings)


async def _run_one(
    provider: BaseLLMProvider,
    prompt: str,
    max_tokens: int,
    semaphore: asyncio.Semaphore,
) -> RequestResult:
    async with semaphore:
        start = time.monotonic()
        ttft_s: float | None = None
        accumulated = ""
        total_tokens: int | None = None
        async for chunk in provider.stream(prompt=prompt, max_tokens=max_tokens):
            if ttft_s is None and chunk.delta:
                ttft_s = time.monotonic() - start
            accumulated = chunk.accumulated_text
            if chunk.total_tokens is not None:
                total_tokens = chunk.total_tokens
        latency_s = time.monotonic() - start
        completion_tokens = total_tokens or provider.estimate_tokens(accumulated)
        return RequestResult(
            latency_ms=latency_s * 1000,
            ttft_ms=(ttft_s or latency_s) * 1000,
            completion_tokens=completion_tokens,
        )


async def run_benchmark(
    provider: BaseLLMProvider,
    prompt: str,
    requests: int,
    concurrency: int,
    max_tokens: int,
) -> BenchmarkSummary:
    """Drive ``requests`` calls (bounded to ``concurrency`` in flight) and summarize."""
    semaphore = asyncio.Semaphore(concurrency)
    wall_start = time.monotonic()
    results = await asyncio.gather(
        *(_run_one(provider, prompt, max_tokens, semaphore) for _ in range(requests))
    )
    wall_elapsed_s = time.monotonic() - wall_start

    latencies = [r.latency_ms for r in results]
    ttfts = [r.ttft_ms for r in results]
    total_tokens = sum(r.completion_tokens for r in results)
    throughput = total_tokens / wall_elapsed_s if wall_elapsed_s > 0 else 0.0

    cost = API_COST_PER_1M_TOKENS_USD.get(provider.provider_name)
    if provider.provider_name == "vllm":
        cost = derive_self_hosted_cost_per_1m_tokens(throughput)

    return BenchmarkSummary(
        provider=provider.provider_name,
        model=provider.model,
        requests=requests,
        concurrency=concurrency,
        p50_latency_ms=percentile(latencies, 50),
        p95_latency_ms=percentile(latencies, 95),
        p99_latency_ms=percentile(latencies, 99),
        ttft_p50_ms=percentile(ttfts, 50),
        throughput_tokens_per_s=throughput,
        cost_per_1m_tokens_usd=cost,
        results=list(results),
    )


def derive_self_hosted_cost_per_1m_tokens(throughput_tokens_per_s: float) -> float | None:
    """Amortize GPU_HOUR_USD over measured throughput to estimate self-host cost.

    cost/1M tokens = (GPU $/hour / 3600 s/hour) / (tokens/s) * 1,000,000 tokens.
    Undefined (None) when throughput is zero (nothing was measured, e.g. all
    requests failed) — reporting 0.0 there would misleadingly read as "free".
    """
    if throughput_tokens_per_s <= 0:
        return None
    cost_per_second = GPU_HOUR_USD / 3600
    return (cost_per_second / throughput_tokens_per_s) * 1_000_000


def format_cost(cost: float | None) -> str:
    """Render a cost value for the Markdown table, or an em dash when unknown."""
    return f"{cost:.4f}" if cost is not None else "—"


def render_row(summary: BenchmarkSummary) -> str:
    """Render one Markdown table row for a benchmark summary."""
    return (
        f"| {summary.provider} | {summary.model} | {summary.requests} | {summary.concurrency} "
        f"| {summary.p50_latency_ms:.0f} | {summary.p95_latency_ms:.0f} "
        f"| {summary.p99_latency_ms:.0f} | {summary.ttft_p50_ms:.0f} "
        f"| {summary.throughput_tokens_per_s:.1f} "
        f"| {format_cost(summary.cost_per_1m_tokens_usd)} |"
    )


RESULTS_HEADER = (
    "| Provider | Model | Requests | Concurrency | p50 (ms) | p95 (ms) | p99 (ms) "
    "| TTFT p50 (ms) | Throughput (tok/s) | Cost / 1M tok (USD) |"
)
RESULTS_SEPARATOR = "|---|---|---|---|---|---|---|---|---|---|"
RUNS_SECTION_HEADING = "## Serving benchmark"


def append_result_row(results_path: Path, summary: BenchmarkSummary) -> None:
    """Insert one benchmark run as the newest row right under RESULTS.md's table header.

    Locates the exact header+separator pair (seeding it, under
    ``RUNS_SECTION_HEADING``, if the file doesn't have it yet) and inserts
    the new row immediately after — so results stay newest-first regardless
    of how many other sections/tables share the file.
    """
    marker = f"{RESULTS_HEADER}\n{RESULTS_SEPARATOR}\n"
    row = render_row(summary)
    if results_path.exists():
        text = results_path.read_text(encoding="utf-8")
    else:
        text = ""
    if marker in text:
        text = text.replace(marker, marker + row + "\n", 1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"\n{RUNS_SECTION_HEADING}\n\n{marker}{row}\n"
    results_path.write_text(text, encoding="utf-8")


def render_summary_text(summary: BenchmarkSummary) -> str:
    """Render a human-readable summary for terminal output."""
    return (
        f"Provider: {summary.provider} ({summary.model})\n"
        f"Requests: {summary.requests}, concurrency: {summary.concurrency}\n"
        f"Latency p50/p95/p99 (ms): {summary.p50_latency_ms:.0f} / "
        f"{summary.p95_latency_ms:.0f} / {summary.p99_latency_ms:.0f}\n"
        f"TTFT p50 (ms): {summary.ttft_p50_ms:.0f}\n"
        f"Throughput (tok/s): {summary.throughput_tokens_per_s:.1f}\n"
        f"Cost / 1M tokens (USD): {format_cost(summary.cost_per_1m_tokens_usd)}\n\n"
        f"{RESULTS_HEADER}\n{RESULTS_SEPARATOR}\n{render_row(summary)}"
    )


async def main(argv: list[str] | None = None) -> int:
    """Run the serving benchmark for one provider and print + persist results."""
    parser = argparse.ArgumentParser(description="Qiki LLM serving benchmark")
    parser.add_argument(
        "--provider",
        choices=["mock", "ollama", "vllm", "gemini", "groq"],
        default="mock",
    )
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT)
    parser.add_argument("--results-path", type=Path, default=Path("RESULTS.md"))
    args = parser.parse_args(argv)

    settings = Settings()
    provider = build_provider(args.provider, settings)
    summary = await run_benchmark(
        provider=provider,
        prompt=args.prompt,
        requests=args.requests,
        concurrency=args.concurrency,
        max_tokens=args.max_tokens,
    )

    print(render_summary_text(summary))
    append_result_row(args.results_path, summary)
    print(f"\nAppended run to {args.results_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
