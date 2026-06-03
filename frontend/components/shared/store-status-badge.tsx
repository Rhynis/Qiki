'use client'

import { useOpeningStatus } from '@/lib/hooks/use-opening-status'
import { cn } from '@/lib/utils'

type StoreStatusBadgeProps = {
  variant?: 'light' | 'dark'
  className?: string
}

const BADGE_STYLES = {
  light: {
    open: 'bg-emerald-50 text-emerald-700',
    closed: 'bg-slate-100 text-slate-600',
    openDot: 'bg-emerald-500',
    closedDot: 'bg-slate-400',
  },
  dark: {
    open: 'bg-emerald-500/15 text-emerald-300',
    closed: 'bg-white/10 text-slate-300',
    openDot: 'bg-emerald-400',
    closedDot: 'bg-slate-400',
  },
} as const

/**
 * Huy hiệu trạng thái cửa hàng (mở/ngoài giờ) dùng chung cho footer (light) và
 * hero card nền tối (dark). Đồng bộ với giờ mở cửa thật qua useOpeningStatus.
 */
export function StoreStatusBadge({ variant = 'light', className }: StoreStatusBadgeProps) {
  const { isOpen } = useOpeningStatus()
  const styles = BADGE_STYLES[variant]

  return (
    <span
      suppressHydrationWarning
      className={cn(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold',
        isOpen ? styles.open : styles.closed,
        className
      )}
    >
      <span
        aria-hidden
        className={cn('h-1.5 w-1.5 rounded-full', isOpen ? styles.openDot : styles.closedDot)}
      />
      {isOpen ? 'Đang mở cửa' : 'Ngoài giờ'}
    </span>
  )
}
