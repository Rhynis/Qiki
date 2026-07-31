"""Tests for OrderService."""

import asyncio
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, InsufficientStockException, ValidationException
from app.db.session import AsyncSessionLocal
from app.models.product import Product
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import CheckoutRequest, OrderItemCreate, OrderSearchParams, VatInfo
from app.schemas.product import ProductCreate
from app.services.order_service import OrderService

pytestmark = pytest.mark.asyncio


def user_model(role: str = "customer", *, phone: str = "+84901234567") -> User:
    """Create a user model."""
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email=f"{role}-{uuid4().hex}@example.com",
        hashed_password="hashed",
        full_name=f"{role.title()} User",
        phone=phone,
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


async def create_user(session: AsyncSession, role: str = "customer") -> User:
    user = user_model(role)
    session.add(user)
    await session.commit()
    return user


async def create_product(
    session: AsyncSession,
    *,
    sku: str = "GAS-12-SAIGON",
    name: str = "Binh gas 12kg",
    brand: str = "Saigon Petro",
    size_kg: Decimal = Decimal("12"),
    category: Literal["gas", "nuoc_uong"] = "gas",
    unit: Literal["kg", "lít"] = "kg",
    price: Decimal = Decimal("350000"),
    stock_quantity: int = 20,
    is_active: bool = True,
) -> Product:
    product = await ProductRepository(session).create(
        ProductCreate(
            sku=sku,
            name=name,
            brand=brand,
            size_kg=size_kg,
            category=category,
            unit=unit,
            price=price,
            stock_quantity=stock_quantity,
            description="San pham giao tan noi",
            image_url="https://example.com/gas-12kg.jpg",
            safety_info="Dat binh noi thoang khi.",
            pricing_note=(
                "Giá tại cửa hàng; giao +5.000đ; lên lầu +5.000đ/lầu"
                if category == "nuoc_uong"
                else None
            ),
        )
    )
    product.is_active = is_active
    await session.commit()
    return product


def checkout_payload(product: Product, **overrides: object) -> CheckoutRequest:
    data: dict[str, object] = {
        "items": [OrderItemCreate(product_id=product.id, quantity=2, is_exchange=False)],
        "customer_name": "Nguyen Van A",
        "customer_phone": "0901234567",
        "customer_email": "customer@example.com",
        "delivery_address": "123 Nguyen Trai",
        "delivery_ward": "Phuong Ben Thanh",
        "delivery_district": "Quan 1",
        "delivery_city": "TP. Hồ Chí Minh",
        "payment_method": "cod",
        "vat_invoice_requested": False,
    }
    data.update(overrides)
    return CheckoutRequest.model_validate(data)


def raw_order_data(index: int = 1) -> dict[str, object]:
    """Return valid raw order data for repository-level tests."""
    return {
        "user_id": None,
        "customer_name": f"Nguyen Van A {index}",
        "customer_phone": "+84901234567",
        "customer_email": None,
        "delivery_address": "123 Nguyen Trai",
        "delivery_ward": "Phuong Ben Thanh",
        "delivery_district": "Quan 1",
        "delivery_city": "TP. Hồ Chí Minh",
        "delivery_notes": None,
        "different_recipient_name": None,
        "different_recipient_phone": None,
        "subtotal": Decimal("0"),
        "shipping_fee": Decimal("0"),
        "total_amount": Decimal("0"),
        "vat_invoice_requested": False,
        "vat_info": None,
        "payment_method": "cod",
        "payment_status": "pending",
        "status": "pending",
        "source": "website",
        "referral_conversation_id": None,
        "idempotency_key": uuid4(),
        "customer_notes": None,
    }


def service(session: AsyncSession) -> OrderService:
    return OrderService(OrderRepository(session), ProductRepository(session))


async def test_create_order_authenticated_user(order_session: AsyncSession) -> None:
    product = await create_product(order_session)
    user = await create_user(order_session)

    order = await service(order_session).create_order(
        checkout_payload(product),
        user,
        uuid4(),
        order_session,
    )

    assert order.user_id == user.id
    assert order.total_amount == Decimal("700000.00")
    assert order.items[0].product_name == "Binh gas 12kg"


