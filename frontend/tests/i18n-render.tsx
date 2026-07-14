import { render, type RenderOptions } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import type { ReactElement, ReactNode } from 'react'
import enMessages from '@/messages/en.json'
import viMessages from '@/messages/vi.json'

const messagesByLocale = {
  vi: viMessages,
  en: enMessages,
} as const

type Locale = keyof typeof messagesByLocale

/**
 * Render a component wrapped in NextIntlClientProvider so `useTranslations`
 * resolves against the real catalogs. Defaults to Vietnamese (the app default)
 * so existing assertions keep passing; pass `locale: 'en'` to check English.
 */
export function renderWithIntl(
  ui: ReactElement,
  { locale = 'vi', ...options }: RenderOptions & { locale?: Locale } = {}
) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <NextIntlClientProvider locale={locale} messages={messagesByLocale[locale]}>
        {children}
      </NextIntlClientProvider>
    )
  }

  return render(ui, { wrapper: Wrapper, ...options })
}
