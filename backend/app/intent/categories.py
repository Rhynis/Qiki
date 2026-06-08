"""Intent categories and routing metadata for GasBot conversations."""

from enum import StrEnum
from typing import TypedDict


class IntentCategory(StrEnum):
    """Supported customer intent categories."""

    PRODUCT_INQUIRY = "product_inquiry"
    PLACE_ORDER = "place_order"
    DELIVERY_STATUS = "delivery_status"
    COMPLAINT = "complaint"
    TECHNICAL_ISSUE = "technical_issue"
    SAFETY_EMERGENCY = "safety_emergency"
    PAYMENT_ISSUE = "payment_issue"
    GENERAL_INFO = "general_info"


class IntentRoutingRule(TypedDict):
    """Routing metadata attached to an intent."""

    requires_human: bool
    priority: int
    auto_response: bool


INTENT_EXAMPLES: dict[IntentCategory, list[str]] = {
    IntentCategory.PRODUCT_INQUIRY: [
        "Binh gas 12kg gia bao nhieu?",
        "Co ban gas Petrolimex khong?",
        "Loai gas nao phu hop cho gia dinh?",
        "Gia binh gas hom nay the nao?",
        "Binh gas nao tiet kiem nhat?",
        "Co ban nuoc Hoan Hao khong?",
        "Nuoc Vihawa 20 lit gia bao nhieu?",
        "Nuoc",
        "Gas",
    ],
    IntentCategory.PLACE_ORDER: [
        "Toi muon dat mot binh gas",
        "Dat 2 binh 12kg giao Quan 1",
        "Mua gas giup toi",
        "Cho toi dat hang ngay bay gio",
        "Can giao mot binh gas chieu nay",
    ],
    IntentCategory.DELIVERY_STATUS: [
        "Don hang cua toi den dau roi?",
        "Khi nao giao gas?",
        "Tai sao don cua toi chua toi?",
        "Kiem tra trang thai giao hang",
        "Shipper sap den chua?",
    ],
    IntentCategory.COMPLAINT: [
        "Binh gas bi thieu can",
        "Nhan vien giao hang tho lo",
        "Toi khong hai long ve dich vu",
        "Gas moi doi nhung rat nhanh het",
        "Can khieu nai don hang",
    ],
    IntentCategory.TECHNICAL_ISSUE: [
        "Bep gas khong bat duoc",
        "Cach lap van gas an toan",
        "Van binh gas bi ket",
        "Can huong dan thay day dan gas",
        "Lua bep gas bi do",
    ],
    IntentCategory.SAFETY_EMERGENCY: [
        "Toi ngui thay mui gas",
        "Hinh nhu co ro ri gas",
        "Bep gas bi chay",
        "Nghe tieng xi tu binh gas",
        "Gas boc mui trong bep",
    ],
    IntentCategory.PAYMENT_ISSUE: [
        "Toi chua nhan hoa don",
        "Tien da tru nhung don chua duyet",
        "Thanh toan that bai",
        "Co the xuat VAT khong?",
        "Can doi phuong thuc thanh toan",
    ],
    IntentCategory.GENERAL_INFO: [
        "Cua hang mo cua may gio?",
        "Dia chi cong ty o dau?",
        "Co giao hang cuoi tuan khong?",
        "Hotline la so nao?",
        "Khu vuc nao duoc giao hang?",
    ],
}


INTENT_ROUTING_RULES: dict[IntentCategory, IntentRoutingRule] = {
    IntentCategory.PRODUCT_INQUIRY: {
        "requires_human": False,
        "priority": 3,
        "auto_response": True,
    },
    IntentCategory.PLACE_ORDER: {
        "requires_human": False,
        "priority": 2,
        "auto_response": True,
    },
    IntentCategory.DELIVERY_STATUS: {
        "requires_human": False,
        "priority": 2,
        "auto_response": True,
    },
    IntentCategory.COMPLAINT: {
        "requires_human": True,
        "priority": 1,
        "auto_response": False,
    },
    IntentCategory.TECHNICAL_ISSUE: {
        "requires_human": False,
        "priority": 2,
        "auto_response": True,
    },
    IntentCategory.SAFETY_EMERGENCY: {
        "requires_human": True,
        "priority": 0,
        "auto_response": False,
    },
    IntentCategory.PAYMENT_ISSUE: {
        "requires_human": False,
        "priority": 1,
        "auto_response": True,
    },
    IntentCategory.GENERAL_INFO: {
        "requires_human": False,
        "priority": 4,
        "auto_response": True,
    },
}
