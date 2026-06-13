'use client'

import { create } from 'zustand'
import type { Order, PaymentMethod, VatInfo } from '@/types/order'
import { DELIVERY_CITY } from '@/utils/vietnamese-address'

export type CheckoutStep = 1 | 2 | 3 | 4

export interface CheckoutFormState {
  customer_name: string
  customer_phone: string
  customer_email: string
  delivery_address: string
  delivery_ward: string
  delivery_district: string
  delivery_city: string
  delivery_notes: string
  has_different_recipient: boolean
  different_recipient_name: string
  different_recipient_phone: string
  payment_method: PaymentMethod
  vat_invoice_requested: boolean
  vat_info: VatInfo
  customer_notes: string
}

interface CheckoutState {
  step: CheckoutStep
  form: CheckoutFormState
  lastOrder: Order | null
  setStep: (step: CheckoutStep) => void
  nextStep: () => void
  previousStep: () => void
  updateForm: (data: Partial<CheckoutFormState>) => void
  setLastOrder: (order: Order | null) => void
  resetCheckout: () => void
}

const initialForm: CheckoutFormState = {
  customer_name: '',
  customer_phone: '',
  customer_email: '',
  delivery_address: '',
  delivery_ward: '',
  delivery_district: '',
  delivery_city: DELIVERY_CITY,
  delivery_notes: '',
  has_different_recipient: false,
  different_recipient_name: '',
  different_recipient_phone: '',
  payment_method: 'cod',
  vat_invoice_requested: false,
  vat_info: {
    company_name: '',
    tax_code: '',
    address: '',
  },
  customer_notes: '',
}

export const useCheckoutStore = create<CheckoutState>()((set) => ({
  step: 1,
  form: initialForm,
  lastOrder: null,
  setStep: (step) => set({ step }),
  nextStep: () => set((state) => ({ step: Math.min(state.step + 1, 4) as CheckoutStep })),
  previousStep: () => set((state) => ({ step: Math.max(state.step - 1, 1) as CheckoutStep })),
  updateForm: (data) =>
    set((state) => ({
      form: {
        ...state.form,
        ...data,
        vat_info: data.vat_info
          ? { ...state.form.vat_info, ...data.vat_info }
          : state.form.vat_info,
      },
    })),
  setLastOrder: (order) => set({ lastOrder: order }),
  resetCheckout: () => set((state) => ({ step: 1, form: initialForm, lastOrder: state.lastOrder })),
}))
