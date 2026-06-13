import { describe, expect, it } from 'vitest'
import {
  formatPhoneInput,
  isVietnameseMobilePhone,
  normalizePhoneDigits,
} from '@/utils/phone-format'

describe('phone format helpers', () => {
  it('formats local mobile numbers as 3-4-3', () => {
    expect(formatPhoneInput('0903026306')).toBe('090 3026 306')
  })

  it('normalizes formatted values to digits only', () => {
    expect(normalizePhoneDigits('090 3026 306')).toBe('0903026306')
  })

  it('validates Vietnamese mobile prefixes', () => {
    expect(isVietnameseMobilePhone('090 3026 306')).toBe(true)
    expect(isVietnameseMobilePhone('020 3026 306')).toBe(false)
  })
})
