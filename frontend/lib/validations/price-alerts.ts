import { z } from 'zod'
import { emailInvalidMessage } from '@/lib/validations/auth'

export const priceAlertSubscribeSchema = z.object({
  email: z.string().email(emailInvalidMessage),
  consent: z.boolean().refine((value) => value, {
    message: 'Vui lòng đồng ý nhận email thông báo giá',
  }),
})

export type PriceAlertSubscribeValues = z.infer<typeof priceAlertSubscribeSchema>
