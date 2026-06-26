'use client'

import { useEffect, useState } from 'react'

type DetailedHealthResponse = {
  llm_provider?: string
}

export function DemoModeBanner() {
  const [isDemoMode, setIsDemoMode] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const res = await fetch('/health/detailed')
        const data = (await res.json()) as DetailedHealthResponse

        if (!cancelled) {
          setIsDemoMode(data.llm_provider === 'ollama')
        }
      } catch {
        // Stay hidden on failure.
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [])

  if (!isDemoMode) {
    return null
  }

  return (
    <div className="border-b border-amber-300 bg-amber-100 px-4 py-2 text-center text-sm text-amber-900">
      🖥️ Chế độ Demo: LLM đang chạy cục bộ (Qwen 2.5 7B) trên máy Mac qua Cloudflare Tunnel
    </div>
  )
}
