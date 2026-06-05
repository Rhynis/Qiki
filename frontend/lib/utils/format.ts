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

/** Format a date in Vietnamese format. */
export function formatDate(date: Date | string, includeTime = true): string {
  const d = typeof date === 'string' ? new Date(date) : date
  const dateStr = new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(d)

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

/** Format phone number for display without masking. */
export function formatPhone(phone: string): string {
  if (!phone) return ''
  if (phone.startsWith('+84')) return '0' + phone.slice(3)
  return phone
}
