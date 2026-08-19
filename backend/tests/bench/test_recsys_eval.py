"""Tests for the simulated recommendation eval harness (no live DB required
except for the deliberately-mocked CLI wiring tests)."""

import random
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.schemas.product import BestSellerProduct, ProductResponse
from bench import recsys_eval


def make_product(
    *,
    sku: str,
    name: str,
    brand: str = "Saigon Petro",
    category: str = "gas",
    size_kg: str = "12",
) -> ProductResponse:
    now = datetime.now(UTC)
    return ProductResponse(
        id=uuid4(),
        sku=sku,
        name=name,
        brand=brand,
        size_kg=Decimal(size_kg),
        category=category,  # type: ignore[arg-type]
        unit="kg" if category == "gas" else "lít",  # type: ignore[arg-type]
        price=Decimal("500000"),
        stock_quantity=10,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


CATALOG = [
    make_product(sku="A1", name="A1", brand="Saigon Petro", size_kg="12"),
    make_product(sku="A2", name="A2", brand="Saigon Petro", size_kg="6"),
    make_product(sku="B1", name="B1", brand="Elf Gas", size_kg="12"),
    make_product(sku="W1", name="W1", brand="Vihawa", category="nuoc_uong", size_kg="20"),
    make_product(sku="W2", name="W2", brand="Hoàn Hảo", category="nuoc_uong", size_kg="20"),
]


class TestRankMetrics:
    def test_recall_is_1_when_found_else_0(self) -> None:
        assert recsys_eval.recall_at_rank(1) == 1.0
        assert recsys_eval.recall_at_rank(5) == 1.0
        assert recsys_eval.recall_at_rank(None) == 0.0

    def test_ndcg_decreases_with_rank(self) -> None:
        assert recsys_eval.ndcg_at_rank(1) == 1.0
        assert recsys_eval.ndcg_at_rank(2) < recsys_eval.ndcg_at_rank(1)
        assert recsys_eval.ndcg_at_rank(None) == 0.0

    def test_average_precision_is_reciprocal_rank(self) -> None:
        assert recsys_eval.average_precision_at_rank(1) == 1.0
        assert recsys_eval.average_precision_at_rank(4) == pytest.approx(0.25)
        assert recsys_eval.average_precision_at_rank(None) == 0.0


class TestRelatedCandidates:
    def test_prefers_same_brand(self) -> None:
        seed = CATALOG[0]  # A1, Saigon Petro
        related = recsys_eval._related_candidates(seed, CATALOG)
        assert related == [CATALOG[1]]  # A2, same brand

    def test_gas_with_no_same_brand_falls_back_to_water(self) -> None:
        seed = CATALOG[2]  # B1, Elf Gas (only Elf product)
        related = recsys_eval._related_candidates(seed, CATALOG)
        assert {p.id for p in related} == {CATALOG[3].id, CATALOG[4].id}

    def test_water_falls_back_to_other_water_brand(self) -> None:
        seed = CATALOG[3]  # W1, Vihawa
        related = recsys_eval._related_candidates(seed, CATALOG)
        assert related == [CATALOG[4]]  # W2, Hoàn Hảo


class TestSimulateSessions:
    def test_deterministic_for_the_same_seed(self) -> None:
        sessions_a = recsys_eval.simulate_sessions(random.Random(42), CATALOG, 20)
        sessions_b = recsys_eval.simulate_sessions(random.Random(42), CATALOG, 20)

        assert [(s.seed.id, s.ground_truth.id) for s in sessions_a] == [
            (s.seed.id, s.ground_truth.id) for s in sessions_b
        ]

    def test_different_seeds_can_diverge(self) -> None:
        sessions_a = recsys_eval.simulate_sessions(random.Random(1), CATALOG, 20)
        sessions_b = recsys_eval.simulate_sessions(random.Random(2), CATALOG, 20)

        pairs_a = [(s.seed.id, s.ground_truth.id) for s in sessions_a]
        pairs_b = [(s.seed.id, s.ground_truth.id) for s in sessions_b]
        assert pairs_a != pairs_b

    def test_ground_truth_is_never_the_seed_itself(self) -> None:
        sessions = recsys_eval.simulate_sessions(random.Random(7), CATALOG, 50)
        assert all(s.seed.id != s.ground_truth.id for s in sessions)


class TestEvaluateWarmSessions:
    async def test_recall_1_when_the_ranker_always_returns_ground_truth_first(self) -> None:
        sessions = [recsys_eval.SimulatedSession(seed=CATALOG[0], ground_truth=CATALOG[1])]
        recommendation_service = AsyncMock()

        class _Candidate:
            def __init__(self, product: ProductResponse) -> None:
                self.product = product

        recommendation_service.recommend = AsyncMock(return_value=[_Candidate(CATALOG[1])])

        metrics = await recsys_eval.evaluate_warm_sessions(
            recommendation_service, sessions, CATALOG, k=5
        )

        assert metrics.recall_at_k == 1.0
        assert metrics.ndcg_at_k == 1.0
        assert metrics.map_score == 1.0

    async def test_recall_0_when_ground_truth_never_appears(self) -> None:
        sessions = [recsys_eval.SimulatedSession(seed=CATALOG[0], ground_truth=CATALOG[1])]
        recommendation_service = AsyncMock()

        class _Candidate:
            def __init__(self, product: ProductResponse) -> None:
                self.product = product

        recommendation_service.recommend = AsyncMock(return_value=[_Candidate(CATALOG[2])])

        metrics = await recsys_eval.evaluate_warm_sessions(
            recommendation_service, sessions, CATALOG, k=5
        )

        assert metrics.recall_at_k == 0.0
        assert metrics.ndcg_at_k == 0.0
        assert metrics.map_score == 0.0

    async def test_coverage_counts_distinct_recommended_products(self) -> None:
        sessions = [
            recsys_eval.SimulatedSession(seed=CATALOG[0], ground_truth=CATALOG[1]),
            recsys_eval.SimulatedSession(seed=CATALOG[2], ground_truth=CATALOG[3]),
        ]
        recommendation_service = AsyncMock()

        class _Candidate:
            def __init__(self, product: ProductResponse) -> None:
                self.product = product

        recommendation_service.recommend = AsyncMock(
            side_effect=[[_Candidate(CATALOG[1])], [_Candidate(CATALOG[1])]]
        )

        metrics = await recsys_eval.evaluate_warm_sessions(
            recommendation_service, sessions, CATALOG, k=5
        )

        # Both sessions recommended the same single product -> coverage is 1/5.
        assert metrics.coverage == pytest.approx(1 / len(CATALOG))


class TestEvaluateColdStart:
    async def test_reports_none_honestly_when_no_order_history(self) -> None:
        order_service = AsyncMock()
        order_service.get_best_sellers = AsyncMock(return_value=[])
        recommendation_service = AsyncMock()

        metrics = await recsys_eval.evaluate_cold_start(
            recommendation_service, order_service, cold_start_sessions=10, k=5
        )

        assert metrics.precision_at_k is None
        assert "no order history" in metrics.note
        recommendation_service.recommend.assert_not_awaited()

    async def test_precision_1_when_cold_start_matches_real_best_sellers(self) -> None:
        best_seller = BestSellerProduct(**CATALOG[0].model_dump(), total_sold=5)
        order_service = AsyncMock()
        order_service.get_best_sellers = AsyncMock(return_value=[best_seller])
        recommendation_service = AsyncMock()

        class _Candidate:
            def __init__(self, product: ProductResponse) -> None:
                self.product = product

        recommendation_service.recommend = AsyncMock(return_value=[_Candidate(CATALOG[0])])

        metrics = await recsys_eval.evaluate_cold_start(
            recommendation_service, order_service, cold_start_sessions=3, k=1
        )

        assert metrics.precision_at_k == 1.0


class TestInsertRow:
    def test_seeds_the_section_when_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "RESULTS.md"

        recsys_eval._insert_row(
            path, recsys_eval.WARM_HEADER, recsys_eval.WARM_SEPARATOR, "| row |", "## Heading"
        )

        text = path.read_text(encoding="utf-8")
        assert "## Heading" in text
        assert recsys_eval.WARM_HEADER in text
        assert "| row |" in text

    def test_inserts_newest_row_directly_under_the_header(self, tmp_path: Path) -> None:
        path = tmp_path / "RESULTS.md"
        path.write_text(
            f"## Heading\n\n{recsys_eval.WARM_HEADER}\n{recsys_eval.WARM_SEPARATOR}\n",
            encoding="utf-8",
        )

        recsys_eval._insert_row(
            path, recsys_eval.WARM_HEADER, recsys_eval.WARM_SEPARATOR, "| first |", "## Heading"
        )
        recsys_eval._insert_row(
            path, recsys_eval.WARM_HEADER, recsys_eval.WARM_SEPARATOR, "| second |", "## Heading"
        )

        lines = path.read_text(encoding="utf-8").splitlines()
        separator_index = lines.index(recsys_eval.WARM_SEPARATOR)
        assert lines[separator_index + 1] == "| second |"
        assert lines[separator_index + 2] == "| first |"


class TestCliWiring:
    async def test_run_exits_1_on_an_empty_catalog(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_product_service = AsyncMock()
        fake_product_service.list_active_catalog = AsyncMock(return_value=[])
        monkeypatch.setattr(recsys_eval, "ProductService", lambda *_a, **_kw: fake_product_service)
        monkeypatch.setattr(recsys_eval, "OrderService", lambda *_a, **_kw: AsyncMock())

        args = recsys_eval.argparse.Namespace(
            simulate=True,
            seed=42,
            sessions=10,
            cold_start_sessions=5,
            k=5,
            results_path=Path("unused.md"),
        )

        exit_code = await recsys_eval._run(session=AsyncMock(), args=args)

        assert exit_code == 1

    async def test_main_requires_the_simulate_flag(self) -> None:
        with pytest.raises(SystemExit):
            await recsys_eval.main([])
