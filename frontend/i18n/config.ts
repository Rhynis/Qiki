/** Shared i18n locale configuration for the storefront. */

export const locales = ['vi', 'en'] as const

export type Locale = (typeof locales)[number]

/** Vietnamese stays the default so existing users see no change. */
export const defaultLocale: Locale = 'vi'

/** Cookie that persists the visitor's chosen storefront language. */
export const LOCALE_COOKIE = 'NEXT_LOCALE'

/** Narrow an arbitrary string to a supported locale, falling back to the default. */
export function resolveLocale(value: string | undefined | null): Locale {
  return locales.includes(value as Locale) ? (value as Locale) : defaultLocale
}
