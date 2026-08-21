// Shared, deterministic API resolver for the E2E suite.
//
// Used by BOTH the mock HTTP server (for Next SSR fetches, which Playwright cannot
// intercept) and the Playwright `page.route` fixture (for client-side calls — the
// Next `/api/*` rewrite proxy 500s on POST bodies, so we never rely on it). One
// source of truth keeps SSR and client responses identical and the suite free of
// any live backend.
const now = '2026-06-15T00:00:00.000Z'

export const PRODUCTS = [
  // Gas: grouped by brand in the DB (parent-elf), but shown individually on the
  // listing — no "Nhiều lựa chọn" hint, no on-detail selector (#342).
  product('elf-12', 'ELF-12KG', 'Bình gas Elf 12kg (đỏ)', 'Elf Gas', '12', 'gas', 'kg', '710000', { parent_id: 'parent-elf', colour: 'đỏ', variant_label: '12 kg (đỏ)' }),
  product('sp-12', 'SP-12KG', 'Bình gas Saigon Petro 12kg', 'Saigon Petro', '12', 'gas', 'kg', '605000'),
  product('elf-6', 'ELF-6KG', 'Bình gas Elf 6kg', 'Elf Gas', '6', 'gas', 'kg', '350000', { parent_id: 'parent-elf', colour: null, variant_label: '6 kg' }),
  // Water: single product, no parent — its own card, no hint.
  product('water-20', 'WATER-20L', 'Nước Hoàn Hảo 20 lít', 'Hoàn Hảo', '20', 'nuoc_uong', 'lít', '55000'),
  // Water: grouped by parent (same size, different bottle form) — ONE combined
  // listing card with the "Nhiều lựa chọn" hint, and a detail-page selector.
  product('vihawa-normal', 'VIHAWA-20L', 'Nước Vihawa 20 lít', 'Vihawa', '20', 'nuoc_uong', 'lít', '55000', { parent_id: 'parent-vihawa', variant_label: 'Bình thường' }),
  product('vihawa-hotcold', 'VIHAWA-20L-NL', 'Nước Vihawa 20 lít (bình nóng lạnh)', 'Vihawa', '20', 'nuoc_uong', 'lít', '65000', { parent_id: 'parent-vihawa', variant_label: 'Bình nóng lạnh' }),
]

// Parent groupings. parent-elf exercises "gas is grouped in the DB but shown
// individually"; parent-vihawa exercises the water grouped-card + selector journeys.
const PARENTS = [
  {
    id: 'parent-elf',
    name: 'Bình gas Elf',
    brand: 'Elf Gas',
    category: 'gas',
    description: 'Sản phẩm mẫu cho kiểm thử.',
    image_url: null,
    is_active: true,
    created_at: now,
    updated_at: now,
  },
  {
    id: 'parent-vihawa',
    name: 'Nước Vihawa',
    brand: 'Vihawa',
    category: 'nuoc_uong',
    description: 'Sản phẩm mẫu cho kiểm thử.',
    image_url: null,
    is_active: true,
    created_at: now,
    updated_at: now,
  },
]

function product(id, sku, name, brand, size, category, unit, price, extra = {}) {
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
    parent_id: extra.parent_id ?? null,
    colour: extra.colour ?? null,
    variant_label: extra.variant_label ?? null,
  }
}

