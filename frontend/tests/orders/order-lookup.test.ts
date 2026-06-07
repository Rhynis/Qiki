import { describe, expect, it } from 'vitest'
import { sanitizeOrderNumberForLookup } from '@/lib/utils/order-lookup'

describe('order lookup utilities', () => {
  it('trims spaces and trailing punctuation from copied order numbers', () => {
    expect(sanitizeOrderNumberForLookup('  GB-20260607-F2A9. ')).toBe('GB-20260607-F2A9')
  })
})
