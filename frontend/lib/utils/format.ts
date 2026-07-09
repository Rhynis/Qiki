/**
 * Vietnamese formatting utilities.
 */

/** Format a number as Vietnamese currency. */
export function formatPrice(amount: number | string): string {
  const num = typeof amount === 'string' ? Number.parseFloat(amount) : amount
  if (Number.isNaN(num)) return '0₫'
  return new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
  }).format(num)
}

/** Format a number with Vietnamese thousands separators. */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('vi-VN').format(num)
}

/** Format product size with its display unit. */
export function formatProductSize(size: number | string, unit = 'kg'): string {
  const num = typeof size === 'string' ? Number.parseFloat(size) : size
  const formatted = Number.isNaN(num) ? String(size) : new Intl.NumberFormat('vi-VN').format(num)
  return `${formatted} ${unit}`
}

/** Format a date in Vietnamese format as dd-mm-yyyy (with time when requested). */
export function formatDate(date: Date | string, includeTime = true): string {
  const d = typeof date === 'string' ? new Date(date) : date
  const dateStr = new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
    .format(d)
    .replace(/\//g, '-')

  if (!includeTime) return dateStr

  const timeStr = new Intl.DateTimeFormat('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)

  return `${dateStr} ${timeStr}`
}

/** Format phone number for display with masked middle digits. */
export function formatPhoneMasked(phone: string): string {
  if (!phone) return ''
  const normalized = phone.startsWith('+84') ? '0' + phone.slice(3) : phone
  if (normalized.length < 10) return normalized
  return normalized.slice(0, 4) + '****' + normalized.slice(-3)
}

/**
 * Format a phone number for display: convert `+84…` to a local `0…` number and
 * group 10-digit VN mobiles as 4-3-3 (e.g. `0708 277 925`).
 *
 * Landlines (area-code prefixes like `028…`) and already-formatted numbers such
 * as `(028) 37269435` are returned unchanged — only mobiles get 4-3-3 grouping.
 */
export function formatPhone(phone: string): string {
  if (!phone) return ''
  const local = phone.startsWith('+84') ? '0' + phone.slice(3) : phone
  if (/^0[35789]\d{8}$/.test(local)) {
    return `${local.slice(0, 4)} ${local.slice(4, 7)} ${local.slice(7)}`
  }
  return local
}
