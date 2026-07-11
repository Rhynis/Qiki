'use client'

import { Heart } from 'lucide-react'
import { usePathname, useRouter } from 'next/navigation'
import type { MouseEvent } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { useToggleWishlist, useWishlist } from '@/lib/hooks/use-wishlist'

type WishlistButtonProps = {
  productId: string
  className?: string
  withLabel?: boolean
}

/**
 * Heart toggle to save/unsave a product. Shown to everyone, but a guest is
 * prompted to log in on click. Safe to place over a card-wide link (it stops
 * propagation so it never triggers navigation).
 */
export function WishlistButton({ productId, className, withLabel = false }: WishlistButtonProps) {
  const router = useRouter()
  const pathname = usePathname()
  const { savedIds, isAuthenticated } = useWishlist()
  const toggle = useToggleWishlist()

  const saved = savedIds.has(productId)
  const label = saved ? 'Bỏ khỏi yêu thích' : 'Lưu vào yêu thích'

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault()
    event.stopPropagation()
    if (!isAuthenticated) {
      toast.info('Vui lòng đăng nhập để lưu sản phẩm yêu thích')
      router.push(`/login?redirectTo=${encodeURIComponent(pathname)}`)
      return
    }
    toggle.mutate({ productId, saved })
  }

  return (
    <Button
      type="button"
      variant={withLabel ? 'outline' : 'ghost'}
      size={withLabel ? 'default' : 'icon'}
      className={cn(withLabel ? '' : 'h-11 w-11', className)}
      title={label}
      aria-label={label}
      aria-pressed={saved}
      disabled={toggle.isPending}
      onClick={handleClick}
    >
      <Heart className={cn('h-5 w-5', saved && 'fill-red-500 text-red-500')} />
      {withLabel ? <span className="ml-2">{saved ? 'Đã lưu' : 'Lưu'}</span> : null}
    </Button>
  )
}
