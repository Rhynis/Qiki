"""Tests for RAG context construction."""

from uuid import uuid4

from app.rag.context_builder import ContextBuilder
from app.rag.schemas import RetrievedDocument


def doc(title: str, content: str, similarity: float = 0.8) -> RetrievedDocument:
    return RetrievedDocument(
        id=uuid4(),
        title=title,
        content=content,
        category="faq",
        similarity=similarity,
        source_type="hybrid",
    )


def test_build_context_with_multiple_docs() -> None:
    context = ContextBuilder().build_context(
        [
            doc("Thanh toán COD", "Khách hàng có thể thanh toán khi nhận hàng."),
            doc("Giao hàng", "GasBot giao hàng trong nội thành TP.HCM."),
        ]
    )

    assert "Tài liệu 1" in context
    assert "Thanh toán COD" in context
    assert "Tài liệu 2" in context
    assert "Giao hàng" in context


def test_build_context_respects_max_chars() -> None:
    context = ContextBuilder().build_context(
        [
            doc("Dài", "A" * 180),
            doc("Cũng dài", "B" * 180),
        ],
        max_chars=180,
    )

    assert len(context) <= 183
    assert context.endswith("...")


def test_build_context_handles_empty_docs() -> None:
    assert ContextBuilder().build_context([]) == "Không có thông tin liên quan trong cơ sở dữ liệu."


def test_build_context_includes_product_catalog_context() -> None:
    context = ContextBuilder().build_context(
        [],
        product_context="Bảng giá sản phẩm hiện có:\n- Bình gas Petrolimex 12kg: 440.000đ",
    )

    assert "Thông tin từ cơ sở kiến thức" in context
    assert "Thông tin sản phẩm đang bán" in context
    assert "Bình gas Petrolimex 12kg" in context
    assert "440.000đ" in context


def test_format_conversation_history_with_recent_messages() -> None:
    messages = [
        {"role": "system", "content": "start"},
        {"role": "user", "content": "Tôi cần mua gas"},
        {"role": "assistant", "content": "Bạn cần loại nào?"},
        {"role": "staff", "content": "Tôi hỗ trợ thêm"},
    ]

    history = ContextBuilder().format_conversation_history(messages, max_messages=3)

    assert "start" not in history
    assert "Khách hàng: Tôi cần mua gas" in history
    assert "Bot: Bạn cần loại nào?" in history
    assert "Nhân viên: Tôi hỗ trợ thêm" in history


def test_format_conversation_history_handles_empty() -> None:
    assert ContextBuilder().format_conversation_history([]) == "(Chưa có lịch sử trò chuyện)"
