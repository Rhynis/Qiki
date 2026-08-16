"""Quality-after-quantization harness: base model vs AWQ model, same prompt set.

Runs a fixed Vietnamese prompt set (the existing RAG eval golden set,
``data/eval/rag_test_suite.json``, which already ships ``expected_keywords``
per case) through a base checkpoint and its AWQ-quantized counterpart, then
reports the keyword-recall delta. This is the "quality, not just speed" half
of the vLLM story — the ADR (docs/adr/0003) is explicit that a latency win
that silently degrades answers isn't a win.

The actual GPU run (two live vLLM endpoints, one per checkpoint) is the
owner's job. This script + ``--mode mock`` gives it a real, deterministic,
GPU-free code path to exercise in CI.

Run against two live vLLM endpoints:
    python -m bench.quality_quantization --mode vllm \\
        --base-url http://gpu-host:8000/v1 --base-model Qwen/Qwen3-4B-Instruct \\
        --awq-url http://gpu-host:8001/v1 --awq-model Qwen/Qwen3-4B-Instruct-AWQ

Run in CI (no GPU, no live server):
    python -m bench.quality_quantization --mode mock
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation.schemas import TestCase  # noqa: E402
from app.llm.base import BaseLLMProvider  # noqa: E402
from app.llm.providers.vllm_provider import VLLMProvider  # noqa: E402
from bench.mock_provider import MockLLMProvider  # noqa: E402

DEFAULT_CASES_PATH = Path("data/eval/rag_test_suite.json")

# Deliberately different response richness so `--mode mock` exercises a real
# (non-zero) delta: the "awq" mock simulates the kind of detail loss a heavy
# quantization regression would produce, without claiming any real accuracy
# number — the owner's live GPU run is what fills in RESULTS.md for real.
MOCK_BASE_TEXT = (
    "Petrolimex 12kg giá 450000 đồng, còn hàng. Bình 6kg giá 250000 đồng. "
    "Vui lòng kiểm tra van trước khi lắp bình gas 45kg cho công nghiệp."
)
MOCK_AWQ_TEXT = "Petrolimex 12kg giá 450000 đồng, còn hàng."


@dataclass
class QualitySummary:
    """Aggregated keyword-recall score for one model over the case set."""

    label: str
    model: str
    cases: int
    mean_keyword_recall: float


def load_cases(path: Path) -> list[TestCase]:
    """Load the RAG golden-set cases used as the fixed prompt set."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [TestCase.model_validate(item) for item in raw]


def keyword_recall(text: str, keywords: list[str]) -> float:
    """Fraction of expected_keywords present (case-insensitive) in text."""
    if not keywords:
        return 1.0
    lowered = text.lower()
    hits = sum(1 for keyword in keywords if keyword.lower() in lowered)
    return hits / len(keywords)


async def score_provider(provider: BaseLLMProvider, cases: list[TestCase]) -> QualitySummary:
    """Generate an answer per case and average its keyword-recall score."""
    scores: list[float] = []
    for case in cases:
        response = await provider.generate(prompt=case.query, max_tokens=256)
        scores.append(keyword_recall(response.text, case.expected_keywords))
    mean_score = sum(scores) / len(scores) if scores else 0.0
    return QualitySummary(
        label=provider.provider_name,
        model=provider.model,
        cases=len(cases),
        mean_keyword_recall=mean_score,
    )


def build_providers(args: argparse.Namespace) -> tuple[BaseLLMProvider, BaseLLMProvider]:
    """Build the (base, awq) provider pair for the requested mode."""
    if args.mode == "mock":
        return (
            MockLLMProvider(model="base-mock", response_text=MOCK_BASE_TEXT),
            MockLLMProvider(model="awq-mock", response_text=MOCK_AWQ_TEXT),
        )
    base = VLLMProvider(base_url=args.base_url, model=args.base_model)
    awq = VLLMProvider(base_url=args.awq_url, model=args.awq_model)
    return base, awq


RESULTS_SECTION_HEADING = "## Quality-after-quantization"
RESULTS_HEADER = "| Base model | AWQ model | Cases | Base recall | AWQ recall | Delta |"
RESULTS_SEPARATOR = "|---|---|---|---|---|---|"


def render_row(base: QualitySummary, awq: QualitySummary) -> str:
    """Render one Markdown row comparing base vs AWQ keyword recall."""
    delta = awq.mean_keyword_recall - base.mean_keyword_recall
    return (
        f"| {base.model} | {awq.model} | {base.cases} "
        f"| {base.mean_keyword_recall:.1%} | {awq.mean_keyword_recall:.1%} | {delta:+.1%} |"
    )


def append_result_row(results_path: Path, base: QualitySummary, awq: QualitySummary) -> None:
    """Insert this run's comparison row as the newest row under the table header.

    Mirrors ``serving_benchmark.append_result_row``'s marker-based insertion
    so both scripts can share the same RESULTS.md file without stepping on
    each other's tables regardless of section order.
    """
    marker = f"{RESULTS_HEADER}\n{RESULTS_SEPARATOR}\n"
    row = render_row(base, awq)
    text = results_path.read_text(encoding="utf-8") if results_path.exists() else ""
    if marker in text:
        text = text.replace(marker, marker + row + "\n", 1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"\n{RESULTS_SECTION_HEADING}\n\n{marker}{row}\n"
    results_path.write_text(text, encoding="utf-8")


async def main(argv: list[str] | None = None) -> int:
    """Run the quality-after-quantization comparison and print + persist results."""
    parser = argparse.ArgumentParser(description="Qiki quantization quality harness")
    parser.add_argument("--mode", choices=["mock", "vllm"], default="mock")
    parser.add_argument("--base-url", default="http://localhost:8000/v1")
    parser.add_argument("--base-model", default="Qwen/Qwen3-4B-Instruct")
    parser.add_argument("--awq-url", default="http://localhost:8001/v1")
    parser.add_argument("--awq-model", default="Qwen/Qwen3-4B-Instruct-AWQ")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--results-path", type=Path, default=Path("RESULTS.md"))
    args = parser.parse_args(argv)

    cases = load_cases(args.cases)
    base_provider, awq_provider = build_providers(args)

    base_summary = await score_provider(base_provider, cases)
    awq_summary = await score_provider(awq_provider, cases)

    print(f"Base  ({base_summary.model}): {base_summary.mean_keyword_recall:.1%} keyword recall")
    print(f"AWQ   ({awq_summary.model}): {awq_summary.mean_keyword_recall:.1%} keyword recall")
    print(f"Delta: {awq_summary.mean_keyword_recall - base_summary.mean_keyword_recall:+.1%}")
    print(f"\n{RESULTS_HEADER}\n{RESULTS_SEPARATOR}\n{render_row(base_summary, awq_summary)}")

    append_result_row(args.results_path, base_summary, awq_summary)
    print(f"\nAppended run to {args.results_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
