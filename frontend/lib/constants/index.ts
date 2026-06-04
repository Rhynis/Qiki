/** Application-wide constants. */

export const APP_NAME = 'Gas Quốc Cường'
export const APP_DESCRIPTION = 'Mua gas LPG an toàn tại Bình Thạnh và Thủ Đức'
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// Chuỗi địa chỉ/khu vực để khoảng trắng thường; khi render bọc qua protectVi()
// (lib/utils) để cụm tên riêng (Bình Thạnh, Thủ Đức...) không bị tách dòng.
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
    weekdaysLabel: 'Thứ 2 - Thứ 6',
    weekdaysTime: '06:30 - 20:00',
    weekendsLabel: 'Thứ 7 - Chủ nhật',
    weekendsTime: '07:30 - 20:00',
    summary: 'T2-T6 06:30-20:00 · T7-CN 07:30-20:00',
  },
  deliveryAreas: ['Bình Thạnh', 'Thủ Đức'],
  deliveryAreaLabel: 'Bình Thạnh, Thủ Đức',
  deliveryWards: [
    'Hiệp Bình',
    'Thủ Đức',
    'Tam Bình',
    'Bình Quới',
    'Bình Thạnh',
    'Thạnh Mỹ Tây',
    'Gia Định',
    'Bình Lợi Trung',
  ],
  address: '15 đường số 5, Khu phố 36, Phường Hiệp Bình, Thành phố Hồ Chí Minh',
  addressOld: '15 đường số 5, Khu phố 1, Phường Hiệp Bình Chánh, Thủ Đức, Thành phố Hồ Chí Minh',
  map: {
    embedSrc:
      'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3918.7643965987318!2d106.71049211181263!3d10.829333789278088!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x31752887b578d34b%3A0x5dcf1fcbd8f8eb28!2zQ-G7rWEgaMOgbmcgZ2FzIFF14buRYyBDxrDhu51uZw!5e0!3m2!1svi!2s!4v1780486193049!5m2!1svi!2s',
    link: 'https://maps.app.goo.gl/3kwGY46Pzpbp7v6t8',
  },
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
