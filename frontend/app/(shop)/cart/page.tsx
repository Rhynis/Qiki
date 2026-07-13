'use client'

import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { ShoppingBag } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CartReviewStep } from '@/components/shop/checkout/cart-review-step'
import { OrderSummarySidebar } from '@/components/shop/checkout/order-summary-sidebar'
import { PageHeader } from '@/components/shared/page-header'

export default function CartPage() {
  const t = useTranslations('cart')
  const router = useRouter()
  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <PageHeader title={t('title')} description={t('description')} />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Client-side navigation so the persisted cart store survives back/forward. */}
        <CartReviewStep onNext={() => router.push('/checkout')} />
        <OrderSummarySidebar />
      </div>
      <Button asChild variant="outline">
        <Link href="/products">
          <ShoppingBag className="mr-2 h-4 w-4" />
          {t('continueShopping')}
        </Link>
      </Button>
    </section>
  )
}