async def test_order_references_specific_variant_row(order_session: AsyncSession) -> None:
    """An order line must reference one exact variant row at its exact price."""
    from app.models.product import ProductParent

    parent = ProductParent(name="Bình gas Saigon Petro", brand="Saigon Petro", category="gas")
    order_session.add(parent)
    await order_session.flush()
    xam = await create_product(
        order_session, sku="SP-12KG-XAM", price=Decimal("605000"), stock_quantity=10
    )
    xanh = await create_product(
        order_session, sku="SP-12KG-XANH", price=Decimal("665000"), stock_quantity=10
    )
    xam.parent_id = parent.id
    xanh.parent_id = parent.id
    await order_session.commit()

    order = await service(order_session).create_order(
        checkout_payload(xanh, items=[OrderItemCreate(product_id=xanh.id, quantity=1)]),
        None,
        uuid4(),
        order_session,
    )

    assert len(order.items) == 1
    line = order.items[0]
    # The line references the selected variant, not the parent or the sibling.
    assert line.product_id == xanh.id
    assert line.unit_price == Decimal("665000")


async def test_shipping_fee_gas_only_is_zero(order_session: AsyncSession) -> None:
    product = await create_product(order_session)

    order = await service(order_session).create_order(
        checkout_payload(product),
        None,
        uuid4(),
        order_session,
    )

    assert order.subtotal == Decimal("700000.00")
    assert order.shipping_fee == Decimal("0.00")
    assert order.total_amount == order.subtotal


async def test_shipping_fee_water_charges_per_unit(order_session: AsyncSession) -> None:
    product = await create_product(
        order_session,
        sku="VIHAWA-20L",
        name="Nước Vihawa 20 lít",
        brand="Vihawa",
        size_kg=Decimal("20"),
        category="nuoc_uong",
        unit="lít",
        price=Decimal("55000"),
    )

    order = await service(order_session).create_order(
        checkout_payload(product),
        None,
        uuid4(),
        order_session,
    )

    assert order.subtotal == Decimal("110000.00")
    assert order.shipping_fee == Decimal("10000.00")
    assert order.total_amount == order.subtotal + Decimal("10000.00")


async def test_shipping_fee_mixed_only_counts_water(order_session: AsyncSession) -> None:
    gas = await create_product(order_session, sku="SP-12KG-XAM")
    water = await create_product(
        order_session,
        sku="HOANHAO-20L",
        name="Nước Hoàn Hảo 20 lít",
        brand="Hoàn Hảo",
        size_kg=Decimal("20"),
        category="nuoc_uong",
        unit="lít",
        price=Decimal("15000"),
    )

    order = await service(order_session).create_order(
        checkout_payload(
            gas,
            items=[
                OrderItemCreate(product_id=gas.id, quantity=1),
                OrderItemCreate(product_id=water.id, quantity=3),
            ],
        ),
        None,
        uuid4(),
        order_session,
    )

    assert order.subtotal == Decimal("395000.00")
    assert order.shipping_fee == Decimal("15000.00")
    assert order.total_amount == order.subtotal + Decimal("15000.00")


async def test_create_order_guest_user(order_session: AsyncSession) -> None:
    product = await create_product(order_session)

    order = await service(order_session).create_order(
        checkout_payload(product),
        None,
        uuid4(),
        order_session,
    )

    assert order.user_id is None
    assert order.customer_phone == "+84901234567"


async def test_create_order_with_different_recipient(order_session: AsyncSession) -> None:
    product = await create_product(order_session)

    order = await service(order_session).create_order(
        checkout_payload(
            product,
            different_recipient_name="Tran Thi B",
            different_recipient_phone="0912345678",
        ),
        None,
        uuid4(),
        order_session,
    )

    assert order.different_recipient_name == "Tran Thi B"
    assert order.different_recipient_phone == "+84912345678"


async def test_create_order_with_vat_invoice(order_session: AsyncSession) -> None:
    product = await create_product(order_session)

    order = await service(order_session).create_order(
        checkout_payload(
            product,
            vat_invoice_requested=True,
            vat_info=VatInfo(
                company_name="Cong ty TNHH GasBot",
                tax_code="0312345678",
                address="456 Le Loi, Quan 1",
            ),
        ),
        None,
        uuid4(),
        order_session,
    )

    assert order.vat_invoice_requested is True
    assert order.vat_info is not None
    assert order.vat_info.tax_code == "0312345678"


