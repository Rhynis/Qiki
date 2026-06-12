import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge Tailwind class names safely. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const NBSP = String.fromCharCode(160)

// Phrases to keep on a single line (proper nouns + phrases that lose meaning when
// wrapped). Order longer phrases before shorter ones so the longer match is
// replaced first (e.g. "Thành phố Hồ Chí Minh" before "Hồ Chí Minh",
// "Hiệp Bình Chánh" before "Hiệp Bình").
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
 * Replace spaces inside proper-noun / fixed phrases with a non-breaking space so
 * the text doesn't break mid-phrase (e.g. "Bình Thạnh" won't split into "Bình"
 * / "Thạnh"). Remaining spaces are left intact so the sentence still wraps normally.
 */
export function protectVi(text: string): string {
  return PROTECTED_PHRASES.reduce(
    (acc, phrase) => acc.split(phrase).join(phrase.split(' ').join(NBSP)),
    text
  )
}
