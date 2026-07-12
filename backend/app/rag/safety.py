"""Safety detection for emergency gas queries.

The primary goal is 100% recall on safety-critical queries. False positives are
acceptable; false negatives for real emergencies are not.
"""

import re
import unicodedata
from re import Pattern
from typing import ClassVar

from app.core.logging import get_logger
from app.rag.schemas import SafetyResult

SAFETY_EMERGENCY_RESPONSE_VI = """⚠️ CẢNH BÁO AN TOÀN ⚠️

Đây có thể là tình huống NGUY HIỂM. Vui lòng thực hiện NGAY các bước sau:

1. KHÔNG bật/tắt bất kỳ thiết bị điện nào (kể cả công tắc đèn, quạt)
2. KHÔNG sử dụng lửa, KHÔNG hút thuốc
3. Mở RỘNG cửa sổ và cửa ra vào để thông gió
4. Đóng van bình gas NẾU có thể tiếp cận an toàn
5. Sơ tán mọi người ra khỏi khu vực, đến nơi thoáng đãng
6. KHÔNG bật điện thoại trong khu vực nghi ngờ rò gas

🚨 GỌI NGAY các số khẩn cấp:
- Cảnh sát PCCC: 114
- Cấp cứu: 115
- Hotline Gas Quốc Cường: 090 3026306

⛔ KHÔNG tự xử lý. Hãy gọi kỹ thuật viên chuyên nghiệp.

Tôi đang chuyển cuộc trò chuyện này đến nhân viên hỗ trợ. Vui lòng chờ trong giây lát.
Bạn có an toàn không?"""

SAFETY_EMERGENCY_RESPONSE_EN = """⚠️ SAFETY WARNING ⚠️

This may be a DANGEROUS situation. Please do the following NOW:

1. Do NOT switch any electrical device on/off (including light switches, fans)
2. Do NOT use fire, do NOT smoke
3. Open windows and doors WIDE to ventilate
4. Close the gas cylinder valve IF you can reach it safely
5. Evacuate everyone from the area to an open space
6. Do NOT use your phone inside the suspected gas-leak area

🚨 CALL these emergency numbers NOW:
- Fire department: 114
- Emergency medical: 115
- Gas Quốc Cường hotline: 090 3026306

⛔ Do NOT handle it yourself. Call a professional technician.

I'm transferring this conversation to a support agent. Please wait a moment.
Are you safe?"""


