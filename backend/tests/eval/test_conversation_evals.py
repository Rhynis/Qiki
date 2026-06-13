"""Scripted multi-turn conversation evals (deterministic, must-pass).

Each scenario drives the real ConversationService through a dialogue and asserts
hard invariants that guard against the recurring chat regressions. These run
unconditionally (no LLM judge / no network). Judged metrics live in
``test_judged_metrics.py`` and are skipped unless a key is present.
"""

from __future__ import annotations

import pytest

from app.intent.categories import IntentCategory
from app.rag.safety import SAFETY_EMERGENCY_RESPONSE_VI, SafetyChecker
from tests.eval.harness import ConversationDriver, run_full_gas_order, start_driver
from tests.services.test_conversation_service import (
    FakeLLMProvider,
    FakeProductService,
    _prod_gas_catalog,
    _water_catalog,
    account_user,
    add_order_state_history,
    complete_order_payload,
    complete_water_confirmation_slots,
    make_service,
)


@pytest.mark.asyncio
async def test_specific_gas_order_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Order Petrolimex 12kg -> summary shown -> confirm -> order created."""
    driver, orders = await run_full_gas_order(monkeypatch)

    summary_reply = driver.turns[0][1]
    assert "Qiki tóm tắt đơn hàng" in summary_reply
    assert "Bạn xác nhận đặt đơn này không?" in summary_reply

    final_reply = driver.turns[1][1]
    assert orders.created_count == 1
    assert "Đã ghi nhận đơn" in final_reply
    assert "QC-000123" in final_reply

    case = driver.to_test_case(
        scenario="Khách đặt 1 bình gas Petrolimex 12kg rồi xác nhận.",
        expected_outcome="Bot tóm tắt đơn, chờ xác nhận, rồi tạo đơn khi khách đồng ý.",
        name="specific_gas_order",
    )
    assert len(case.turns) == 4


@pytest.mark.asyncio
async def test_add_gas_item_asks_size_no_phantom_missing_product() -> None:
    """'thêm 1 bình gas' asks the size and never invents a 'thiếu sản phẩm' (guards #169)."""
    products = _water_catalog() + _prod_gas_catalog()
    service, _conversations, messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([{}]),
        product_service=FakeProductService(products=products),
    )
    conversation = await service.start_conversation(user=None, session_id="eval")
    await add_order_state_history(
        messages,
        conversation.id,
        status="awaiting_confirmation",
        slots=complete_water_confirmation_slots(),
    )
    driver = ConversationDriver(service=service, conversation_id=conversation.id)

    response = await driver.turn("thêm 1 bình gas đi")

    assert response.assistant_message is not None
    reply = response.assistant_message.content
    assert "gas loại 6, 12, 45 kg" in reply
    assert "bao nhiêu kg" in reply
    assert "thiếu sản phẩm" not in reply
    assert "xin thêm sản phẩm" not in reply
    assert orders.created_count == 0
    assert response.assistant_message.retrieved_documents[0]["status"] == "awaiting_product_choice"


@pytest.mark.asyncio
async def test_keu_nhan_vien_mid_order_handoff_not_summary() -> None:
    """'kêu nhân viên' mid-order escalates to a human, not an order summary (guards #179)."""
    service, _conversations, messages, rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        product_service=FakeProductService(products=_water_catalog()),
    )
    conversation = await service.start_conversation(user=None, session_id="eval")
    await add_order_state_history(
        messages,
        conversation.id,
        status="awaiting_confirmation",
        slots=complete_water_confirmation_slots(),
    )
    driver = ConversationDriver(service=service, conversation_id=conversation.id)

    response = await driver.turn("kêu nhân viên cho tui")

    assert response.conversation.status == "escalated"
    assert response.assistant_message is not None
    reply = response.assistant_message.content
    assert "nhân viên" in reply
    assert "Qiki tóm tắt đơn hàng" not in reply
    assert orders.created_count == 0
    assert rag.calls == 0