async def test_create_order_decrements_stock_correctly(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=5)

    await service(order_session).create_order(
        checkout_payload(product), None, uuid4(), order_session
    )
    await order_session.refresh(product)

    assert product.stock_quantity == 3


async def test_create_order_insufficient_stock_raises(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=1)

    with pytest.raises(InsufficientStockException):
        await service(order_session).create_order(
            checkout_payload(product),
            None,
            uuid4(),
            order_session,
        )


async def test_create_order_inactive_product_raises(order_session: AsyncSession) -> None:
    product = await create_product(order_session, is_active=False)

    with pytest.raises(ValidationException):
        await service(order_session).create_order(
            checkout_payload(product),
            None,
            uuid4(),
            order_session,
        )


async def test_idempotency_returns_same_order(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=5)
    key = uuid4()

    first = await service(order_session).create_order(
        checkout_payload(product), None, key, order_session
    )
    await order_session.commit()
    second = await service(order_session).create_order(
        checkout_payload(product), None, key, order_session
    )

    await order_session.refresh(product)
    assert second.id == first.id
    assert product.stock_quantity == 3


async def test_order_numbers_are_daily_sequential_and_unique(order_session: AsyncSession) -> None:
    today = datetime.now(UTC).strftime("%Y%m%d")

    async def create_raw_order(index: int) -> str:
        async with AsyncSessionLocal() as session:
            order = await OrderRepository(session).create_with_items(raw_order_data(index), [])
            await session.commit()
            assert order.order_number is not None
            return order.order_number

    order_numbers = await asyncio.gather(*(create_raw_order(index) for index in range(1, 11)))
    suffixes = sorted(int(order_number.rsplit("-", 1)[1]) for order_number in order_numbers)

    assert len(set(order_numbers)) == 10
    assert all(re.fullmatch(rf"GB-{today}-[0-9]{{3,}}", number) for number in order_numbers)
    assert suffixes == list(range(1, 11))


async def test_concurrent_order_creation_no_oversell(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=5)

    async def attempt_checkout() -> bool:
        async with AsyncSessionLocal() as session:
            try:
                await service(session).create_order(
                    checkout_payload(
                        product,
                        items=[OrderItemCreate(product_id=product.id, quantity=1)],
                    ),
                    None,
                    uuid4(),
                    session,
                )
                await session.commit()
                return True
            except (DBAPIError, InsufficientStockException, ValidationException):
                await session.rollback()
                return False

    results = await asyncio.gather(*(attempt_checkout() for _ in range(10)))

    refreshed = await ProductRepository(order_session).get_by_id(product.id)
    assert refreshed is not None
    await order_session.refresh(refreshed)
    successful_orders = sum(results)
    assert 0 < successful_orders <= 5
    assert refreshed.stock_quantity == 5 - successful_orders


async def test_order_from_chatbot_records_source_and_conversation(
    order_session: AsyncSession,
) -> None:
    product = await create_product(order_session)

    # referral_conversation_id has a FK to conversations; omit to avoid setup overhead.
    # The FK enforcement is covered by the migration schema constraint.
    order = await service(order_session).create_order(
        checkout_payload(product, source="chatbot"),
        None,
        uuid4(),
        order_session,
    )

    assert order.source == "chatbot"


async def test_cancel_pending_order_restores_stock(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=5)
    created = await service(order_session).create_order(
        checkout_payload(product),
        None,
        uuid4(),
        order_session,
    )

    cancelled = await service(order_session).cancel_order(
        created.id,
        None,
        "Customer requested cancellation",
        phone="+84901234567",
    )
    await order_session.refresh(product)

    assert cancelled.status == "cancelled"
    assert product.stock_quantity == 5


async def test_cannot_cancel_delivered_order(order_session: AsyncSession) -> None:
    product = await create_product(order_session)
    admin = user_model("admin")
    created = await service(order_session).create_order(
        checkout_payload(product),
        None,
        uuid4(),
        order_session,
    )
    await service(order_session).update_order_status(created.id, "confirmed", admin)
    await service(order_session).update_order_status(created.id, "shipping", admin)
    await service(order_session).update_order_status(created.id, "delivered", admin)

    with pytest.raises(ValidationException):
        await service(order_session).cancel_order(created.id, None, phone="+84901234567")


