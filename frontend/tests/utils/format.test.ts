import { describe, expect, it } from 'vitest'
import {
  formatDate,
  formatNumber,
  formatPhone,
  formatPhoneMasked,
  formatPrice,
} from '@/lib/utils/format'

describe('format utilities', () => {
  it('formats prices as VND', () => {
    expect(formatPrice(450000)).toContain('450.000')
  })

  it('handles invalid price input', () => {
    expect(formatPrice('not-a-number')).toBe('0₫')
  })

  it('formats numbers with Vietnamese separators', () => {
    expect(formatNumber(1234567)).toBe('1.234.567')
  })

  it('formats dates with and without time', () => {
    const date = new Date('2026-05-25T14:30:00+07:00')
    expect(formatDate(date, false)).toContain('25/05/2026')
    expect(formatDate(date, true)).toContain('25/05/2026')
  })

  it('formats phone numbers', () => {
    expect(formatPhone('+84901234567')).toBe('0901234567')
    expect(formatPhone('0901234567')).toBe('0901234567')
  })

  it('masks phone numbers', () => {
    expect(formatPhoneMasked('+84901234567')).toBe('0901****567')
  })
})
