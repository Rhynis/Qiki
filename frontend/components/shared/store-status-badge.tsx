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
    pending: 'bg-slate-100 text-slate-500',
    openDot: 'bg-emerald-500',
    closedDot: 'bg-slate-400',
    pendingDot: 'bg-slate-300',
  },
  dark: {
    open: 'bg-emerald-500/15 text-emerald-300',
    closed: 'bg-white/10 text-slate-300',
    pending: 'bg-white/10 text-slate-300',
    openDot: 'bg-emerald-400',
    closedDot: 'bg-slate-400',
    pendingDot: 'bg-slate-500',
  },
} as const

/**
 * Store status badge (open/closed) shared by the footer (light) and the dark
 * hero card (dark). Stays in sync with the real opening hours via useOpeningStatus.
 */
export function StoreStatusBadge({ variant = 'light', className }: StoreStatusBadgeProps) {
  const status = useOpeningStatus()
  const styles = BADGE_STYLES[variant]
  const isOpen = status?.isOpen ?? false
  const stateClass = status === null ? styles.pending : isOpen ? styles.open : styles.closed
  const dotClass = status === null ? styles.pendingDot : isOpen ? styles.openDot : styles.closedDot
  const label = status === null ? 'Đang cập nhật' : isOpen ? 'Đang mở cửa' : 'Ngoài giờ'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold',
        stateClass,
        className
      )}
    >
      <span aria-hidden className={cn('h-1.5 w-1.5 rounded-full', dotClass)} />
      {label}
    </span>
  )
}