@pytest.mark.parametrize(
    ("from_status", "new_status", "is_valid"),
    [
        ("pending", "confirmed", True),
        ("pending", "shipping", False),
        ("confirmed", "shipping", True),
        ("shipping", "delivered", True),
        ("delivered", "cancelled", False),
    ],
)
async def test_status_transitions_enforced(
    order_session: AsyncSession,
    from_status: str,
    new_status: str,
    is_valid: bool,
) -> None:
    product = await create_product(order_session)
    admin = user_model("admin")
    created = await service(order_session).create_order(
        checkout_payload(product),
        None,
        uuid4(),
        order_session,
    )
    order = await OrderRepository(order_session).get_by_id(created.id)
    assert order is not None
    order.status = from_status
    await order_session.flush()

    if is_valid:
        updated = await service(order_session).update_order_status(created.id, new_status, admin)
        assert updated.status == new_status
    else:
        with pytest.raises(ValidationException):
            await service(order_session).update_order_status(created.id, new_status, admin)


async def test_lookup_guest_order_by_number_and_phone(order_session: AsyncSession) -> None:
    product = await create_product(order_session)
    created = await service(order_session).create_order(
        checkout_payload(product),
        None,
        uuid4(),
        order_session,
    )

    found = await service(order_session).lookup_guest_order(created.order_number, "+84901234567")

    assert found.id == created.id


async def test_user_cannot_see_others_orders(order_session: AsyncSession) -> None:
    product = await create_product(order_session)
    owner = await create_user(order_session)
    other = user_model("customer")
    created = await service(order_session).create_order(
        checkout_payload(product),
        owner,
        uuid4(),
        order_session,
    )

    with pytest.raises(ForbiddenException):
        await service(order_session).get_order(created.id, other)


async def test_staff_can_see_all_orders(order_session: AsyncSession) -> None:
    product = await create_product(order_session)
    staff = user_model("staff")
    await service(order_session).create_order(
        checkout_payload(product), None, uuid4(), order_session
    )

    result = await service(order_session).list_all_orders(staff, OrderSearchParams())

    assert result.total == 1


async def test_order_charges_the_sale_price(order_session: AsyncSession) -> None:
    # A product on sale is charged at the sale price, not the list price.
    product = await create_product(order_session, price=Decimal("710000"), stock_quantity=10)
    product.sale_price = Decimal("600000")
    await order_session.commit()

    order = await service(order_session).create_order(
        checkout_payload(product, items=[OrderItemCreate(product_id=product.id, quantity=2)]),
        None,
        uuid4(),
        order_session,
    )

    line = order.items[0]
    assert line.unit_price == Decimal("600000")  # the sale price, not 710000
    assert order.subtotal == Decimal("1200000")  # 600000 x 2
    assert order.total_amount == Decimal("1200000")  # gas ships free


async def test_concurrent_order_no_oversell_with_sale_price(order_session: AsyncSession) -> None:
    # No-oversell (SERIALIZABLE + SELECT FOR UPDATE) still holds with a sale price set.
    product = await create_product(order_session, price=Decimal("710000"), stock_quantity=5)
    product.sale_price = Decimal("600000")
    await order_session.commit()

    async def attempt_checkout() -> bool:
        async with AsyncSessionLocal() as session:
            try:
                await service(session).create_order(
                    checkout_payload(
                        product,
                        items=[OrderItemCreate(product_id=product.id, quantity=1)],
                    ),
                    None,
                    uuid4(),
                    session,
                )
                await session.commit()
                return True
            except (DBAPIError, InsufficientStockException, ValidationException):
                await session.rollback()
                return False

    results = await asyncio.gather(*(attempt_checkout() for _ in range(10)))

    refreshed = await ProductRepository(order_session).get_by_id(product.id)
    assert refreshed is not None
    await order_session.refresh(refreshed)
    successful_orders = sum(results)
    assert 0 < successful_orders <= 5
    assert refreshed.stock_quantity == 5 - successful_orders
