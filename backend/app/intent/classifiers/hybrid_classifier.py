"""Hybrid intent classifier combining embedding and LLM results."""

import re
import unicodedata
from collections.abc import Mapping, Sequence

import sentry_sdk

from app.intent.base import BaseIntentClassifier
from app.intent.categories import IntentCategory
from app.intent.schemas import IntentResult
from app.llm.exceptions import LLMQuotaExceededError, LLMRateLimitError


class HybridIntentClassifier(BaseIntentClassifier):
    """Use embeddings first, with LLM fallback for uncertain or safety cases."""

    def __init__(
        self,
        embedding_classifier: BaseIntentClassifier,
        llm_classifier: BaseIntentClassifier,
        confidence_threshold: float = 0.7,
    ) -> None:
        self.embedding_classifier = embedding_classifier
        self.llm_classifier = llm_classifier
        self.confidence_threshold = confidence_threshold

    async def classify(
        self,
        text: str,
        conversation_history: Sequence[Mapping[str, str]] | None = None,
    ) -> IntentResult:
        """Classify with embedding, then double-check when required."""
        if self._is_bare_product_category(text):
            return IntentResult(
                category=IntentCategory.PRODUCT_INQUIRY,
                confidence=0.95,
                reasoning="Bare product category should show catalog cards, not start checkout",
                classifier="hybrid_category_keyword",
            )

        try:
            embedding_result = await self.embedding_classifier.classify(
                text,
                conversation_history,
            )
        except (LLMQuotaExceededError, LLMRateLimitError):
            sentry_sdk.capture_message(
                "Gemini embed quota exceeded, intent via LLM fallback",
                level="warning",
            )
            llm_result = await self.llm_classifier.classify(text, conversation_history)
            return IntentResult(
                category=llm_result.category,
                confidence=llm_result.confidence,
                reasoning=llm_result.reasoning,
                classifier="llm_fallback",
            )
        must_check_llm = (
            embedding_result.category == IntentCategory.SAFETY_EMERGENCY
            or embedding_result.confidence < self.confidence_threshold
        )
        if not must_check_llm:
            return IntentResult(
                category=embedding_result.category,
                confidence=embedding_result.confidence,
                reasoning=embedding_result.reasoning,
                classifier="hybrid_embedding",
            )

        llm_result = await self.llm_classifier.classify(text, conversation_history)
        if (
            embedding_result.category == IntentCategory.SAFETY_EMERGENCY
            or llm_result.category == IntentCategory.SAFETY_EMERGENCY
        ):
            return IntentResult(
                category=IntentCategory.SAFETY_EMERGENCY,
                confidence=max(embedding_result.confidence, llm_result.confidence),
                reasoning="Safety emergency confirmed by hybrid double-check",
                classifier="hybrid_safety",
            )

        return IntentResult(
            category=llm_result.category,
            confidence=llm_result.confidence,
            reasoning=llm_result.reasoning,
            classifier="hybrid_llm",
        )

    @classmethod
    def _is_bare_product_category(cls, text: str) -> bool:
        normalized = cls._normalize_text(text)
        return normalized in {"gas", "binh gas", "nuoc", "nuoc uong"}

    @staticmethod
    def _normalize_text(text: str) -> str:
        decomposed = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
        without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
        return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()
