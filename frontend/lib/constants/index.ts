/** Application-wide constants. */

export const APP_NAME = 'Gas Quốc Cường'
export const APP_DESCRIPTION = 'Mua gas LPG an toàn tại Bình Thạnh và Thủ Đức'
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const SHOP_INFO = {
  name: APP_NAME,
  hotline: {
    label: '090 3026306',
    value: '0903026306',
    href: 'tel:0903026306',
  },
  zalo: {
    label: 'Zalo 090 3026306',
    href: 'https://zalo.me/0903026306',
  },
  landline: {
    label: '(028) 37269435',
    href: 'tel:02837269435',
  },
  hours: {
    weekdays: 'T2-T6 06:30-20:00',
    weekends: 'T7-CN 07:30-20:00',
    summary: 'T2-T6 06:30-20:00 · T7-CN 07:30-20:00',
  },
  deliveryAreas: ['Bình Thạnh', 'Thủ Đức'],
  deliveryAreaLabel: 'Bình Thạnh, Thủ Đức',
  address: '15 đường số 5, Khu phố 1, Phường Hiệp Bình Chánh, Thủ Đức, TP.HCM',
} as const

export const ROUTES = {
  HOME: '/',
  PRODUCTS: '/products',
  CART: '/cart',
  CHECKOUT: '/checkout',
  ORDERS: '/orders',
  TRACK: '/track',
  LOGIN: '/login',
  REGISTER: '/register',
  FORGOT_PASSWORD: '/forgot-password',
  RESET_PASSWORD: '/reset-password',
  ADMIN: {
    DASHBOARD: '/admin',
    PRODUCTS: '/admin/products',
    ORDERS: '/admin/orders',
    CHAT: '/admin/chat',
    KNOWLEDGE_BASE: '/admin/knowledge-base',
  },
} as const

export const PAGINATION = {
  DEFAULT_PAGE: 1,
  DEFAULT_LIMIT: 20,
  MAX_LIMIT: 100,
} as const

export const INTENT_CATEGORIES = {
  PRODUCT_INQUIRY: 'product_inquiry',
  PLACE_ORDER: 'place_order',
  DELIVERY_STATUS: 'delivery_status',
  COMPLAINT: 'complaint',
  TECHNICAL_ISSUE: 'technical_issue',
  SAFETY_EMERGENCY: 'safety_emergency',
  PAYMENT_ISSUE: 'payment_issue',
  GENERAL_INFO: 'general_info',
} as const

export const ORDER_STATUS = {
  PENDING: 'pending',
  CONFIRMED: 'confirmed',
  SHIPPING: 'shipping',
  DELIVERED: 'delivered',
  CANCELLED: 'cancelled',
} as const

export const ORDER_STATUS_LABELS_VI: Record<string, string> = {
  pending: 'Chờ xác nhận',
  confirmed: 'Đã xác nhận',
  shipping: 'Đang giao',
  delivered: 'Đã giao',
  cancelled: 'Đã hủy',
}

export const PAYMENT_METHOD_LABELS_VI: Record<string, string> = {
  cod: 'Thanh toán khi nhận hàng (COD)',
  bank_transfer: 'Chuyển khoản ngân hàng',
}
