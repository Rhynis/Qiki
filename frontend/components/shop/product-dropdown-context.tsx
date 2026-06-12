'use client'

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from 'react'

type ProductDropdownContextValue = {
  openId: string | null
  setOpenId: Dispatch<SetStateAction<string | null>>
}

const ProductDropdownContext = createContext<ProductDropdownContextValue | null>(null)

/** Tracks which product filter/sort dropdown is open so only one shows at a time. */
export function ProductDropdownProvider({ children }: { children: ReactNode }) {
  const [openId, setOpenId] = useState<string | null>(null)
  const value = useMemo(() => ({ openId, setOpenId }), [openId])
  return <ProductDropdownContext.Provider value={value}>{children}</ProductDropdownContext.Provider>
}

/**
 * Returns controlled `open`/`onOpenChange` props for a single shared-open dropdown.
 * Opening one closes the others; a stale close from a previously-open dropdown
 * never clears the newly opened one. Falls back to uncontrolled (no provider).
 */
export function useDropdownOpen(id: string): {
  open?: boolean
  onOpenChange?: (open: boolean) => void
} {
  const context = useContext(ProductDropdownContext)
  if (!context) return {}
  const { openId, setOpenId } = context
  return {
    open: openId === id,
    onOpenChange: (next: boolean) => {
      setOpenId((current) => (next ? id : current === id ? null : current))
    },
  }
}
