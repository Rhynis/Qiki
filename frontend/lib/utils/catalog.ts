import type { Product } from '@/types/product'

/**
 * Collapse water (`nuoc_uong`) siblings that share a `parent_id` into a single
 * representative — the cheapest variant — so the listing shows ONE card per
 * water product family (e.g. Vihawa Bình thường / Bình nóng lạnh) instead of
 * one card per SKU. Gas is left untouched: every active gas product keeps its
 * own card, since gas varies by size and grouping it hid non-default sizes
 * behind a selector on the detail page (#342).
 *
 * A water product whose parent has only one active variant on this page (e.g.
 * filtered out by search/price) is shown as a plain individual card — grouping
 * hint is only useful when there is actually more than one option to pick.
 */
export function groupWaterVariants(products: Product[]): Product[] {
  const waterGroups = new Map<string, Product[]>()
  for (const product of products) {
    if (product.category === 'nuoc_uong' && product.parent_id) {
      const siblings = waterGroups.get(product.parent_id) ?? []
      siblings.push(product)
      waterGroups.set(product.parent_id, siblings)
    }
  }

  const representativeIds = new Set<string>()
  const groupedOutIds = new Set<string>()
  for (const siblings of waterGroups.values()) {
    if (siblings.length <= 1) continue
    const cheapest = siblings.reduce((min, variant) =>
      Number(variant.price) < Number(min.price) ? variant : min
    )
    representativeIds.add(cheapest.id)
    for (const variant of siblings) groupedOutIds.add(variant.id)
  }

  return products.filter(
    (product) => !groupedOutIds.has(product.id) || representativeIds.has(product.id)
  )
}
