import { describe, expect, it } from 'vitest'
import enMessages from '@/messages/en.json'
import viMessages from '@/messages/vi.json'

type Messages = Record<string, unknown>

/** Collect every leaf key path (e.g. "header.cart") from a nested catalog. */
function keyPaths(messages: Messages, prefix = ''): string[] {
  return Object.entries(messages).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
      return keyPaths(value as Messages, path)
    }
    return [path]
  })
}

describe('i18n catalog parity', () => {
  const viKeys = keyPaths(viMessages as Messages).sort()
  const enKeys = keyPaths(enMessages as Messages).sort()

  it('vi.json and en.json have identical key sets', () => {
    const missingInEn = viKeys.filter((key) => !enKeys.includes(key))
    const missingInVi = enKeys.filter((key) => !viKeys.includes(key))
    expect(missingInEn, `keys missing from en.json: ${missingInEn.join(', ')}`).toEqual([])
    expect(missingInVi, `keys missing from vi.json: ${missingInVi.join(', ')}`).toEqual([])
  })

  it('no message value is an empty string in either locale', () => {
    for (const [locale, messages] of [
      ['vi', viMessages],
      ['en', enMessages],
    ] as const) {
      const empties = keyPaths(messages as Messages).filter((path) => {
        const value = path
          .split('.')
          .reduce<unknown>((acc, key) => (acc as Messages)?.[key], messages)
        return value === ''
      })
      expect(empties, `empty ${locale} values: ${empties.join(', ')}`).toEqual([])
    }
  })
})
