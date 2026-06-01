"""Build prompt context from retrieved documents and conversation history."""

from collections.abc import Mapping, Sequence

from app.rag.schemas import RetrievedDocument


class ContextBuilder:
    """Construct context strings for LLM prompts."""

    def build_context(
        self,
        documents: list[RetrievedDocument],
        max_chars: int = 3000,
        product_context: str | None = None,
    ) -> str:
        """Build a bounded context string from retrieved documents."""
        if not documents:
            knowledge_context = "Không có thông tin liên quan trong cơ sở dữ liệu."
            return self.combine_context(knowledge_context, product_context)

        parts: list[str] = []
        total_chars = 0
        for index, document in enumerate(documents, 1):
            document_text = (
                f"[Tài liệu {index} - Loại: {document.category} - "
                f"Tiêu đề: {document.title}]\n{document.content}\n"
            )
            if total_chars + len(document_text) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 100:
                    parts.append(document_text[:remaining] + "...")
                break
            parts.append(document_text)
            total_chars += len(document_text)
        knowledge_context = "\n".join(parts)
        return self.combine_context(knowledge_context, product_context)

    @staticmethod
    def combine_context(knowledge_context: str, product_context: str | None = None) -> str:
        """Combine KB context with optional live product catalog context."""
        if not product_context:
            return knowledge_context
        return (
            "Thông tin từ cơ sở kiến thức:\n"
            f"{knowledge_context}\n\n"
            "Thông tin sản phẩm đang bán:\n"
            f"{product_context.strip()}"
        )

    def format_conversation_history(
        self,
        messages: Sequence[Mapping[str, str]],
        max_messages: int = 5,
    ) -> str:
        """Format recent messages as Vietnamese conversation history."""
        if not messages:
            return "(Chưa có lịch sử trò chuyện)"

        role_labels = {
            "user": "Khách hàng",
            "assistant": "Bot",
            "staff": "Nhân viên",
            "system": "Hệ thống",
        }
        lines: list[str] = []
        for message in messages[-max_messages:]:
            raw_role = message.get("role", "")
            role = role_labels.get(raw_role, raw_role)
            content = message.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
