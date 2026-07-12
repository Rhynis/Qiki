// Shared, deterministic API resolver for the E2E suite.
//
// Used by BOTH the mock HTTP server (for Next SSR fetches, which Playwright cannot
// intercept) and the Playwright `page.route` fixture (for client-side calls — the
// Next `/api/*` rewrite proxy 500s on POST bodies, so we never rely on it). One
// source of truth keeps SSR and client responses identical and the suite free of
// any live backend.
const now = '2026-06-15T00:00:00.000Z'

export const PRODUCTS = [
  product('elf-12', 'ELF-12KG', 'Bình gas Elf 12kg (đỏ)', 'Elf Gas', '12', 'gas', 'kg', '710000'),
  product('sp-12', 'SP-12KG', 'Bình gas Saigon Petro 12kg', 'Saigon Petro', '12', 'gas', 'kg', '605000'),
  product('elf-6', 'ELF-6KG', 'Bình gas Elf 6kg', 'Elf Gas', '6', 'gas', 'kg', '350000'),
  product('water-20', 'WATER-20L', 'Nước Hoàn Hảo 20 lít', 'Hoàn Hảo', '20', 'nuoc_uong', 'lít', '55000'),
]

function product(id, sku, name, brand, size, category, unit, price) {
  return {
    id,
    sku,
    name,
    brand,
    size_kg: size,
    category,
    unit,
    price,
    stock_quantity: 50,
    description: 'Sản phẩm mẫu cho kiểm thử.',
    image_url: null,
    safety_info: null,
    pricing_note: category === 'nuoc_uong' ? 'Giá tại cửa hàng; giao +5.000đ.' : null,
    is_active: true,
    created_at: now,
    updated_at: now,
  }
}

function buildOrder(overrides = {}) {
  const base = PRODUCTS[0]
  const item = {
    id: `item-${base.id}`,
    order_id: 'ord-1',
    product_id: base.id,
    product_name: base.name,
    product_brand: base.brand,
    product_size_kg: base.size_kg,
    quantity: 1,
    unit_price: base.price,
    subtotal: base.price,
    is_exchange: false,
    created_at: now,
  }
  return {
    id: 'ord-1',
    order_number: 'QC-000123',
    user_id: null,
    customer_name: 'Nguyen Van Test',
    customer_phone: '0903026306',
    customer_email: null,
    delivery_address: '15 đường số 5, khu phố 32',
    delivery_ward: 'Bình Lợi Trung',
    delivery_district: 'Bình Thạnh',
    delivery_city: 'TP. Hồ Chí Minh',
    delivery_notes: null,
    different_recipient_name: null,
    different_recipient_phone: null,
    subtotal: item.subtotal,
    shipping_fee: '0',
    total_amount: item.subtotal,
    vat_invoice_requested: false,
    vat_info: null,
    einvoice: null,
    payment_method: 'cod',
    payment_status: 'pending',
    status: 'pending',
    source: 'website',
    referral_conversation_id: null,
    customer_notes: null,
    internal_notes: null,
    cancelled_at: null,
    cancelled_reason: null,
    delivered_at: null,
    created_at: now,
    updated_at: now,
    items: [item],
    deliveries: [],
    ...overrides,
  }
}

function userFromCookie(cookie) {
  // Mirrors the app middleware: base64-decode the (unsigned) JWT payload and
  // honour role + exp. The E2E seeds this cookie to drive logged-in journeys.
  const match = /gasbot_access_token=([^;]+)/.exec(cookie ?? '')
  if (!match) return null
  try {
    const segment = match[1].split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const payload = JSON.parse(Buffer.from(segment, 'base64').toString())
    if (typeof payload.exp !== 'number' || payload.exp * 1000 <= Date.now()) return null
    const role = payload.role === 'admin' ? 'admin' : 'customer'
    return {
      id: role === 'admin' ? 'admin-1' : 'user-1',
      email: payload.email ?? `${role}@example.com`,
      email_verified: true,
      full_name: role === 'admin' ? 'Quản trị viên' : 'Khách Hàng Test',
      phone: '0903026306',
      role,
      is_active: true,
      created_at: now,
    }
  } catch {
    return null
  }
}

const json = (status, body) => ({ status, body })

