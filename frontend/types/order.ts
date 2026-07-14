export type OrderStatus = 'pending' | 'confirmed' | 'shipping' | 'delivered' | 'cancelled'
export type PaymentMethod = 'cod' | 'bank_transfer'
export type PaymentStatus = 'pending' | 'paid' | 'refunded'
export type OrderSource = 'website' | 'chatbot'

export interface OrderItemCreate {
  product_id: string
  quantity: number
  is_exchange: boolean
}

export interface VatInfo {
  company_name: string
  tax_code: string
  address: string
}

export interface CheckoutRequest {
  items: OrderItemCreate[]
  customer_name: string
  customer_phone: string
  customer_email?: string | null
  delivery_address: string
  delivery_ward?: string | null
  delivery_district?: string | null
  delivery_city: string
  delivery_notes?: string | null
  different_recipient_name?: string | null
  different_recipient_phone?: string | null
  payment_method: PaymentMethod
  vat_invoice_requested: boolean
  vat_info?: VatInfo | null
  customer_notes?: string | null
  source: OrderSource
  referral_conversation_id?: string | null
  coupon_code?: string | null
}

export interface OrderItem {
  id: string
  order_id: string
  product_id: string | null
  product_name: string
  product_brand: string | null
  product_size_kg: string | null
  quantity: number
  unit_price: string
  subtotal: string
  is_exchange: boolean
  created_at: string
}

export type DeliveryStatus = 'pending' | 'shipping' | 'delivered' | 'cancelled'

export interface DeliveryItem {
  id: string
  delivery_id: string
  order_item_id: string
  quantity: number
  created_at: string
}

export interface Delivery {
  id: string
  order_id: string
  code: string
  status: DeliveryStatus
  scheduled_at: string | null
  delivered_at: string | null
  notes: string | null
  items: DeliveryItem[]
  created_at: string
}

export interface DeliveryItemCreate {
  order_item_id: string
  quantity: number
}

export interface DeliveryCreate {
  items: DeliveryItemCreate[]
  scheduled_at?: string | null
  notes?: string | null
}

export interface DeliveryStatusUpdate {
  status: DeliveryStatus
  notes?: string | null
}

export interface ReorderItem {
  product_id: string
  sku: string
  name: string
  brand: string
  size_kg: string
  category: string
  unit: string
  price: string
  quantity: number
  image_url: string | null
  stock_quantity: number
}

export interface SkippedReorderItem {
  product_id: string | null
  product_name: string
  reason: 'inactive' | 'out_of_stock' | 'not_found'
}

export interface ReorderResponse {
  items: ReorderItem[]
  skipped: SkippedReorderItem[]
}

export interface Order {
  id: string
  order_number: string
  user_id: string | null
  customer_name: string
  customer_phone: string
  customer_email: string | null
  delivery_address: string
  delivery_ward: string | null
  delivery_district: string | null
  delivery_city: string
  delivery_notes: string | null
  different_recipient_name: string | null
  different_recipient_phone: string | null
  subtotal: string
  shipping_fee: string
  discount_amount: string
  coupon_code: string | null
  total_amount: string
  vat_invoice_requested: boolean
  vat_info: VatInfo | null
  einvoice: InvoiceResult | null
  payment_method: PaymentMethod
  payment_status: PaymentStatus
  status: OrderStatus
  source: OrderSource
  referral_conversation_id: string | null
  customer_notes: string | null
  internal_notes: string | null
  cancelled_at: string | null
  cancelled_reason: string | null
  delivered_at: string | null
  created_at: string
  updated_at: string
  items: OrderItem[]
  deliveries: Delivery[]
}

export interface InvoiceResult {
  provider: string
  status: string
  invoice_no: string | null
  pdf_url: string | null
  payload: Record<string, unknown> | null
  issued_at: string | null
}

export interface OrderListResponse {
  items: Order[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

export interface GuestOrderLookup {
  order_number: string
  phone: string
}

export interface OrderSearchParams {
  status?: OrderStatus
  source?: OrderSource
  search?: string
  skip?: number
  limit?: number
}

export interface OrderStatusUpdate {
  new_status: OrderStatus
  notes?: string | null
}

export interface OrderCancelRequest {
  reason?: string | null
  phone?: string | null
}
