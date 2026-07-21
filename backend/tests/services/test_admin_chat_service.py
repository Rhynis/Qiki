"""Tests for AdminChatService (admin_chat catalog management flow)."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fakeredis.aioredis import FakeRedis

from app.core.exceptions import ForbiddenException
from app.models.product import Product
from app.models.user import User
from app.schemas.admin_chat import AdminChatRequest
from app.schemas.product import ProductSearchParams
from app.services.admin_chat_service import AdminChatService
from app.services.product_service import ProductService

pytestmark = pytest.mark.asyncio


def make_admin(role: str = "admin") -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email=f"{role}-{uuid4().hex[:6]}@example.com",
        hashed_password="hashed",
        full_name=f"{role.title()} User",
        phone="0900000000",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def make_product(
    *,
    sku: str = "GAS-ELF-12",
    name: str = "Gas Elf 12kg",
    brand: str = "Elf",
    size_kg: Decimal = Decimal("12"),
    price: Decimal = Decimal("445000"),
    stock_quantity: int = 15,
    is_active: bool = True,
    colour: str | None = None,
) -> Product:
    now = datetime.now(UTC)
    return Product(
        id=uuid4(),
        sku=sku,
        name=name,
        brand=brand,
        size_kg=size_kg,
        category="gas",
        unit="kg",
        price=price,
        stock_quantity=stock_quantity,
        description="desc",
        image_url="https://example.com/x.jpg",
        safety_info="safe",
        pricing_note=None,
        is_active=is_active,
        colour=colour,
        created_at=now,
        updated_at=now,
    )


class FakeProductRepository:
    """In-memory product repository honoring active_only + pagination."""

    def __init__(self, products: list[Product]) -> None:
        self.products: dict[UUID, Product] = {product.id: product for product in products}

    async def get_by_id(self, product_id: UUID, *, active_only: bool = False) -> Product | None:
        product = self.products.get(product_id)
        if product and active_only and not product.is_active:
            return None
        return product

    async def list_products(
        self,
        params: ProductSearchParams,
        *,
        active_only: bool = True,
    ) -> tuple[list[Product], int]:
        items = [
            product for product in self.products.values() if not active_only or product.is_active
        ]
        items.sort(key=lambda product: product.name)
        total = len(items)
        page = items[params.skip : params.skip + params.limit]
        return page, total

    async def update(self, product_id: UUID, data: dict[str, object]) -> Product:
        product = self.products[product_id]
        for key, value in data.items():
            setattr(product, key, value)
        return product


class FakeAuditRepository:
    """Capture audit entries in memory."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    async def record(
        self,
        *,
        admin_id: UUID,
        action: str,
        target_type: str,
        target_id: UUID | None,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> object:
        entry = {
            "admin_id": admin_id,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "before": before,
            "after": after,
        }
        self.entries.append(entry)
        return entry


def build_service(
    products: list[Product], redis: FakeRedis
) -> tuple[AdminChatService, FakeProductRepository, FakeAuditRepository]:
    repository = FakeProductRepository(products)
    audit = FakeAuditRepository()
    service = AdminChatService(
        product_service=ProductService(repository),  # type: ignore[arg-type]
        product_repository=repository,  # type: ignore[arg-type]
        audit_repository=audit,  # type: ignore[arg-type]
        redis=redis,
    )
    return service, repository, audit


async def test_admin_chat_price_update_requires_confirmation_first(
    mock_redis: FakeRedis,
) -> None:
    product = make_product(price=Decimal("445000"))
    service, repository, audit = build_service([product], mock_redis)
    admin = make_admin()

    response = await service.handle(
        AdminChatRequest(message="đổi giá Elf 12kg thành 460000"), admin
    )

    assert response.status == "confirm_required"
    assert response.pending_token is not None
    assert response.action is not None
    assert response.action.action == "update_price"
    assert response.action.current_value == "445.000đ"
    assert response.action.new_value == "460.000đ"
    # Never mutates on the first message.
    assert repository.products[product.id].price == Decimal("445000")
    assert audit.entries == []


