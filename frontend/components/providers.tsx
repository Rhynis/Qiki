'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { useEffect, useState, type ReactNode } from 'react'
import { TooltipProvider } from '@/components/ui/tooltip'

/** Application-level client providers. */
export function Providers({ children }: { children: ReactNode }) {
  // Flag the document as hydrated once the client tree has committed. This runs
  // after every descendant effect, so all event handlers are attached by now;
  // E2E tests wait on it to avoid interacting before the app is interactive.
  useEffect(() => {
    document.documentElement.dataset.hydrated = 'true'
  }, [])

  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5 * 60 * 1000,
            refetchOnWindowFocus: false,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>{children}</TooltipProvider>
      {process.env.NODE_ENV === 'development' ? <ReactQueryDevtools initialIsOpen={false} /> : null}
    </QueryClientProvider>
  )
}
