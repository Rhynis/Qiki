'use client'

import { useEffect, useState } from 'react'

const TYPING_STATUSES = ['Đang đọc câu hỏi…', 'Đang tìm thông tin…', 'Đang soạn câu trả lời…']

export function TypingIndicator() {
  const [statusIndex, setStatusIndex] = useState(0)

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setStatusIndex((current) => (current + 1) % TYPING_STATUSES.length)
    }, 1500)

    return () => window.clearInterval(intervalId)
  }, [])

  return (
    <div className="flex flex-col gap-1 rounded-md bg-slate-100 px-3 py-2 text-slate-500">
      <div className="flex items-center gap-1">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]" />
      </div>
      <span aria-live="polite" className="text-xs text-slate-500">
        {TYPING_STATUSES[statusIndex]}
      </span>
    </div>
  )
}