async def test_admin_chat_confirm_executes_price_update_and_audits(
    mock_redis: FakeRedis,
) -> None:
    product = make_product(price=Decimal("445000"))
    service, repository, audit = build_service([product], mock_redis)
    admin = make_admin()

    planned = await service.handle(AdminChatRequest(message="đổi giá Elf 12kg thành 460000"), admin)
    executed = await service.handle(
        AdminChatRequest(message="", confirm=True, pending_token=planned.pending_token), admin
    )

    assert executed.status == "executed"
    # ProductUpdate.model_dump(mode="json") serializes the Decimal to a string;
    # the real Numeric column round-trips it back to Decimal (see the API test).
    assert Decimal(str(repository.products[product.id].price)) == Decimal("460000")
    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert entry["admin_id"] == admin.id
    assert entry["action"] == "update_price"
    assert entry["target_id"] == product.id
    assert entry["before"] == {"price": "445000"}
    assert entry["after"] == {"price": "460000"}


async def test_admin_chat_stock_update_confirm_then_execute(mock_redis: FakeRedis) -> None:
    product = make_product(stock_quantity=15)
    service, repository, audit = build_service([product], mock_redis)
    admin = make_admin()

    planned = await service.handle(
        AdminChatRequest(message="cập nhật tồn Elf 12kg thành 30"), admin
    )
    assert planned.status == "confirm_required"
    assert repository.products[product.id].stock_quantity == 15

    executed = await service.handle(
        AdminChatRequest(message="", confirm=True, pending_token=planned.pending_token), admin
    )
    assert executed.status == "executed"
    assert repository.products[product.id].stock_quantity == 30
    assert audit.entries[0]["before"] == {"stock_quantity": 15}
    assert audit.entries[0]["after"] == {"stock_quantity": 30}


async def test_admin_chat_hide_product_toggle_by_sku(mock_redis: FakeRedis) -> None:
    product = make_product(sku="GAS-ELF-12", is_active=True)
    service, repository, audit = build_service([product], mock_redis)
    admin = make_admin()

    planned = await service.handle(AdminChatRequest(message="ẩn sản phẩm GAS-ELF-12"), admin)
    assert planned.status == "confirm_required"
    assert planned.action is not None and planned.action.action == "set_active"
    assert repository.products[product.id].is_active is True

    executed = await service.handle(
        AdminChatRequest(message="", confirm=True, pending_token=planned.pending_token), admin
    )
    assert executed.status == "executed"
    assert repository.products[product.id].is_active is False
    assert audit.entries[0]["after"] == {"is_active": False}


async def test_admin_chat_price_command_without_amount_never_mutates(
    mock_redis: FakeRedis,
) -> None:
    product = make_product(price=Decimal("445000"))
    service, repository, audit = build_service([product], mock_redis)
    admin = make_admin()

    # A price cue with no parseable amount is not actionable and must not mutate.
    response = await service.handle(AdminChatRequest(message="đổi giá Elf 12kg"), admin)

    assert response.status == "unrecognized"
    assert response.pending_token is None
    assert repository.products[product.id].price == Decimal("445000")
    assert audit.entries == []


async def test_admin_chat_validation_rejects_non_positive_price() -> None:
    # The server-side guard rejects a non-positive price even if extraction ever
    # produced one (defense in depth before calling the admin service).
    from app.services.admin_chat_parser import ParsedInstruction

    product = make_product(price=Decimal("445000"))
    error = AdminChatService._validation_error(
        ParsedInstruction(action="update_price", price_value=Decimal("0")), product
    )
    assert error is not None


async def test_admin_chat_negative_stock_never_mutates(mock_redis: FakeRedis) -> None:
    product = make_product(stock_quantity=15)
    service, repository, _ = build_service([product], mock_redis)
    admin = make_admin()

    response = await service.handle(AdminChatRequest(message="đặt tồn Elf 12kg thành -5"), admin)

    assert response.status == "invalid"
    assert repository.products[product.id].stock_quantity == 15


async def test_admin_chat_unrecognized_message_no_mutation(mock_redis: FakeRedis) -> None:
    product = make_product()
    service, _, audit = build_service([product], mock_redis)
    admin = make_admin()

    response = await service.handle(AdminChatRequest(message="chào Qiki"), admin)

    assert response.status == "unrecognized"
    assert response.pending_token is None
    assert audit.entries == []


async def test_admin_chat_product_not_found(mock_redis: FakeRedis) -> None:
    product = make_product(brand="Elf")
    service, _, _ = build_service([product], mock_redis)
    admin = make_admin()

    response = await service.handle(
        AdminChatRequest(message="đổi giá Petrolimex 45kg thành 900000"), admin
    )

    assert response.status == "not_found"
    assert response.pending_token is None