function parentDetail(parentId) {
  const parent = PARENTS.find((p) => p.id === parentId)
  if (!parent) return null
  const variants = PRODUCTS.filter((p) => p.parent_id === parentId).sort(
    (a, b) => Number(a.price) - Number(b.price)
  )
  return { ...parent, variants }
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
  if (method === 'GET' && path === '/api/v1/products/parents') {
    const category = query.get('category')
    const items = PARENTS.filter((p) => !category || p.category === category).map((parent) => {
      const variants = PRODUCTS.filter((p) => p.parent_id === parent.id)
      const prices = variants.map((v) => Number(v.price))
      return {
        id: parent.id,
        name: parent.name,
        brand: parent.brand,
        category: parent.category,
        description: parent.description,
        image_url: parent.image_url,
        min_price: (prices.length ? Math.min(...prices) : 0).toFixed(2),
        max_price: (prices.length ? Math.max(...prices) : 0).toFixed(2),
        variant_count: variants.length,
        in_stock: variants.some((v) => v.stock_quantity > 0),
      }
    })
    return json(200, { items, total: items.length, page: 1, limit: 20, has_more: false })
  }
  const parentMatch = /^\/api\/v1\/products\/parents\/([^/]+)$/.exec(path)
  if (method === 'GET' && parentMatch) {
    const detail = parentDetail(parentMatch[1])
    return detail ? json(200, detail) : json(404, { detail: 'Not found' })
  }
  if (method === 'GET' && path === '/api/v1/admin/products/low-stock') return json(200, [])
  if (method === 'GET' && path === '/api/v1/admin/insights') {
    return json(200, {
      period_start: '2026-05-16T00:00:00Z',
      period_end: '2026-06-15T00:00:00Z',
      summary: {
        total_conversations: 12,
        total_messages: 84,
        user_messages: 40,
        assistant_messages: 44,
        escalated_conversations: 2,
        flagged_messages: 3,
        low_confidence_messages: 5,
        negative_feedback_messages: 1,
        unanswered_messages: 4,
        escalation_rate: 0.17,
        flag_rate: 0.04,
      },
      top_intents: [{ intent: 'price_inquiry', count: 20 }],
      top_questions: [{ question: 'Giá bình gas 12kg bao nhiêu?', count: 8 }],
      trend: [{ date: '2026-06-15', conversations: 3, flagged: 1, escalated: 0 }],
      knowledge_gaps: [],
    })
  }
  const recMatch = /^\/api\/v1\/products\/([^/]+)\/recommendations$/.exec(path)
  if (method === 'GET' && recMatch) {
    const recs = PRODUCTS.filter((p) => p.id !== recMatch[1])
      .slice(0, 3)
      .map((p, i) => ({ ...p, score: 1 - i * 0.1, reason: 'Sản phẩm liên quan' }))
    return json(200, recs)
  }
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

  // --- Coupons -------------------------------------------------------------
  if (method === 'POST' && path === '/api/v1/coupons/validate') {
    return json(200, {
      code: String(body.code ?? 'SALE10').toUpperCase(),
      discount_type: 'percent',
      value: '10',
      discount_amount: '10000',
      min_order: '0',
    })
  }
  if (method === 'GET' && path === '/api/v1/admin/coupons') {
    return json(200, { items: [], total: 0, page: 1, limit: 20, has_more: false })
  }
  if (method === 'POST' && path === '/api/v1/admin/coupons') {
    return json(201, {
      id: 'coupon-1',
      code: String(body.code ?? 'SALE10').toUpperCase(),
      discount_type: body.discount_type ?? 'percent',
      value: String(body.value ?? '10'),
      min_order: String(body.min_order ?? '0'),
      max_discount: body.max_discount ?? null,
      usage_limit: body.usage_limit ?? null,
      used_count: 0,
      per_user_limit: body.per_user_limit ?? null,
      active: true,
      starts_at: null,
      ends_at: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
  }
  if (/^\/api\/v1\/admin\/coupons\/[^/]+$/.test(path) && method === 'PATCH') {
    return json(200, {
      id: 'coupon-1',
      code: 'SALE10',
      discount_type: 'percent',
      value: '10',
      min_order: '0',
      max_discount: null,
      usage_limit: null,
      used_count: 0,
      per_user_limit: null,
      active: body.active ?? true,
      starts_at: null,
      ends_at: null,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    })
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

  // --- Driver --------------------------------------------------------------
  if (method === 'GET' && path === '/api/v1/driver/deliveries') return json(200, [])
  if (/^\/api\/v1\/driver\/deliveries\/[^/]+\/status$/.test(path) && method === 'PATCH') {
    return json(200, {
      id: 'del-1',
      code: 'QC-000123-D1',
      status: body.status ?? 'delivered',
      customer_name: 'Nguyen Van Test',
      customer_phone: '0903026306',
      delivery_address: '15 đường số 5, khu phố 32',
      notes: null,
      scheduled_at: null,
      delivered_at: now,
      last_lat: body.lat ?? null,
      last_lng: body.lng ?? null,
      items: [{ product_name: 'Bình gas Elf 12kg (đỏ)', quantity: 1 }],
      created_at: now,
    })
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
