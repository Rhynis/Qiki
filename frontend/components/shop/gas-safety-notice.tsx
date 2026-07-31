import { AlertTriangle } from 'lucide-react'

// Fixed Vietnamese gas-safety notice shown under the description on gas product
// pages. Kept as a single constant so it does not drift; the emergency hotline
// (090 3026306 / 114 / 115) must stay in sync with the chatbot's
// SAFETY_EMERGENCY_RESPONSE_VI constant in backend/app/rag/safety.py.
export const GAS_SAFETY_NOTICE_VI = `An toàn sử dụng gas
• Khóa van bình gas sau mỗi lần sử dụng.
• Kiểm tra dây dẫn, van và bếp định kỳ; thay khi có dấu hiệu rò rỉ, nứt, mòn.
• Đặt bình nơi thoáng khí, thẳng đứng, tránh xa nguồn nhiệt và tia lửa điện.
• Khi ngửi thấy mùi gas: KHÔNG bật/tắt công tắc điện hay lửa, khóa van bình, mở cửa cho thông thoáng.
• Sự cố khẩn cấp (rò rỉ nhiều, cháy): gọi ngay hotline 090 3026306 — hoặc 114 (cứu hỏa) / 115 (cấp cứu).`

/**
 * Subtle warning card with the gas-safety notice. Render only for gas products.
 * Styled with brand tokens (no hardcoded colours) so it fits other gas pages too.
 */
export function GasSafetyNotice() {
  return (
    <div
      role="note"
      aria-label="An toàn sử dụng gas"
      className="rounded-lg border border-primary/20 bg-primary/5 p-4 text-sm text-slate-700"
    >
      <div className="flex gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
        <p className="whitespace-pre-line leading-6">{GAS_SAFETY_NOTICE_VI}</p>
      </div>
    </div>
  )
}
