"""Tests for RecommendationService: content + popularity + rules ranking."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundException
from app.schemas.product import BestSellerProduct, ProductResponse
from app.services.recommendation_service import (
    REASON_BEST_SELLER,
    REASON_POPULAR_FALLBACK,
    RecommendationService,
)

pytestmark = pytest.mark.asyncio


def make_product(
    *,
    sku: str = "SP-12KG-XAM",
    name: str = "Bình gas Saigon Petro 12kg",
    brand: str = "Saigon Petro",
    size_kg: str = "12",
    category: str = "gas",
    unit: str = "kg",
    price: str = "605000",
    sale_price: str | None = None,
    stock_quantity: int = 20,
) -> ProductResponse:
    now = datetime.now(UTC)
    return ProductResponse(
        id=uuid4(),
        sku=sku,
        name=name,
        brand=brand,
        size_kg=Decimal(size_kg),
        category=category,  # type: ignore[arg-type]
        unit=unit,  # type: ignore[arg-type]
        price=Decimal(price),
        sale_price=Decimal(sale_price) if sale_price else None,
        stock_quantity=stock_quantity,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def as_best_seller(product: ProductResponse, total_sold: int) -> BestSellerProduct:
    return BestSellerProduct(**product.model_dump(), total_sold=total_sold)


def service(
    catalog: list[ProductResponse],
    viewed: ProductResponse | None = None,
    best_sellers: list[BestSellerProduct] | None = None,
) -> RecommendationService:
    product_service = AsyncMock()
    product_service.list_active_catalog = AsyncMock(return_value=catalog)
    if viewed is not None:
        product_service.get_product = AsyncMock(return_value=viewed)
    else:
        product_service.get_product = AsyncMock(side_effect=NotFoundException("not found"))
    order_service = AsyncMock()
    order_service.get_best_sellers = AsyncMock(return_value=best_sellers or [])
    return RecommendationService(product_service, order_service)


class TestExclusionAndDeterminism:
    async def test_never_recommends_the_viewed_product_itself(self) -> None:
        viewed = make_product(sku="A", name="A")
        other = make_product(sku="B", name="B")
        svc = service([viewed, other], viewed=viewed)

        results = await svc.recommend(product_id=viewed.id)

        assert viewed.id not in [c.product.id for c in results]
        assert other.id in [c.product.id for c in results]

    async def test_ranking_is_deterministic_across_repeated_calls(self) -> None:
        viewed = make_product(sku="A", name="A")
        catalog = [viewed] + [make_product(sku=f"P{i}", name=f"P{i}") for i in range(5)]
        svc = service(catalog, viewed=viewed)

        first = await svc.recommend(product_id=viewed.id)
        second = await svc.recommend(product_id=viewed.id)

        assert [c.product.id for c in first] == [c.product.id for c in second]
        assert [c.score for c in first] == [c.score for c in second]

    async def test_ties_break_by_product_name_ascending(self) -> None:
        # Same brand/category/price/size -> identical score; name is the
        # deterministic tiebreak, not insertion order.
        viewed = make_product(sku="A", name="Viewed", brand="X", category="gas")
        zeta = make_product(sku="Z", name="Zeta", brand="Other", category="gas", size_kg="6")
        alpha = make_product(sku="AA", name="Alpha", brand="Other", category="gas", size_kg="6")
        svc = service([viewed, zeta, alpha], viewed=viewed)

        results = await svc.recommend(product_id=viewed.id)

        assert [c.product.name for c in results] == ["Alpha", "Zeta"]

    async def test_raises_not_found_for_an_unknown_or_inactive_product(self) -> None:
        svc = service([], viewed=None)

        with pytest.raises(NotFoundException):
            await svc.recommend(product_id=uuid4())

    async def test_respects_the_limit(self) -> None:
        viewed = make_product(sku="A", name="A")
        catalog = [viewed] + [make_product(sku=f"P{i}", name=f"P{i}") for i in range(10)]
        svc = service(catalog, viewed=viewed)

        results = await svc.recommend(product_id=viewed.id, limit=3)

        assert len(results) == 3


class TestContentSignals:
    async def test_same_brand_outranks_a_different_brand_same_category(self) -> None:
        viewed = make_product(sku="A", name="Viewed", brand="Saigon Petro", category="gas")
        same_brand = make_product(
            sku="B", name="SameBrand", brand="Saigon Petro", category="gas", size_kg="6"
        )
        other_brand = make_product(
            sku="C", name="OtherBrand", brand="Elf Gas", category="gas", size_kg="12"
        )
        svc = service([viewed, same_brand, other_brand], viewed=viewed)

        results = await svc.recommend(product_id=viewed.id)

        assert results[0].product.id == same_brand.id
        assert "Saigon Petro" in results[0].reason

    async def test_gas_recommends_water_with_a_complementary_reason(self) -> None:
        viewed = make_product(sku="A", name="Gas", category="gas", brand="Elf Gas")
        water = make_product(
            sku="W", name="Water", category="nuoc_uong", brand="Vihawa", unit="lít", size_kg="20"
        )
        unrelated_gas = make_product(
            sku="C", name="OtherGas", category="gas", brand="Sao Mai", size_kg="45"
        )
        svc = service([viewed, water, unrelated_gas], viewed=viewed)

        results = await svc.recommend(product_id=viewed.id)

        assert results[0].product.id == water.id
        assert "nước" in results[0].reason

    async def test_water_recommends_the_other_water_brand(self) -> None:
        viewed = make_product(
            sku="A", name="Vihawa", category="nuoc_uong", brand="Vihawa", unit="lít", size_kg="20"
        )
        other_brand_water = make_product(
            sku="B",
            name="HoanHao",
            category="nuoc_uong",
            brand="Hoàn Hảo",
            unit="lít",
            size_kg="20",
        )
        same_brand_water = make_product(
            sku="C",
            name="VihawaHotCold",
            category="nuoc_uong",
            brand="Vihawa",
            unit="lít",
            size_kg="20",
        )
        svc = service([viewed, other_brand_water, same_brand_water], viewed=viewed)

        results = await svc.recommend(product_id=viewed.id)

        assert results[0].product.id == other_brand_water.id
        assert "hãng nước" in results[0].reason

    async def test_adjacent_gas_size_scores_above_unrelated_category(self) -> None:
        viewed = make_product(sku="A", name="Viewed", brand="X", category="gas", size_kg="12")
        adjacent_size = make_product(
            sku="B", name="Bigger", brand="Y", category="gas", size_kg="45"
        )
        water = make_product(
            sku="C", name="Water", brand="Vihawa", category="nuoc_uong", unit="lít", size_kg="20"
        )
        svc = service([viewed, adjacent_size, water], viewed=viewed)

        results = await svc.recommend(product_id=viewed.id)
        by_id = {c.product.id: c for c in results}

        # Water wins (explicit complementary rule, weight 0.40 > adjacent
        # size's 0.20), but the size match must still score above zero and
        # carry its own concrete reason.
        assert results[0].product.id == water.id
        assert by_id[adjacent_size.id].score > 0
        assert "cỡ" in by_id[adjacent_size.id].reason

    async def test_price_band_match_gives_a_small_positive_score(self) -> None:
        viewed = make_product(sku="A", name="Viewed", brand="X", category="gas", price="600000")
        close_price = make_product(
            sku="B", name="ClosePrice", brand="Y", category="gas", price="620000"
        )
        far_price = make_product(
            sku="C", name="FarPrice", brand="Z", category="gas", price="2000000"
        )
        svc = service([viewed, close_price, far_price], viewed=viewed)

        results = await svc.recommend(product_id=viewed.id)
        by_id = {c.product.id: c.score for c in results}

        assert by_id[close_price.id] > by_id[far_price.id]

    async def test_effective_price_is_compared_not_the_stale_list_price(self) -> None:
        # A steep sale price should pull a candidate INTO the price band even
        # though its list price is far away -- scored via score, not the
        # reason string, since same_category (0.10) and price_band (0.10)
        # can legitimately tie on which becomes the displayed reason.
        viewed = make_product(sku="A", name="Viewed", brand="X", price="600000")
        far_list_price_but_on_sale = make_product(
            sku="B", name="OnSale", brand="Y", price="2000000", sale_price="610000"
        )
        far_list_price_no_sale = make_product(sku="C", name="FullPrice", brand="Z", price="2000000")
        svc = service([viewed, far_list_price_but_on_sale, far_list_price_no_sale], viewed=viewed)

        results = await svc.recommend(product_id=viewed.id)
        by_id = {c.product.id: c.score for c in results}

        assert by_id[far_list_price_but_on_sale.id] > by_id[far_list_price_no_sale.id]


class TestPopularityAndColdStart:
    async def test_best_seller_ranks_above_a_quiet_product_with_the_same_content_match(
        self,
    ) -> None:
        # Same category/brand-tier/size for both candidates (only same_category,
        # 0.10, applies as a content signal) so popularity (0.25 at ratio=1.0)
        # is the strongest signal and must win as the displayed reason.
        viewed = make_product(sku="A", name="Viewed", brand="X", category="gas")
        best_seller = make_product(sku="B", name="BestSeller", brand="Y", category="gas")
        quiet = make_product(sku="C", name="Quiet", brand="Z", category="gas")
        svc = service(
            [viewed, best_seller, quiet],
            viewed=viewed,
            best_sellers=[as_best_seller(best_seller, 10), as_best_seller(quiet, 1)],
        )

        results = await svc.recommend(product_id=viewed.id)

        assert results[0].product.id == best_seller.id
        assert results[0].reason == REASON_BEST_SELLER

    async def test_cold_start_with_no_product_id_ranks_by_popularity(self) -> None:
        top = make_product(sku="A", name="Top")
        mid = make_product(sku="B", name="Mid")
        catalog = [top, mid]
        svc = service(
            catalog,
            viewed=None,
            best_sellers=[as_best_seller(top, 20), as_best_seller(mid, 5)],
        )

        results = await svc.recommend(product_id=None)

        assert [c.product.id for c in results] == [top.id, mid.id]
        assert results[0].reason == REASON_BEST_SELLER

    async def test_cold_start_with_no_order_history_falls_back_honestly(self) -> None:
        catalog = [make_product(sku="A", name="A"), make_product(sku="B", name="B")]
        svc = service(catalog, viewed=None, best_sellers=[])

        results = await svc.recommend(product_id=None)

        assert len(results) == 2
        assert all(c.score == 0.0 for c in results)
        assert all(c.reason == REASON_POPULAR_FALLBACK for c in results)
