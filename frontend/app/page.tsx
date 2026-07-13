import Link from 'next/link'
import {
  Bot,
  CheckCircle2,
  Clock,
  Headphones,
  MapPin,
  Phone,
  ShieldCheck,
  ShoppingBag,
  Truck,
} from 'lucide-react'
import { useTranslations } from 'next-intl'
import { ChatOpenButton } from '@/components/shared/chat-open-button'
import { DeliveryAreaPopover } from '@/components/shared/delivery-area-popover'
import { StoreStatusBadge } from '@/components/shared/store-status-badge'
import { Button } from '@/components/ui/button'
import { SHOP_INFO } from '@/lib/constants'
import { protectVi } from '@/lib/utils'

export default function HomePage() {
  const t = useTranslations('home')
  const tCommon = useTranslations('common')

  const trustItems = [
    {
      title: t('trustQikiTitle'),
      description: t('trustQikiDescription'),
      icon: Bot,
    },
    {
      title: t('trustDeliveryTitle'),
      description: [
        `${SHOP_INFO.hours.weekdaysLabel}: ${SHOP_INFO.hours.weekdaysTime}`,
        `${SHOP_INFO.hours.weekendsLabel}: ${SHOP_INFO.hours.weekendsTime}`,
      ],
      icon: Clock,
    },
    {
      title: t('trustSafeTitle'),
      description: t('trustSafeDescription'),
      icon: ShieldCheck,
    },
    {
      title: t('trustAreaTitle'),
      description: t('trustAreaDescription', { area: SHOP_INFO.deliveryAreaLabel }),
      icon: MapPin,
    },
  ]

  const orderSteps = [
    {
      title: t('step1Title'),
      description: t('step1Description'),
      icon: ShoppingBag,
    },
    {
      title: t('step2Title'),
      description: t('step2Description'),
      icon: Headphones,
    },
    {
      title: t('step3Title'),
      description: t('step3Description'),
      icon: Truck,
    },
  ]

  const heroDetails: Array<{ label: string; value: string }> = [
    { label: t('heroDetailHotline'), value: SHOP_INFO.hotline.label },
    { label: t('heroDetailHours'), value: SHOP_INFO.hours.summary },
    {
      label: t('heroDetailPayment'),
      value: t('heroPaymentValue'),
    },
  ]

  return (
    <div className="bg-slate-50">
      <section className="bg-slate-950 text-white">
        <div className="mx-auto max-w-6xl px-4 py-12 md:py-16">
          <div className="grid gap-10 md:grid-cols-[1.08fr_0.92fr] md:items-center">
            <div className="space-y-7">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-sm text-slate-200">
                <CheckCircle2 className="h-4 w-4 text-primary" />
                {t('badge', { area: protectVi(SHOP_INFO.deliveryAreaLabel) })}
              </div>
              <div className="space-y-4">
                <h1 className="max-w-3xl text-4xl font-semibold text-white md:text-5xl">
                  {protectVi(t('heroTitle'))}
                </h1>
                <p className="max-w-2xl text-lg text-slate-300">
                  {protectVi(t('heroSubtitle'))}
                </p>
              </div>
              <div className="flex w-full max-w-md flex-col gap-3 sm:max-w-none sm:flex-row sm:flex-wrap sm:items-start">
                <div className="flex w-full flex-col gap-3 sm:w-auto">
                  <ChatOpenButton className="w-full bg-primary text-primary-foreground hover:bg-primary/90" />
                  <Button
                    asChild
                    className="w-full border-white/40 bg-white/5 text-white hover:bg-white/10 hover:text-white"
                    size="lg"
                    variant="outline"
                  >
                    <Link href="/products">{tCommon('viewProducts')}</Link>
                  </Button>
                </div>
                <Button
                  asChild
                  className="w-full border-transparent bg-white text-slate-950 hover:bg-slate-100 sm:w-auto"
                  size="lg"
                  variant="outline"
                >
                  <a href={SHOP_INFO.hotline.href}>
                    <Phone className="h-4 w-4" />
                    {tCommon('orderByPhone', { phone: SHOP_INFO.hotline.label })}
                  </a>
                </Button>
              </div>
            </div>

            <div className="rounded-lg border border-white/10 bg-white/[0.06] p-5 shadow-2xl shadow-slate-950/40">
              <div className="rounded-md border border-white/10 bg-slate-900 p-4">
                <div className="border-b border-white/10 pb-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm text-slate-400">{t('deliveryArea')}</p>
                    <StoreStatusBadge className="shrink-0 px-3 py-1 text-sm" variant="dark" />
                  </div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <p className="text-xl font-semibold leading-tight text-white">
                      {protectVi(t('deliveryAreaValue'))}
                    </p>
                    <DeliveryAreaPopover />
                  </div>
                </div>
                <div className="mt-5 grid gap-3">
                  {heroDetails.map(({ label, value }) => (
                    <div
                      className="flex items-start justify-between gap-4 rounded-md bg-white/[0.06] px-4 py-3"
                      key={label}
                    >
                      <span className="shrink-0 text-sm text-slate-400">{label}</span>
                      <span className="text-right text-sm font-semibold text-white">
                        {protectVi(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {trustItems.map((item) => (
            <div className="rounded-lg border bg-white p-5 shadow-sm" key={item.title}>
              <item.icon className="h-6 w-6 text-primary" />
              <h2 className="mt-4 text-balance text-lg font-semibold text-slate-950">
                {item.title}
              </h2>
              {Array.isArray(item.description) ? (
                <div className="mt-2 space-y-1 text-sm text-slate-600">
                  {item.description.map((line) => (
                    <p key={line}>{protectVi(line)}</p>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-600">{protectVi(item.description)}</p>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="border-y bg-white">
        <div className="mx-auto max-w-6xl px-4 py-12">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div>
              <h2 className="text-balance text-3xl font-semibold text-slate-950">
                {t('howToOrder')}
              </h2>
              <p className="mt-2 max-w-2xl text-slate-600">{protectVi(t('howToOrderSubtitle'))}</p>
            </div>
            <Button asChild variant="outline">
              <a href={SHOP_INFO.zalo.href} rel="noreferrer" target="_blank">
                {t('messageZalo')}
              </a>
            </Button>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {orderSteps.map((step, index) => (
              <div
                className="flex h-full flex-col rounded-lg border border-slate-200 bg-slate-50 p-5"
                key={step.title}
              >
                <div className="flex items-center justify-between">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                    {index + 1}
                  </span>
                  <step.icon className="h-5 w-5 text-slate-400" />
                </div>
                <h3 className="mt-4 text-balance text-lg font-semibold text-slate-950">
                  {protectVi(step.title)}
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {protectVi(step.description)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="rounded-lg border bg-slate-950 p-6 text-white md:flex md:items-center md:justify-between md:gap-8">
          <div>
            <p className="text-sm font-medium text-primary">{t('ctaLabel')}</p>
            <h2 className="mt-2 text-balance text-2xl font-semibold">{t('ctaTitle')}</h2>
            <p className="mt-2 max-w-2xl text-sm text-slate-300">{protectVi(t('ctaDescription'))}</p>
          </div>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row md:mt-0">
            <Button asChild className="bg-primary text-primary-foreground hover:bg-primary/90">
              <a href={SHOP_INFO.hotline.href}>
                {tCommon('callHotline', { phone: SHOP_INFO.hotline.label })}
              </a>
            </Button>
            <Button
              asChild
              className="border-white/40 bg-white/5 text-white hover:bg-white/10 hover:text-white"
              variant="outline"
            >
              <Link href="/track">{t('ctaTrackOrder')}</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}