/**
 * Resolve one API request to `{ status, body }`.
 * @param {{ method: string, path: string, query: URLSearchParams, body?: any, cookie?: string }} req
 */
export function resolveApi({ method, path, query, body = {}, cookie }) {
  // --- Products ------------------------------------------------------------
  if (method === 'GET' && path === '/api/v1/products') {
    let items = PRODUCTS.slice()
    const category = query.get('category')
    if (category) items = items.filter((p) => p.category === category)
    const brand = query.get('brand')
    if (brand) items = items.filter((p) => p.brand === brand)
    const sortBy = query.get('sort_by')
    const dir = query.get('sort_order') === 'asc' ? 1 : -1
    if (sortBy === 'price') items.sort((a, b) => (Number(a.price) - Number(b.price)) * dir)
    else if (sortBy === 'name') items.sort((a, b) => a.name.localeCompare(b.name) * dir)
    return json(200, { items, total: items.length, page: 1, limit: 20, has_more: false })
  }
  if (method === 'GET' && path === '/api/v1/products/brands') {
    return json(200, [...new Set(PRODUCTS.map((p) => p.brand))])
  }
  if (method === 'GET' && path === '/api/v1/admin/products/low-stock') return json(200, [])
  const productMatch = /^\/api\/v1\/products\/([^/]+)$/.exec(path)
  if (method === 'GET' && productMatch) {
    const found = PRODUCTS.find((p) => p.id === productMatch[1])
    return found ? json(200, found) : json(404, { detail: 'Not found' })
  }
  if (method === 'POST' && path === '/api/v1/products') {
    return json(201, product('new-1', body.sku ?? 'NEW', body.name ?? 'Mới', body.brand ?? 'Elf Gas', '12', body.category ?? 'gas', 'kg', String(body.price ?? '100000')))
  }

  // --- Wishlist ------------------------------------------------------------
  if (method === 'GET' && path === '/api/v1/wishlist') return json(200, [])
  if (/^\/api\/v1\/wishlist\/[^/]+$/.test(path) && (method === 'POST' || method === 'DELETE')) {
    return json(204, undefined)
  }

  // --- Orders --------------------------------------------------------------
  if (method === 'POST' && path === '/api/v1/orders/checkout') {
    return json(201, buildOrder({
      customer_name: body.customer_name,
      customer_phone: body.customer_phone,
      delivery_ward: body.delivery_ward,
      payment_method: body.payment_method ?? 'cod',
    }))
  }
  if (method === 'POST' && path === '/api/v1/orders/lookup') {
    return json(200, buildOrder({ order_number: body.order_number ?? 'QC-000123' }))
  }
  if (method === 'GET' && path === '/api/v1/orders/best-sellers') {
    return json(
      200,
      PRODUCTS.slice(0, 4).map((p, index) => ({ ...p, total_sold: 40 - index * 5 }))
    )
  }
  const reorderMatch = /^\/api\/v1\/orders\/([^/]+)\/reorder$/.exec(path)
  if (method === 'POST' && reorderMatch) {
    return json(200, { items: [], skipped: [] })
  }
  if (method === 'GET' && path === '/api/v1/orders/me') {
    return json(200, { items: [buildOrder()], total: 1, page: 1, limit: 20, has_more: false })
  }
  const orderMatch = /^\/api\/v1\/orders\/([^/]+)$/.exec(path)
  if (method === 'GET' && orderMatch && orderMatch[1] !== 'me') {
    return json(200, buildOrder({ id: orderMatch[1] }))
  }

  // --- Auth ----------------------------------------------------------------
  if (method === 'GET' && path === '/api/v1/auth/me') {
    const user = userFromCookie(cookie)
    return user ? json(200, user) : json(401, { detail: 'Not authenticated' })
  }
  if (method === 'POST' && path === '/api/v1/auth/login') {
    return json(200, {
      token_type: 'bearer',
      user: { id: 'user-1', email: body.email ?? 'customer@example.com', email_verified: true, full_name: 'Khách Hàng Test', phone: '0903026306', role: 'customer', is_active: true, created_at: now },
    })
  }
  if (method === 'POST' && path === '/api/v1/auth/register') {
    return json(201, { id: 'user-1', email: body.email ?? 'new@example.com', full_name: body.full_name ?? 'Khách Hàng Mới', phone: body.phone ?? '0903026306', role: 'customer', is_active: true, created_at: now })
  }
  if (method === 'POST' && path === '/api/v1/auth/refresh') {
    const user = userFromCookie(cookie)
    return user ? json(200, { token_type: 'bearer', user }) : json(401, { detail: 'Not authenticated' })
  }
  if (method === 'POST' && (path === '/api/v1/auth/password/reset-request' || path === '/api/v1/auth/password/reset' || path === '/api/v1/auth/logout' || path === '/api/v1/auth/password/change')) {
    return json(200, { message: 'ok' })
  }

  // --- Admin ---------------------------------------------------------------
  if (method === 'GET' && path === '/api/v1/admin/dashboard') {
    return json(200, {
      orders_today: 3,
      orders_pending: 1,
      revenue_today: 2130000,
      low_stock_count: 0,
      users_total: 5,
      users_new_today: 1,
    })
  }
  if (method === 'GET' && path === '/api/v1/admin/orders') {
    return json(200, { items: [buildOrder()], total: 1, page: 1, limit: 50, has_more: false })
  }
  if (method === 'GET' && path === '/api/v1/admin/orders/statistics') {
    return json(200, { pending: 1, confirmed: 0, shipping: 0, delivered: 0, cancelled: 0, total: 1 })
  }
  if (method === 'GET' && path === '/api/v1/admin/users') {
    return json(200, { items: [{ id: 'user-1', email: 'customer@example.com', full_name: 'Khách Hàng Test', phone: '0903026306', role: 'customer', is_active: true, created_at: now }], total: 1, page: 1, limit: 20, has_more: false })
  }
  if (method === 'GET' && path === '/api/v1/staff/conversations/assigned') {
    return json(200, {
      items: [{
        id: 'conv-1',
        session_id: 'sess-abc',
        status: 'escalated',
        messages: [
          { id: 'm1', conversation_id: 'conv-1', role: 'user', content: 'Giá gas 12kg bao nhiêu? sđt 0903026306', intent: 'product_inquiry', flagged_for_review: false, is_emergency: false, created_at: now },
          { id: 'm2', conversation_id: 'conv-1', role: 'assistant', content: 'Dạ bình gas 12kg giá 710.000đ ạ.', flagged_for_review: false, is_emergency: false, created_at: now },
        ],
        created_at: now,
        updated_at: now,
      }],
      total: 1,
      skip: 0,
      limit: 100,
    })
  }
  if (method === 'GET' && /^\/api\/v1\/admin\/knowledge-base/.test(path)) {
    return json(200, { items: [], total: 0, page: 1, limit: 20, has_more: false })
  }

  // --- Conversations (chat widget) -----------------------------------------
  if (method === 'POST' && path === '/api/v1/conversations/start') {
    return json(201, { id: 'conv-widget', session_id: 'sess-widget', status: 'active', messages: [], created_at: now, updated_at: now })
  }
  if (method === 'GET' && path === '/api/v1/conversations/active') return json(200, null)
  const convMessages = /^\/api\/v1\/conversations\/([^/]+)\/messages$/.exec(path)
  if (convMessages) {
    const conversationId = convMessages[1]
    if (method === 'GET') return json(200, { items: [], total: 0, skip: 0, limit: 50 })
    return json(200, {
      user_message: { id: `msg-u-${Date.now()}`, conversation_id: conversationId, role: 'user', content: body.content ?? '', flagged_for_review: false, is_emergency: false, created_at: now },
      assistant_message: { id: `msg-a-${Date.now()}`, conversation_id: conversationId, role: 'assistant', content: 'Dạ Qiki đã nhận tin nhắn của bạn, cửa hàng sẽ hỗ trợ ngay ạ.', flagged_for_review: false, is_emergency: false, created_at: now },
      conversation: { id: conversationId, session_id: 'sess-widget', status: 'active', messages: [], created_at: now, updated_at: now },
      products: [],
    })
  }
  const convDetail = /^\/api\/v1\/conversations\/([^/]+)$/.exec(path)
  if (method === 'GET' && convDetail) {
    return json(200, { id: convDetail[1], session_id: 'sess-widget', status: 'active', messages: [], created_at: now, updated_at: now })
  }

  // Default: empty 200 so an unmocked call never crashes a page.
  return json(200, {})
}
