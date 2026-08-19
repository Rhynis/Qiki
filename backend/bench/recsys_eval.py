"""Offline recommendation eval: a SEEDED, SIMULATED interaction log over the
real catalog.

**Honest framing (see docs/adr/0004-recommendations-thin-data.md):** Qiki has
essentially no real interaction history (~1 real customer, a handful of
self-test orders) -- nowhere near enough to evaluate a recommender against
real ground truth. This harness does NOT pretend otherwise. It:

1. Connects to the real database and reads the real active product catalog
   via ``ProductService`` -- the schema and catalog structure are real.
2. Generates a SEEDED, deterministic simulated interaction log: each session
   picks a "viewed" product, then a "next" product biased (70% of the time)
   toward the SAME structural relationships ``RecommendationService`` itself
   scores on (same brand, gas<->water complementary, adjacent size) and
   otherwise (30%) a uniformly random product. This makes recall/NDCG/MAP
   here a **self-consistency / sanity check** -- "does the ranker's output
   line up with plausible structure" -- NOT a claim about real-world
   accuracy. A recommender that scored badly here would be a real bug, but
   scoring well is not evidence of real predictive power.
3. Separately simulates a cold-start slice (no viewed product) and scores it
   against the ACTUAL best-sellers from real order history -- the one place
   this harness touches genuinely real (if sparse) behavioral data.

No external dataset, no GPU. Run with ``python -m bench.recsys_eval --simulate
--seed 42`` against a database that has the catalog seeded (``data/seed.sql``).
"""

import argparse
import asyncio
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.repositories.order_repository import OrderRepository  # noqa: E402
from app.repositories.product_repository import ProductRepository  # noqa: E402
from app.schemas.product import ProductResponse  # noqa: E402
from app.services.order_service import OrderService  # noqa: E402
from app.services.product_service import ProductService  # noqa: E402
from app.services.recommendation_service import RecommendationService  # noqa: E402

DEFAULT_SESSIONS = 300
DEFAULT_COLD_START_SESSIONS = 60
DEFAULT_K = 5
# How often a simulated session's "next" product is structurally related to
# the seed, vs. pure noise -- see the module docstring's honesty note.
RELATED_BIAS = 0.7


@dataclass(frozen=True)
class SimulatedSession:
    """One simulated interaction: a viewed product and what came "next"."""

    seed: ProductResponse
    ground_truth: ProductResponse


def _related_candidates(
    seed: ProductResponse, catalog: list[ProductResponse]
) -> list[ProductResponse]:
    """Products structurally related to ``seed``, in the same priority order
    RecommendationService itself scores (same brand > complementary category
    > same category) -- see that module for the reasoning."""
    same_brand = [p for p in catalog if p.id != seed.id and p.brand == seed.brand]
    if same_brand:
        return same_brand
    if seed.category == "gas":
        water = [p for p in catalog if p.category == "nuoc_uong"]
        if water:
            return water
    if seed.category == "nuoc_uong":
        other_brand_water = [
            p for p in catalog if p.category == "nuoc_uong" and p.brand != seed.brand
        ]
        if other_brand_water:
            return other_brand_water
    return [p for p in catalog if p.id != seed.id and p.category == seed.category]


def simulate_sessions(
    rng: random.Random, catalog: list[ProductResponse], count: int
) -> list[SimulatedSession]:
    """Generate ``count`` deterministic simulated (seed, next) sessions."""
    sessions: list[SimulatedSession] = []
    for _ in range(count):
        seed = rng.choice(catalog)
        others = [p for p in catalog if p.id != seed.id]
        if not others:
            continue
        if rng.random() < RELATED_BIAS:
            candidates = _related_candidates(seed, catalog) or others
        else:
            candidates = others
        ground_truth = rng.choice(candidates)
        sessions.append(SimulatedSession(seed=seed, ground_truth=ground_truth))
    return sessions


def _rank_of(target_id: UUID, ranked_ids: list[UUID]) -> int | None:
    """1-indexed rank of target_id in ranked_ids, or None if absent."""
    try:
        return ranked_ids.index(target_id) + 1
    except ValueError:
        return None


