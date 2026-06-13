import { z } from 'zod'
import { DELIVERY_CITY, isAllowedDeliveryWard } from '@/utils/vietnamese-address'

const phoneRegex = /^(\+84|0)[1-9][0-9]{8,9}$/
const taxCodeRegex = /^[0-9]{10}(-[0-9]{3})?$/

export const cartItemSchema = z.object({
  product_id: z.string().uuid('Sản phẩm không hợp lệ'),
  quantity: z.coerce.number().int('Số lượng phải là số nguyên').min(1, 'Số lượng tối thiểu là 1'),
  is_exchange: z.boolean().default(false),
})

export const cartStepSchema = z.object({
  items: z.array(cartItemSchema).min(1, 'Giỏ hàng đang trống'),
})

export const customerDeliverySchema = z
  .object({
    customer_name: z.string().trim().min(2, 'Tên khách hàng quá ngắn'),
    customer_phone: z.string().trim().regex(phoneRegex, 'Số điện thoại Việt Nam không hợp lệ'),
    customer_email: z.string().trim().email('Email không hợp lệ').or(z.literal('')).optional(),
    delivery_address: z.string().trim().min(5, 'Địa chỉ giao hàng quá ngắn'),
    delivery_ward: z
      .string()
      .trim()
      .refine(isAllowedDeliveryWard, 'Chọn phường/xã trong khu vực giao hàng'),
    delivery_district: z.string().trim().optional(),
    delivery_city: z.literal(DELIVERY_CITY, {
      errorMap: () => ({ message: 'Chọn TP. Hồ Chí Minh' }),
    }),
    delivery_notes: z.string().trim().optional(),
    has_different_recipient: z.boolean(),
    different_recipient_name: z.string().trim().optional(),
    different_recipient_phone: z.string().trim().optional(),
  })
  .superRefine((value, ctx) => {
    if (!value.has_different_recipient) return
    if (!value.different_recipient_name || value.different_recipient_name.length < 2) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['different_recipient_name'],
        message: 'Tên người nhận quá ngắn',
      })
    }
    if (!value.different_recipient_phone || !phoneRegex.test(value.different_recipient_phone)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['different_recipient_phone'],
        message: 'Số điện thoại người nhận không hợp lệ',
      })
    }
  })

export const paymentSchema = z
  .object({
    payment_method: z.enum(['cod', 'bank_transfer'], {
      errorMap: () => ({ message: 'Chọn phương thức thanh toán' }),
    }),
    vat_invoice_requested: z.boolean(),
    vat_info: z.object({
      company_name: z.string().trim().optional(),
      tax_code: z.string().trim().optional(),
      address: z.string().trim().optional(),
    }),
    customer_notes: z.string().trim().optional(),
  })
  .superRefine((value, ctx) => {
    if (!value.vat_invoice_requested) return
    if (!value.vat_info.company_name || value.vat_info.company_name.length < 2) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['vat_info', 'company_name'],
        message: 'Tên công ty quá ngắn',
      })
    }
    if (!value.vat_info.tax_code || !taxCodeRegex.test(value.vat_info.tax_code)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['vat_info', 'tax_code'],
        message: 'Mã số thuế không hợp lệ',
      })
    }
    if (!value.vat_info.address || value.vat_info.address.length < 5) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['vat_info', 'address'],
        message: 'Địa chỉ xuất hóa đơn quá ngắn',
      })
    }
  })

export const guestLookupSchema = z.object({
  order_number: z.string().trim().min(8, 'Mã đơn hàng không hợp lệ'),
  phone: z.string().trim().regex(phoneRegex, 'Số điện thoại Việt Nam không hợp lệ'),
})

export type CustomerDeliveryValues = z.infer<typeof customerDeliverySchema>
export type PaymentValues = z.infer<typeof paymentSchema>
export type GuestLookupValues = z.infer<typeof guestLookupSchema>
