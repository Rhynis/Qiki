import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { ProductDetail } from '@/components/shop/product-detail'
import { formatProductSize } from '@/lib/utils/format'
import type { Product, ProductParent } from '@/types/product'

type ProductDetailPageProps = {
  params: Promise<{ id: string }>
}

function apiUrl(path: string): URL {
  const apiBaseUrl = process.env.BACKEND_URL ?? 'http://localhost:8000'
  return new URL(path, apiBaseUrl)
}

async function getProduct(productId: string): Promise<Product | null> {
  try {
    const response = await fetch(apiUrl(`/api/v1/products/${productId}`), { cache: 'no-store' })
    if (!response.ok) return null
    return (await response.json()) as Product
  } catch {
    return null
  }
}

/** Fetch the sibling variants so the detail page can offer a variant selector. */
async function getVariants(product: Product): Promise<Product[]> {
  if (!product.parent_id) return [product]
  try {
    const response = await fetch(apiUrl(`/api/v1/products/parents/${product.parent_id}`), {
      cache: 'no-store',
    })
    if (!response.ok) return [product]
    const parent = (await response.json()) as ProductParent
    const variants = parent.variants ?? []
    if (!variants.some((variant) => variant.id === product.id)) return [product, ...variants]
    return variants
  } catch {
    return [product]
  }
}

export async function generateMetadata({ params }: ProductDetailPageProps): Promise<Metadata> {
  const { id } = await params
  const product = await getProduct(id)

  if (!product) {
    return { title: 'Sản phẩm | Gas Quốc Cường' }
  }

  return {
    title: `${product.name} | Gas Quốc Cường`,
    description:
      product.description ?? `${product.brand} ${formatProductSize(product.size_kg, product.unit)}`,
  }
}

export default async function ProductDetailPage({ params }: ProductDetailPageProps) {
  const { id } = await params
  const product = await getProduct(id)

  if (!product) {
    notFound()
  }

  const variants = await getVariants(product)

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: product.name,
    description: product.description ?? product.name,
    image: product.image_url ? [product.image_url] : undefined,
    sku: product.sku,
    brand: {
      '@type': 'Brand',
      name: product.brand,
    },
    offers: {
      '@type': 'Offer',
      price: product.price,
      priceCurrency: 'VND',
      availability:
        product.stock_quantity > 0 ? 'https://schema.org/InStock' : 'https://schema.org/OutOfStock',
    },
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <ProductDetail product={product} variants={variants} />
    </>
  )
}
