'use client'

import { useTranslations } from 'next-intl'
import { useEffect } from 'react'
import { CartReviewStep } from '@/components/shop/checkout/cart-review-step'
import { CheckoutStepper } from '@/components/shop/checkout/checkout-stepper'
import { ConfirmStep } from '@/components/shop/checkout/confirm-step'
import { CustomerDeliveryStep } from '@/components/shop/checkout/customer-delivery-step'
import { OrderSummarySidebar } from '@/components/shop/checkout/order-summary-sidebar'
import { PaymentStep } from '@/components/shop/checkout/payment-step'
import { PageHeader } from '@/components/shared/page-header'
import { useCheckoutStore } from '@/lib/stores/checkout-store'

export default function CheckoutPage() {
  const t = useTranslations('checkout')
  const step = useCheckoutStore((state) => state.step)
  const nextStep = useCheckoutStore((state) => state.nextStep)
  const setStep = useCheckoutStore((state) => state.setStep)

  // Reset the wizard to step 1 when leaving checkout so re-entering starts from
  // the beginning. This runs only on unmount (setStep is a stable store action),
  // never while navigating between steps within the same visit. Form values stay.
  useEffect(() => () => setStep(1), [setStep])

  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <PageHeader title={t('title')} description={t('description')} />
      <CheckoutStepper step={step} />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div>
          {step === 1 ? <CartReviewStep onNext={nextStep} /> : null}
          {step === 2 ? <CustomerDeliveryStep onNext={nextStep} /> : null}
          {step === 3 ? <PaymentStep onNext={nextStep} /> : null}
          {step === 4 ? <ConfirmStep /> : null}
        </div>
        <OrderSummarySidebar />
      </div>
    </section>
  )
}