async def test_admin_chat_ambiguous_multiple_matches_no_token(mock_redis: FakeRedis) -> None:
    red = make_product(sku="GAS-ELF-12-RED", name="Gas Elf 12kg Đỏ", colour="đỏ")
    grey = make_product(sku="GAS-ELF-12-GREY", name="Gas Elf 12kg Xám", colour="xám")
    service, _, audit = build_service([red, grey], mock_redis)
    admin = make_admin()

    response = await service.handle(
        AdminChatRequest(message="đổi giá Elf 12kg thành 460000"), admin
    )

    assert response.status == "ambiguous"
    assert response.pending_token is None
    assert audit.entries == []


async def test_admin_chat_confirm_expired_or_unknown_token(mock_redis: FakeRedis) -> None:
    product = make_product()
    service, repository, _ = build_service([product], mock_redis)
    admin = make_admin()

    response = await service.handle(
        AdminChatRequest(message="", confirm=True, pending_token="deadbeef"), admin
    )

    assert response.status == "expired"
    assert repository.products[product.id].price == Decimal("445000")


async def test_admin_chat_token_scoped_to_creating_admin(mock_redis: FakeRedis) -> None:
    product = make_product(price=Decimal("445000"))
    service, repository, audit = build_service([product], mock_redis)
    admin_a = make_admin()
    admin_b = make_admin()

    planned = await service.handle(
        AdminChatRequest(message="đổi giá Elf 12kg thành 460000"), admin_a
    )
    # A different admin must not be able to confirm admin A's pending action.
    response = await service.handle(
        AdminChatRequest(message="", confirm=True, pending_token=planned.pending_token), admin_b
    )

    assert response.status == "expired"
    assert repository.products[product.id].price == Decimal("445000")
    assert audit.entries == []


async def test_admin_chat_confirm_token_is_single_use(mock_redis: FakeRedis) -> None:
    product = make_product(price=Decimal("445000"))
    service, repository, audit = build_service([product], mock_redis)
    admin = make_admin()

    planned = await service.handle(AdminChatRequest(message="đổi giá Elf 12kg thành 460000"), admin)
    first = await service.handle(
        AdminChatRequest(message="", confirm=True, pending_token=planned.pending_token), admin
    )
    second = await service.handle(
        AdminChatRequest(message="", confirm=True, pending_token=planned.pending_token), admin
    )

    assert first.status == "executed"
    assert second.status == "expired"
    # Exactly one mutation + one audit entry despite two confirm calls.
    assert Decimal(str(repository.products[product.id].price)) == Decimal("460000")
    assert len(audit.entries) == 1


async def test_admin_chat_non_admin_cannot_execute_mutation(mock_redis: FakeRedis) -> None:
    # Defense in depth: even if a non-admin somehow reached the service (they
    # cannot — the endpoint gates on get_current_admin), the product service still
    # refuses the mutation when the confirming user is not an admin.
    product = make_product(price=Decimal("445000"))
    service, repository, audit = build_service([product], mock_redis)
    customer = make_admin(role="customer")

    planned = await service.handle(
        AdminChatRequest(message="đổi giá Elf 12kg thành 460000"), customer
    )
    with pytest.raises(ForbiddenException):
        await service.handle(
            AdminChatRequest(message="", confirm=True, pending_token=planned.pending_token),
            customer,
        )
    assert repository.products[product.id].price == Decimal("445000")
    assert audit.entries == []


async def test_admin_chat_confirm_aborts_on_concurrent_change(mock_redis: FakeRedis) -> None:
    # If another operation changes the row between plan and confirm, the confirm
    # must abort (optimistic concurrency) instead of silently overwriting it.
    product = make_product(price=Decimal("445000"))
    service, repository, audit = build_service([product], mock_redis)
    admin = make_admin()

    planned = await service.handle(AdminChatRequest(message="đổi giá Elf 12kg thành 460000"), admin)
    assert planned.status == "confirm_required"

    # A concurrent change to the live price between plan and confirm.
    repository.products[product.id].price = Decimal("500000")

    stale = await service.handle(
        AdminChatRequest(message="", confirm=True, pending_token=planned.pending_token), admin
    )

    assert stale.status == "stale"
    # The concurrent change is preserved; nothing was overwritten or audited.
    assert Decimal(str(repository.products[product.id].price)) == Decimal("500000")
    assert audit.entries == []