@pytest.mark.asyncio
async def test_out_of_area_rejected_in_area_accepted() -> None:
    """Out-of-area address is declined; in-area Bình Lợi Trung is accepted (guards #179)."""
    service_out, _c1, _m1, _r1, orders_out = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider(
            [complete_order_payload(address="12 Lê Lợi, Phường Bến Nghé, Quận 1")]
        ),
    )
    driver_out = await start_driver(service_out)
    out_response = await driver_out.turn("Đặt Petrolimex giao qua Quận 1 giúp tôi")

    assert orders_out.calls == 0
    assert out_response.assistant_message is not None
    assert "chỉ giao trong khu vực Bình Thạnh và Thủ Đức" in out_response.assistant_message.content

    service_in, _c2, messages_in, _r2, _orders_in = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider(
            [
                {
                    "customer_name": "Nick",
                    "delivery_address": "15 đường 5, khu phố 32",
                    "payment_method": "bank_transfer",
                }
            ]
        ),
        product_service=FakeProductService(products=_water_catalog()),
    )
    conversation_in = await service_in.start_conversation(user=None, session_id="eval-in")
    await add_order_state_history(
        messages_in,
        conversation_in.id,
        slots={
            "items": [{"product": "Nước Hoàn Hảo 20 lít", "quantity": 1}],
            "customer_name": "Vân",
            "customer_phone": "0903026306",
        },
    )
    driver_in = ConversationDriver(service=service_in, conversation_id=conversation_in.id)
    in_response = await driver_in.turn("nick 15 đường 5, khu phố 32 phường bình lợi trung ck")

    assert in_response.assistant_message is not None
    in_reply = in_response.assistant_message.content
    assert "chỉ giao trong khu vực Bình Thạnh và Thủ Đức" not in in_reply
    assert "Qiki tóm tắt đơn hàng" in in_reply


@pytest.mark.asyncio
async def test_safety_emergency_constant_response_no_llm() -> None:
    """Safety emergency returns the constant hotline response without calling the LLM.

    NB: the issue references '1900-1234' but the live constant uses the real
    hotline '090 3026306' (+ 114/115); we assert against the real value.
    """
    llm = FakeLLMProvider()
    service, _conversations, _messages, _rag, _orders = make_service(
        category=IntentCategory.SAFETY_EMERGENCY,
        requires_human=True,
        llm_provider=llm,
    )
    driver = await start_driver(service)

    response = await driver.turn("Toi ngui mui gas")

    assert response.assistant_message is not None
    reply = response.assistant_message.content
    assert "090 3026306" in reply
    assert "114" in reply
    assert "115" in reply
    assert response.assistant_message.is_emergency is True
    assert response.conversation.status == "escalated"
    # The conversation LLM (slot extraction) is never invoked for safety.
    assert llm.calls == 0

    # The underlying safety constant is LLM-free and carries the hotline.
    assert "090 3026306" in SAFETY_EMERGENCY_RESPONSE_VI
    assert SafetyChecker().get_emergency_response() == SAFETY_EMERGENCY_RESPONSE_VI


@pytest.mark.asyncio
async def test_logged_in_prefill_still_requires_confirmation() -> None:
    """Logged-in user: name/phone prefilled from the account, confirmation still required (#173)."""
    payload = complete_order_payload(confirmed=True)
    payload["customer_name"] = None
    payload["customer_phone"] = None
    service, _conversations, _messages, _rag, orders = make_service(
        category=IntentCategory.PLACE_ORDER,
        llm_provider=FakeLLMProvider([payload, {"confirmed": True}]),
    )
    user = account_user()
    driver = await start_driver(service)

    account_confirmation = await driver.turn("Tôi muốn đặt 1 bình Petrolimex 12kg", user=user)
    assert orders.calls == 0
    assert account_confirmation.assistant_message is not None
    confirm_reply = account_confirmation.assistant_message.content
    assert "Tran Minh Quan" in confirm_reply
    assert "0903026306" in confirm_reply
    assert "theo tài khoản" in confirm_reply

    summary = await driver.turn("ok xác nhận đơn", user=user)
    assert orders.calls == 0
    assert summary.assistant_message is not None
    assert "Qiki tóm tắt đơn hàng" in summary.assistant_message.content

    created = await driver.turn("ok xác nhận đơn", user=user)
    assert orders.calls == 1
    assert orders.last_user == user
    assert created.assistant_message is not None
    assert "Đã ghi nhận đơn" in created.assistant_message.content
