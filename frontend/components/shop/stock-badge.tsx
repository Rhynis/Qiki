import { useTranslations } from 'next-intl'
import { Badge } from '@/components/ui/badge'

type StockBadgeProps = {
  stockQuantity: number
}

export function StockBadge({ stockQuantity }: StockBadgeProps) {
  const t = useTranslations('stock')

  if (stockQuantity === 0) {
    return (
      <Badge className="bg-safety text-safety-foreground hover:bg-safety/90">
        {t('outOfStock')}
      </Badge>
    )
  }

  if (stockQuantity <= 10) {
    return (
      <Badge className="bg-yellow-100 text-yellow-900 hover:bg-yellow-100">{t('lowStock')}</Badge>
    )
  }

  return <Badge>{t('inStock')}</Badge>
}
