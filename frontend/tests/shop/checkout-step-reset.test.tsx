import { beforeEach, describe, expect, it, vi } from 'vitest'
import CheckoutPage from '@/app/(shop)/checkout/page'
import { useCheckoutStore } from '@/lib/stores/checkout-store'
import { renderWithIntl } from '../i18n-render'

// The checkout steps fetch cart/order data; stub them so the page mounts with
// just its wizard shell. The behavior under test lives in the page's unmount
// cleanup, not in the step components.
vi.mock('@/components/shop/checkout/cart-review-step', () => ({
  CartReviewStep: () => <div data-testid="step-cart-review" />,
}))
vi.mock('@/components/shop/checkout/customer-delivery-step', () => ({
  CustomerDeliveryStep: () => <div data-testid="step-customer-delivery" />,
}))
vi.mock('@/components/shop/checkout/payment-step', () => ({
  PaymentStep: () => <div data-testid="step-payment" />,
}))
vi.mock('@/components/shop/checkout/confirm-step', () => ({
  ConfirmStep: () => <div data-testid="step-confirm" />,
}))
vi.mock('@/components/shop/checkout/checkout-stepper', () => ({
  CheckoutStepper: () => <div data-testid="stepper" />,
}))
vi.mock('@/components/shop/checkout/order-summary-sidebar', () => ({
  OrderSummarySidebar: () => <div data-testid="summary" />,
}))
vi.mock('@/components/shared/page-header', () => ({
  PageHeader: () => <div data-testid="page-header" />,
}))

describe('checkout wizard step reset', () => {
  beforeEach(() => {
    useCheckoutStore.getState().resetCheckout()
  })

  it('resets the step to 1 when leaving checkout and re-enters at the start', () => {
    // The customer is mid-flow on step 3.
    useCheckoutStore.setState({ step: 3 })

    const visit = renderWithIntl(<CheckoutPage />)
    // Navigating between steps within the same visit must not reset it.
    expect(useCheckoutStore.getState().step).toBe(3)

    // Leaving checkout (unmount) resets the wizard to the beginning.
    visit.unmount()
    expect(useCheckoutStore.getState().step).toBe(1)

    // Re-entering starts fresh at step 1.
    renderWithIntl(<CheckoutPage />)
    expect(useCheckoutStore.getState().step).toBe(1)
  })

  it('keeps form field values when the step resets', () => {
    useCheckoutStore.getState().updateForm({ customer_name: 'Khách Hàng Test' })
    useCheckoutStore.setState({ step: 2 })

    renderWithIntl(<CheckoutPage />).unmount()

    expect(useCheckoutStore.getState().step).toBe(1)
    expect(useCheckoutStore.getState().form.customer_name).toBe('Khách Hàng Test')
  })
})
