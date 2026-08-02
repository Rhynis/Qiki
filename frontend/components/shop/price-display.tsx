import { cn } from '@/lib/utils'
import { formatPrice } from '@/lib/utils/format'
import { discountPercentValue, effectivePriceValue } from '@/lib/utils/pricing'

type PriceDisplayProps = {
  /** The regular list price (or line total when `salePrice` is a line total). */
  listPrice: number | string
  /** The sale price/amount when discounted; null/undefined shows a single price. */
  salePrice?: number | string | null
  className?: string
  /** Applied to the effective (charged) price so each surface keeps its own size. */
  priceClassName?: string
}

function toNum(value: number | string | null | undefined): number | null {
  if (value == null) return null
  const parsed = typeof value === 'string' ? Number.parseFloat(value) : value
  return Number.isNaN(parsed) ? null : parsed
}

/**
 * Shared price renderer used by the product card, product detail and order summary
 * so a sale renders identically everywhere: the effective price in primary colour,
 * the original struck through, and a `-X%` badge. Falls back to a single price.
 */
export function PriceDisplay({
  listPrice,
  salePrice,
  className,
  priceClassName,
}: PriceDisplayProps) {
  const list = toNum(listPrice) ?? 0
  const sale = toNum(salePrice ?? null)
  const percent = discountPercentValue(list, sale)

  if (percent == null) {
    return <span className={priceClassName}>{formatPrice(list)}</span>
  }

  return (
    <span className={cn('inline-flex flex-wrap items-baseline gap-x-2 gap-y-1', className)}>
      <span className={priceClassName}>{formatPrice(effectivePriceValue(list, sale))}</span>
      <span className="text-sm font-normal text-slate-400 line-through">{formatPrice(list)}</span>
      <span className="rounded bg-primary/10 px-1.5 py-0.5 text-xs font-semibold text-primary">
        -{percent}%
      </span>
    </span>
  )
}
