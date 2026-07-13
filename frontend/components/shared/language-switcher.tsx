'use client'

import { Globe } from 'lucide-react'
import { useLocale, useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { useTransition } from 'react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { LOCALE_COOKIE, type Locale, locales } from '@/i18n/config'

const LOCALE_LABEL_KEY = {
  vi: 'vietnamese',
  en: 'english',
} as const

// One year, in seconds — long enough that a returning visitor keeps their choice.
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365

function persistLocale(next: Locale) {
  document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${COOKIE_MAX_AGE}; samesite=lax`
}

/** Header control that switches the storefront locale and persists it in a cookie. */
export function LanguageSwitcher() {
  const t = useTranslations('languageSwitcher')
  const locale = useLocale() as Locale
  const router = useRouter()
  const [isPending, startTransition] = useTransition()

  function selectLocale(next: Locale) {
    if (next === locale) return
    persistLocale(next)
    startTransition(() => {
      router.refresh()
    })
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label={t('label')}
          className="inline-flex h-9 items-center gap-1 rounded-md px-2 font-medium text-slate-700 transition hover:bg-slate-100 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          disabled={isPending}
          type="button"
        >
          <Globe aria-hidden="true" className="h-4 w-4" />
          <span className="uppercase">{locale}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {locales.map((option) => (
          <DropdownMenuItem
            className="cursor-pointer"
            key={option}
            onSelect={() => selectLocale(option)}
          >
            {t(LOCALE_LABEL_KEY[option])}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
