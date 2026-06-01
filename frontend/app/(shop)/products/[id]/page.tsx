import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { ProductDetail } from '@/components/shop/product-detail'
import type { Product } from '@/types/product'

type ProductDetailPageProps = {
  params: Promise<{ id: string }>
}

async function getProduct(productId: string): Promise<Product | null> {
  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
  const url = new URL(`/api/v1/products/${productId}`, apiBaseUrl)

  try {
    const response = await fetch(url, { cache: 'no-store' })
    if (!response.ok) return null
    return (await response.json()) as Product
  } catch {
    return null
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
    description: product.description ?? `${product.brand} ${product.size_kg}kg`,
  }
}

export default async function ProductDetailPage({ params }: ProductDetailPageProps) {
  const { id } = await params
  const product = await getProduct(id)

  if (!product) {
    notFound()
  }

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
      <ProductDetail product={product} />
    </>
  )
}
