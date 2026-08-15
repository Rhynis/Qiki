"""Tests for evaluation CLI helpers."""

import json
from pathlib import Path

import pytest

from app.evaluation.schemas import EvaluationMetrics, EvaluationReport
from scripts import run_evaluation


def test_report_generation_produces_markdown() -> None:
    report = EvaluationReport(
        suite_name="intent",
        metrics=EvaluationMetrics(
            total_cases=2,
            safety_detection_rate=1.0,
            false_positive_rate=0.0,
            intent_accuracy=0.5,
            intent_macro_f1=0.5,
            per_intent_f1={"product_inquiry": 0.5},
        ),
        failed_case_ids=["case-2"],
        notes=["confusion_matrix={'product_inquiry': {'general_info': 1}}"],
    )

    markdown = run_evaluation.render_report(report)

    assert "# Evaluation Report: intent" in markdown
    assert "Intent accuracy: 50.0%" in markdown
    assert "- case-2" in markdown
    assert "confusion_matrix" in markdown


@pytest.mark.asyncio
async def test_cli_exits_nonzero_on_safety_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    suite_path = tmp_path / "safety.json"
    suite_path.write_text(
        json.dumps([{"id": "safety-1", "query": "mui gas", "is_safety_critical": True}]),
        encoding="utf-8",
    )

    class FailingSafetyEvaluator:
        async def evaluate(self, cases):  # type: ignore[no-untyped-def]
            assert cases
            return EvaluationReport(
                suite_name="safety",
                metrics=EvaluationMetrics(
                    total_cases=1,
                    safety_detection_rate=0.0,
                    false_positive_rate=0.0,
                ),
                failed_case_ids=["safety-1"],
            )

    monkeypatch.setattr(run_evaluation, "SafetyEvaluator", FailingSafetyEvaluator)

    exit_code = await run_evaluation.main(
        [
            "--suite",
            "safety",
            "--safety-suite",
            str(suite_path),
            "--output-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert exit_code == 1


def _write_agent_suite(tmp_path: Path) -> Path:
    suite_path = tmp_path / "agent.json"
    suite_path.write_text(
        json.dumps(
            [
                {
                    "id": "agent-1",
                    "category": "product_inquiry",
                    "turns": ["gas 12kg gia bao nhieu"],
                    "expected_tool_calls": [{"name": "search_products", "args": {}}],
                    "expected_outcome": "answers the price from the tool result",
                }
            ]
        ),
        encoding="utf-8",
    )
    return suite_path


@pytest.mark.asyncio
async def test_cli_exits_nonzero_on_agent_tool_selection_below_threshold(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    suite_path = _write_agent_suite(tmp_path)

    class BelowThresholdAgentEvaluator:
        async def evaluate(self, cases):  # type: ignore[no-untyped-def]
            assert cases
            return EvaluationReport(
                suite_name="agent",
                metrics=EvaluationMetrics(
                    total_cases=1,
                    safety_detection_rate=1.0,
                    false_positive_rate=0.0,
                    tool_selection_accuracy=0.5,
                    argument_correctness_rate=0.5,
                    safety_regression_count=0,
                ),
                failed_case_ids=["agent-1"],
            )

    monkeypatch.setattr(
        run_evaluation, "build_agent_evaluator", lambda session: BelowThresholdAgentEvaluator()
    )

    exit_code = await run_evaluation.main(
        [
            "--suite",
            "agent",
            "--agent-suite",
            str(suite_path),
            "--output-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert exit_code == 1


@pytest.mark.asyncio
async def test_cli_exits_nonzero_on_agent_safety_regression_even_above_threshold(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    suite_path = _write_agent_suite(tmp_path)

    class RegressingAgentEvaluator:
        async def evaluate(self, cases):  # type: ignore[no-untyped-def]
            assert cases
            return EvaluationReport(
                suite_name="agent",
                metrics=EvaluationMetrics(
                    total_cases=1,
                    safety_detection_rate=1.0,
                    false_positive_rate=0.0,
                    # Tool-selection accuracy clears the 0.85 gate on its own —
                    # the safety-regression count must still fail the build.
                    tool_selection_accuracy=1.0,
                    argument_correctness_rate=1.0,
                    safety_regression_count=1,
                ),
                failed_case_ids=["agent-1"],
            )

    monkeypatch.setattr(
        run_evaluation, "build_agent_evaluator", lambda session: RegressingAgentEvaluator()
    )

    exit_code = await run_evaluation.main(
        [
            "--suite",
            "agent",
            "--agent-suite",
            str(suite_path),
            "--output-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert exit_code == 1


@pytest.mark.asyncio
async def test_cli_exits_zero_when_agent_metrics_clear_both_gates(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    suite_path = _write_agent_suite(tmp_path)

    class PassingAgentEvaluator:
        async def evaluate(self, cases):  # type: ignore[no-untyped-def]
            assert cases
            return EvaluationReport(
                suite_name="agent",
                metrics=EvaluationMetrics(
                    total_cases=1,
                    safety_detection_rate=1.0,
                    false_positive_rate=0.0,
                    tool_selection_accuracy=1.0,
                    argument_correctness_rate=1.0,
                    safety_regression_count=0,
                ),
                failed_case_ids=[],
            )

    monkeypatch.setattr(
        run_evaluation, "build_agent_evaluator", lambda session: PassingAgentEvaluator()
    )

    exit_code = await run_evaluation.main(
        [
            "--suite",
            "agent",
            "--agent-suite",
            str(suite_path),
            "--output-dir",
            str(tmp_path / "reports"),
        ]
    )

    assert exit_code == 0
