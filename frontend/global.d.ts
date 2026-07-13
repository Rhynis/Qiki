import type messages from './messages/vi.json'

/**
 * Augment next-intl so message keys are type-checked against the Vietnamese
 * catalog (the source of truth). Missing or misspelled keys become type errors
 * at build time instead of silent runtime fallbacks.
 */
declare module 'next-intl' {
  interface AppConfig {
    Messages: typeof messages
  }
}
