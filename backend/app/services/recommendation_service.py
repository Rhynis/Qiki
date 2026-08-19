"""Product recommendation ranking: content-based + popularity + explicit rules.

Qiki has almost no real interaction data to learn from (see
``docs/adr/0004-recommendations-thin-data.md`` for the honest framing: ~1 real
customer and a handful of self-test orders). A collaborative-filtering or
learned-embedding ranker would be fitting noise. Instead this combines three
transparent, catalog-derived signals:

1. **Content similarity** to the viewed product (same brand, same category,
   adjacent gas size, similar price) — the primary signal given thin data.
2. **Popularity** (real order history via ``OrderService.get_best_sellers``)
   as a prior, not a learned signal.
3. **Explicit complementary rules** (a gas product suggests water as an
   add-on; a water product suggests the other water brand) — hand-written,
   not inferred, exactly the kind of thing a real merchandiser would set up.

Every candidate's score is the SUM of whichever signals apply; the single
highest-weighted signal that actually contributed becomes the human-readable
``reason`` (never a fabricated or generic claim — see ``_best_reason``).
Cold start (no viewed product) degrades to popularity-only, honestly labeled
when there is no order history to be popular from.
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.schemas.product import ProductResponse
from app.services.order_service import OrderService
from app.services.product_service import ProductService

# Scoring weights, hand-tuned for a thin-data catalog: explicit rules and
# direct content matches dominate; popularity is a prior, not a learned
# weight fit to real behavior. See the ADR for the reasoning.
WEIGHT_COMPLEMENTARY_RULE = 0.40
WEIGHT_SAME_BRAND = 0.30
WEIGHT_ADJACENT_SIZE = 0.20
WEIGHT_POPULARITY = 0.25
WEIGHT_SAME_CATEGORY = 0.10
WEIGHT_PRICE_BAND = 0.10

# A candidate's price counts as "similar" within +/-25% of the viewed product.
PRICE_BAND_RATIO = Decimal("0.25")

DEFAULT_LIMIT = 6
# The real catalog is small (~20 products); fetching it in full and ranking
# in memory is simpler and fast enough, mirroring ProductService's own
# _COMBINED_FETCH_LIMIT reasoning for the same catalog.
CATALOG_FETCH_LIMIT = 100
# How many best-sellers to pull for the popularity prior -- large enough to
# cover the whole small catalog, not just the top few.
POPULARITY_FETCH_LIMIT = 100

REASON_POPULAR_FALLBACK = "Sản phẩm nổi bật trong danh mục"
REASON_BEST_SELLER = "Sản phẩm bán chạy, khách hay chọn"


@dataclass(frozen=True)
class RecommendationCandidate:
    """One ranked recommendation: the product, its score, and why it's here."""

    product: ProductResponse
    score: float
    reason: str


def _signal_contributions(
    candidate: ProductResponse,
    *,
    viewed: ProductResponse | None,
    popularity_ratio: float,
) -> list[tuple[float, str]]:
    """Return every (contribution, reason) pair that applies to this candidate.

    Popularity always applies (0.0 when the candidate has no sales). Content
    and rule signals only apply when there's a viewed product to compare
    against (cold start has none).
    """
    contributions: list[tuple[float, str]] = [
        (WEIGHT_POPULARITY * popularity_ratio, REASON_BEST_SELLER),
    ]
    if viewed is None:
        return contributions

    if viewed.category == "gas" and candidate.category == "nuoc_uong":
        contributions.append((WEIGHT_COMPLEMENTARY_RULE, "Khách mua gas thường lấy kèm nước uống"))
    elif (
        viewed.category == "nuoc_uong"
        and candidate.category == "nuoc_uong"
        and candidate.brand != viewed.brand
    ):
        contributions.append((WEIGHT_COMPLEMENTARY_RULE, "Khách hay đổi giữa các hãng nước uống"))

    if candidate.brand == viewed.brand:
        contributions.append((WEIGHT_SAME_BRAND, f"Cùng hãng {candidate.brand}"))

    if (
        candidate.category == "gas"
        and viewed.category == "gas"
        and candidate.size_kg != viewed.size_kg
    ):
        size_text = f"{candidate.size_kg.normalize():f}".rstrip("0").rstrip(".")
        direction = "cỡ lớn hơn" if candidate.size_kg > viewed.size_kg else "cỡ nhỏ hơn"
        contributions.append((WEIGHT_ADJACENT_SIZE, f"Cùng loại gas, {direction} ({size_text}kg)"))

    if candidate.category == viewed.category:
        contributions.append((WEIGHT_SAME_CATEGORY, "Cùng loại sản phẩm"))

    viewed_price = viewed.sale_price or viewed.price
    candidate_price = candidate.sale_price or candidate.price
    if viewed_price > 0 and abs(candidate_price - viewed_price) <= viewed_price * PRICE_BAND_RATIO:
        contributions.append((WEIGHT_PRICE_BAND, "Mức giá tương đương"))

    return contributions


def _best_reason(contributions: list[tuple[float, str]]) -> tuple[float, str]:
    """Sum every contribution; the reason is whichever one contributed most."""
    total = sum(value for value, _ in contributions)
    positive = [pair for pair in contributions if pair[0] > 0]
    if not positive:
        return total, REASON_POPULAR_FALLBACK
    _, reason = max(positive, key=lambda pair: pair[0])
    return total, reason


class RecommendationService:
    """Rank active products for a "you might also like" style surface."""

    def __init__(self, product_service: ProductService, order_service: OrderService) -> None:
        self.product_service = product_service
        self.order_service = order_service

    async def recommend(
        self,
        *,
        product_id: UUID | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[RecommendationCandidate]:
        """Rank active products, optionally relative to a viewed product.

        Raises ``NotFoundException`` if ``product_id`` is given but isn't an
        active product (mirrors ``ProductService.get_product``). Returns at
        most ``limit`` candidates, deterministically ordered (score desc,
        then name asc as a stable tiebreak), and never includes the viewed
        product itself.
        """
        viewed = await self.product_service.get_product(product_id) if product_id else None
        catalog = await self.product_service.list_active_catalog(limit=CATALOG_FETCH_LIMIT)
        popularity = await self._popularity_ratios()

        candidates: list[RecommendationCandidate] = []
        for candidate in catalog:
            if viewed is not None and candidate.id == viewed.id:
                continue
            contributions = _signal_contributions(
                candidate,
                viewed=viewed,
                popularity_ratio=popularity.get(candidate.id, 0.0),
            )
            score, reason = _best_reason(contributions)
            candidates.append(
                RecommendationCandidate(product=candidate, score=score, reason=reason)
            )

        candidates.sort(key=lambda item: (-item.score, item.product.name))
        return candidates[:limit]

    async def _popularity_ratios(self) -> dict[UUID, float]:
        """Map product id -> total_sold normalized against the current max.

        Empty (all zero) when there's no order history yet -- an honest
        cold-start state, not an error.
        """
        best_sellers = await self.order_service.get_best_sellers(limit=POPULARITY_FETCH_LIMIT)
        if not best_sellers:
            return {}
        max_sold = max(item.total_sold for item in best_sellers)
        if max_sold <= 0:
            return {}
        return {item.id: item.total_sold / max_sold for item in best_sellers}