def recall_at_rank(rank: int | None) -> float:
    """Binary recall for a single relevant item: found within k, or not."""
    return 0.0 if rank is None else 1.0


def ndcg_at_rank(rank: int | None) -> float:
    """NDCG for a single relevant item: IDCG=1 (best case is rank 1)."""
    return 0.0 if rank is None else 1.0 / math.log2(rank + 1)


def average_precision_at_rank(rank: int | None) -> float:
    """AP for a single relevant item: precision at the position it was found."""
    return 0.0 if rank is None else 1.0 / rank


@dataclass(frozen=True)
class WarmMetrics:
    sessions: int
    k: int
    recall_at_k: float
    ndcg_at_k: float
    map_score: float
    coverage: float


@dataclass(frozen=True)
class ColdStartMetrics:
    sessions: int
    k: int
    precision_at_k: float | None
    note: str


async def evaluate_warm_sessions(
    recommendation_service: RecommendationService,
    sessions: list[SimulatedSession],
    catalog: list[ProductResponse],
    k: int,
) -> WarmMetrics:
    """Score the ranker against the structurally-biased simulated sessions."""
    recalls: list[float] = []
    ndcgs: list[float] = []
    aps: list[float] = []
    recommended_ids: set[UUID] = set()

    for session in sessions:
        candidates = await recommendation_service.recommend(product_id=session.seed.id, limit=k)
        ranked_ids = [c.product.id for c in candidates]
        recommended_ids.update(ranked_ids)
        rank = _rank_of(session.ground_truth.id, ranked_ids)
        recalls.append(recall_at_rank(rank))
        ndcgs.append(ndcg_at_rank(rank))
        aps.append(average_precision_at_rank(rank))

    n = len(sessions) or 1
    coverage = len(recommended_ids) / len(catalog) if catalog else 0.0
    return WarmMetrics(
        sessions=len(sessions),
        k=k,
        recall_at_k=sum(recalls) / n,
        ndcg_at_k=sum(ndcgs) / n,
        map_score=sum(aps) / n,
        coverage=coverage,
    )


async def evaluate_cold_start(
    recommendation_service: RecommendationService,
    order_service: OrderService,
    cold_start_sessions: int,
    k: int,
) -> ColdStartMetrics:
    """Score cold-start (no viewed product) recommendations against REAL best-sellers.

    The only slice of this harness measured against genuinely real data. When
    there is no order history at all (the common case for this project today),
    that's reported honestly instead of a fabricated number.
    """
    best_sellers = await order_service.get_best_sellers(limit=k)
    if not best_sellers:
        return ColdStartMetrics(
            sessions=cold_start_sessions,
            k=k,
            precision_at_k=None,
            note="no order history yet -- cold-start precision not measurable",
        )
    true_best_seller_ids = {product.id for product in best_sellers}

    precisions: list[float] = []
    for _ in range(cold_start_sessions):
        candidates = await recommendation_service.recommend(product_id=None, limit=k)
        recommended_ids = {c.product.id for c in candidates}
        precisions.append(len(recommended_ids & true_best_seller_ids) / k)

    n = cold_start_sessions or 1
    return ColdStartMetrics(
        sessions=cold_start_sessions,
        k=k,
        precision_at_k=sum(precisions) / n,
        note="precision@k vs the real best-sellers list",
    )


WARM_HEADER = "| Seed | Sessions | K | Recall@K | NDCG@K | MAP | Coverage |"
WARM_SEPARATOR = "|---|---|---|---|---|---|---|"
COLD_HEADER = "| Seed | Sessions | K | Precision@K vs real best-sellers | Note |"
COLD_SEPARATOR = "|---|---|---|---|---|"
RECSYS_SECTION_HEADING = "## Recommendations (simulated eval)"


def render_warm_row(seed: int, metrics: WarmMetrics) -> str:
    return (
        f"| {seed} | {metrics.sessions} | {metrics.k} | {metrics.recall_at_k:.1%} "
        f"| {metrics.ndcg_at_k:.3f} | {metrics.map_score:.3f} | {metrics.coverage:.1%} |"
    )


