const LOCAL_MOBILE_PREFIXES = new Set(['03', '05', '07', '08', '09'])

export function normalizePhoneDigits(value: string): string {
  const digits = value.replace(/\D/g, '')
  if (digits.startsWith('84') && digits.length >= 11) {
    return `0${digits.slice(2)}`.slice(0, 10)
  }
  return digits.slice(0, 10)
}

export function formatPhoneInput(value: string): string {
  const digits = normalizePhoneDigits(value)
  const groups = [digits.slice(0, 3), digits.slice(3, 7), digits.slice(7, 10)].filter(Boolean)
  return groups.join(' ')
}

export function isVietnameseMobilePhone(value: string): boolean {
  const digits = normalizePhoneDigits(value)
  return digits.length === 10 && LOCAL_MOBILE_PREFIXES.has(digits.slice(0, 2))
}
