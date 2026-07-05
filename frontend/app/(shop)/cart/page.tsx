'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ShoppingBag } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CartReviewStep } from '@/components/shop/checkout/cart-review-step'
import { OrderSummarySidebar } from '@/components/shop/checkout/order-summary-sidebar'
import { PageHeader } from '@/components/shared/page-header'

export default function CartPage() {
  const router = useRouter()
  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <PageHeader title="Giỏ hàng" description="Kiểm tra sản phẩm trước khi thanh toán." />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Client-side navigation so the persisted cart store survives back/forward. */}
        <CartReviewStep onNext={() => router.push('/checkout')} />
        <OrderSummarySidebar />
      </div>
      <Button asChild variant="outline">
        <Link href="/products">
          <ShoppingBag className="mr-2 h-4 w-4" />
          Tiếp tục mua hàng
        </Link>
      </Button>
    </section>
  )
}
