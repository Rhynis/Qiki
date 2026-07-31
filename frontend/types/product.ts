export interface Product {
  id: string
  sku: string
  name: string
  brand: string
  size_kg: string
  category: ProductCategory
  unit: ProductUnit
  price: string
  stock_quantity: number
  description: string | null
  long_description: string | null
  image_url: string | null
  safety_info: string | null
  pricing_note: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  parent_id: string | null
  colour: string | null
  variant_label: string | null
}

export interface ProductParent {
  id: string
  name: string
  brand: string
  category: ProductCategory
  description: string | null
  image_url: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  variants: Product[]
}

export interface ProductParentSummary {
  id: string
  name: string
  brand: string
  category: ProductCategory
  description: string | null
  image_url: string | null
  min_price: string
  max_price: string
  variant_count: number
  in_stock: boolean
}

export interface ProductParentListResponse {
  items: ProductParentSummary[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

export interface ProductParentCreateInput {
  name: string
  brand: string
  category?: ProductCategory
  description?: string | null
  image_url?: string | null
}

export type ProductParentUpdateInput = Partial<ProductParentCreateInput> & {
  is_active?: boolean
}

export type ProductCategory = 'gas' | 'nuoc_uong'
export type ProductUnit = 'kg' | 'lít'

export interface BestSellerProduct extends Product {
  total_sold: number
}

export interface ProductListResponse {
  items: Product[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

export interface ProductSearchParams {
  search?: string
  brand?: string
  category?: ProductCategory
  min_price?: string
  max_price?: string
  size_kg?: string
  in_stock_only?: boolean
  sort_by?: 'created_at' | 'price' | 'name'
  sort_order?: 'asc' | 'desc'
  skip?: number
  limit?: number
}

export interface ProductCreateInput {
  sku: string
  name: string
  brand: string
  size_kg: string
  category?: ProductCategory
  unit?: ProductUnit
  price: string
  stock_quantity: number
  description?: string | null
  long_description?: string | null
  image_url?: string | null
  safety_info?: string | null
  pricing_note?: string | null
  parent_id?: string | null
  colour?: string | null
  variant_label?: string | null
}

export type ProductUpdateInput = Partial<ProductCreateInput> & {
  is_active?: boolean
}
