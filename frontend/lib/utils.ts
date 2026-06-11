import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge Tailwind class names safely. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const NBSP = String.fromCharCode(160)

// Cụm từ cần giữ nguyên trên một dòng (tên riêng + cụm dễ "rớt nghĩa"). Sắp cụm
// dài trước cụm ngắn để cụm dài được thay trước (vd "Thành phố Hồ Chí Minh"
// trước "Hồ Chí Minh", "Hiệp Bình Chánh" trước "Hiệp Bình").
const PROTECTED_PHRASES = [
  'Thành phố Hồ Chí Minh',
  'Hồ Chí Minh',
  'Hiệp Bình Chánh',
  'Hiệp Bình',
  'Bình Thạnh',
  'Thủ Đức',
  'Gas Quốc Cường',
  'trợ lý ảo Qiki',
  'trợ lý ảo',
  'chuyển khoản ngân hàng',
  'trong giờ mở cửa',
  'giờ mở cửa',
  'trước khi đặt',
  'hỗ trợ từng bước',
  'từng bước',
] as const

/**
 * Thay khoảng trắng bên trong các cụm tên riêng/cụm cố định bằng non-breaking
 * space để chữ không bị tách dòng giữa chừng (vd "Bình Thạnh" không thành "Bình"
 * / "Thạnh"). Khoảng trắng còn lại giữ nguyên nên câu vẫn xuống dòng bình thường.
 */
export function protectVi(text: string): string {
  return PROTECTED_PHRASES.reduce(
    (acc, phrase) => acc.split(phrase).join(phrase.split(' ').join(NBSP)),
    text
  )
}