def render_cold_row(seed: int, metrics: ColdStartMetrics) -> str:
    precision_text = (
        f"{metrics.precision_at_k:.1%}" if metrics.precision_at_k is not None else "N/A"
    )
    return f"| {seed} | {metrics.sessions} | {metrics.k} | {precision_text} | {metrics.note} |"


def _insert_row(results_path: Path, header: str, separator: str, row: str, heading: str) -> None:
    """Insert ``row`` as the newest row right under an existing header+separator.

    Mirrors serving_benchmark.append_result_row's marker-based insertion so
    every bench script can share RESULTS.md without stepping on each other's
    tables regardless of section order.
    """
    marker = f"{header}\n{separator}\n"
    text = results_path.read_text(encoding="utf-8") if results_path.exists() else ""
    if marker in text:
        text = text.replace(marker, marker + row + "\n", 1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"\n{heading}\n\n{marker}{row}\n"
    results_path.write_text(text, encoding="utf-8")


def render_summary_text(warm: WarmMetrics, cold: ColdStartMetrics) -> str:
    cold_precision = f"{cold.precision_at_k:.1%}" if cold.precision_at_k is not None else "N/A"
    return (
        f"Warm sessions: {warm.sessions}, K={warm.k}\n"
        f"Recall@K: {warm.recall_at_k:.1%}\n"
        f"NDCG@K: {warm.ndcg_at_k:.3f}\n"
        f"MAP: {warm.map_score:.3f}\n"
        f"Catalog coverage: {warm.coverage:.1%}\n\n"
        f"Cold-start sessions: {cold.sessions}\n"
        f"Cold-start precision@K vs real best-sellers: {cold_precision} ({cold.note})"
    )


async def main(argv: list[str] | None = None) -> int:
    """Run the simulated recommendation eval and print + persist results."""
    parser = argparse.ArgumentParser(description="Qiki recommendation eval (simulated)")
    parser.add_argument(
        "--simulate",
        action="store_true",
        required=True,
        help=(
            "Required today -- a simulated interaction log is the only mode this "
            "harness supports. Real interaction-log evaluation is the ADR's stretch."
        ),
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sessions", type=int, default=DEFAULT_SESSIONS)
    parser.add_argument("--cold-start-sessions", type=int, default=DEFAULT_COLD_START_SESSIONS)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--results-path", type=Path, default=Path("RESULTS.md"))
    args = parser.parse_args(argv)

    async with AsyncSessionLocal() as session:
        exit_code = await _run(session, args)
    return exit_code


async def _run(session: AsyncSession, args: argparse.Namespace) -> int:
    product_service = ProductService(ProductRepository(session))
    order_service = OrderService(OrderRepository(session), ProductRepository(session))
    recommendation_service = RecommendationService(product_service, order_service)

    catalog = await product_service.list_active_catalog(limit=100)
    if not catalog:
        print(
            "No active products in this database -- nothing to simulate. "
            "Seed the catalog first (e.g. `python -m scripts.seed_data`)."
        )
        return 1

    rng = random.Random(args.seed)
    warm_sessions = simulate_sessions(rng, catalog, args.sessions)
    warm_metrics = await evaluate_warm_sessions(
        recommendation_service, warm_sessions, catalog, args.k
    )
    cold_metrics = await evaluate_cold_start(
        recommendation_service, order_service, args.cold_start_sessions, args.k
    )

    print(render_summary_text(warm_metrics, cold_metrics))
    print(f"\n{WARM_HEADER}\n{WARM_SEPARATOR}\n{render_warm_row(args.seed, warm_metrics)}")
    print(f"\n{COLD_HEADER}\n{COLD_SEPARATOR}\n{render_cold_row(args.seed, cold_metrics)}")

    _insert_row(
        args.results_path,
        WARM_HEADER,
        WARM_SEPARATOR,
        render_warm_row(args.seed, warm_metrics),
        RECSYS_SECTION_HEADING,
    )
    _insert_row(
        args.results_path,
        COLD_HEADER,
        COLD_SEPARATOR,
        render_cold_row(args.seed, cold_metrics),
        RECSYS_SECTION_HEADING,
    )
    print(f"\nAppended run to {args.results_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
