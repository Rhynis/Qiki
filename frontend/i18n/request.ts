import { cookies } from 'next/headers'
import { getRequestConfig } from 'next-intl/server'
import { LOCALE_COOKIE, resolveLocale } from '@/i18n/config'

/**
 * next-intl request config. The storefront does not prefix routes with the
 * locale; instead the chosen language is read from a cookie so URLs stay stable
 * and Vietnamese remains the default for visitors who never switch.
 */
export default getRequestConfig(async () => {
  const cookieStore = await cookies()
  const locale = resolveLocale(cookieStore.get(LOCALE_COOKIE)?.value)
  const messages = (await import(`@/messages/${locale}.json`)).default

  return { locale, messages }
})