class SafetyChecker:
    """Detect safety-critical queries and return audited emergency guidance."""

    EMERGENCY_KEYWORDS_VI: ClassVar[list[str]] = [
        "rò gas",
        "ro gas",
        "rò rỉ gas",
        "ro ri gas",
        "rò khí gas",
        "xì gas",
        "xi gas",
        "thoát gas",
        "thoat gas",
        "khí gas thoát",
        "khi gas thoat",
        "gas thoát ra",
        "gas thoat ra",
        "gas đang thoát",
        "gas dang thoat",
        "gas tràn",
        "gas tran",
        "mùi gas",
        "mui gas",
        "ngửi thấy gas",
        "ngui thay gas",
        "ngửi mùi gas",
        "ngui mui gas",
        "gas nồng nặc",
        "gas nong nac",
        "bốc mùi gas",
        "boc mui gas",
        "cháy",
        "chay",
        "cháy nổ",
        "chay no",
        "phát nổ",
        "phat no",
        "nổ bình gas",
        "no binh gas",
        "nổ gas",
        "no gas",
        "gas nổ",
        "gas no",
        "bình gas nổ",
        "binh gas no",
        "bốc lửa",
        "boc lua",
        "bắt lửa",
        "bat lua",
        "đang cháy",
        "dang chay",
        "lửa cháy",
        "lua chay",
        "ngạt",
        "ngat",
        "khó thở",
        "kho tho",
        "ngạt thở",
        "ngat tho",
        "ngạt khí",
        "ngat khi",
        "khẩn cấp",
        "khan cap",
        "nguy hiểm",
        "nguy hiem",
        "cấp cứu",
        "cap cuu",
        "tai nạn",
        "tai nan",
    ]

    EMERGENCY_KEYWORDS_EN: ClassVar[list[str]] = [
        "gas leak",
        "gas leaking",
        "leaking gas",
        "smell gas",
        "smell of gas",
        "gas smell",
        "smelling gas",
        "explosion",
        "explode",
        "exploded",
        "on fire",
        "catching fire",
        "fire",
        "burning",
        "suffocat",
        "can't breathe",
        "cannot breathe",
        "cant breathe",
        "choking",
        "emergency",
        "dangerous",
    ]

    SUSPICIOUS_PATTERNS: ClassVar[list[Pattern[str]]] = [
        re.compile(r"c[oó].*gas.*tho[aá]t ra", re.IGNORECASE),
        re.compile(r"gas.*tho[aá]t ra", re.IGNORECASE),
        re.compile(r"gas.*r[iỉ].*ra ngo[aà]i", re.IGNORECASE),
        re.compile(r"b[iì]nh gas.*h[oỏ]ng.*n[aặ]ng", re.IGNORECASE),
        re.compile(r"b[iì]nh gas.*ph[iì].*kh[ií]", re.IGNORECASE),
        re.compile(r"van gas.*kh[oó]a.*kh[oô]ng.*[dđ][uư][oợ]c", re.IGNORECASE),
        re.compile(r"d[aâ]y.*gas.*n[uứ]t", re.IGNORECASE),
    ]

    # Typographic apostrophes phones emit via autocorrect (e.g. U+2019 in
    # "can't breathe"). Fold them to a straight ASCII apostrophe so emergency
    # keyword matching is not defeated by curly quotes.
    _APOSTROPHE_FOLD: ClassVar[dict[int, int]] = {
        0x2019: 0x27,  # right single quotation mark -> '
        0x2018: 0x27,  # left single quotation mark -> '
        0x02BC: 0x27,  # modifier letter apostrophe -> '
        0xFF07: 0x27,  # fullwidth apostrophe -> '
        0x0060: 0x27,  # grave accent -> '
    }

    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    def _normalize(self, query: str) -> str:
        normalized = unicodedata.normalize("NFC", query).lower()
        normalized = normalized.translate(self._APOSTROPHE_FOLD)
        return " ".join(normalized.split())

    def _ascii_fold(self, query: str) -> str:
        normalized = unicodedata.normalize("NFD", query)
        stripped = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return stripped.replace("đ", "d").replace("Đ", "D").lower()

    def _check_keywords(self, query: str) -> tuple[bool, str | None]:
        """Check critical Vietnamese and English emergency keywords."""
        query_lower = self._normalize(query)
        query_ascii = self._ascii_fold(query_lower)
        for keyword in (*self.EMERGENCY_KEYWORDS_VI, *self.EMERGENCY_KEYWORDS_EN):
            keyword_lower = self._normalize(keyword)
            if keyword_lower in query_lower or self._ascii_fold(keyword_lower) in query_ascii:
                return True, keyword
        return False, None

    def _check_patterns(self, query: str) -> tuple[bool, str | None]:
        """Check context-dependent suspicious patterns."""
        normalized = self._normalize(query)
        ascii_query = self._ascii_fold(normalized)
        for pattern in self.SUSPICIOUS_PATTERNS:
            match = pattern.search(normalized) or pattern.search(ascii_query)
            if match:
                return True, match.group(0)
        return False, None

    async def check_query(self, query: str) -> SafetyResult:
        """Return safety classification before any retrieval or LLM generation."""
        is_emergency, matched = self._check_keywords(query)
        if is_emergency:
            self.logger.warning(
                "safety_emergency_detected",
                matched_keyword=matched,
                query=query[:100],
            )
            return SafetyResult(
                is_emergency=True,
                severity="critical",
                suggested_action="emergency_response",
                detected_via="keyword",
                matched_pattern=matched,
            )

        is_pattern, matched_pattern = self._check_patterns(query)
        if is_pattern:
            self.logger.warning(
                "safety_pattern_detected",
                pattern=matched_pattern,
                query=query[:100],
            )
            return SafetyResult(
                is_emergency=True,
                severity="critical",
                suggested_action="emergency_response",
                detected_via="keyword",
                matched_pattern=matched_pattern,
            )

        return SafetyResult(
            is_emergency=False,
            severity="none",
            suggested_action="normal_response",
            detected_via="none",
        )

    def get_emergency_response(self, language: str = "vi") -> str:
        """Return the hard-coded emergency response, never generated by an LLM."""
        if language == "en":
            return SAFETY_EMERGENCY_RESPONSE_EN
        return SAFETY_EMERGENCY_RESPONSE_VI
