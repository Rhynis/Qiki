'use client'

import { useEffect, useState } from 'react'

type OpeningStatus = {
  isOpen: boolean
  label: string
}

function getOpeningStatus(): OpeningStatus {
  const vietnamTime = new Date(Date.now() + 7 * 60 * 60 * 1000)
  const day = vietnamTime.getUTCDay()
  const minutes = vietnamTime.getUTCHours() * 60 + vietnamTime.getUTCMinutes()
  const isWeekend = day === 0 || day === 6
  const opensAt = isWeekend ? 7 * 60 + 30 : 6 * 60 + 30
  const closesAt = 20 * 60
  const isOpen = minutes >= opensAt && minutes < closesAt

  return {
    isOpen,
    label: isOpen ? 'Đang mở cửa' : 'Đã đóng cửa',
  }
}

export function OpeningHoursBadge() {
  const [status, setStatus] = useState<OpeningStatus>(getOpeningStatus)

  useEffect(() => {
    const intervalId = window.setInterval(() => setStatus(getOpeningStatus()), 60_000)
    return () => window.clearInterval(intervalId)
  }, [])

  return (
    <span
      suppressHydrationWarning
      className={
        status.isOpen
          ? 'inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700'
          : 'inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600'
      }
    >
      {status.label}
    </span>
  )
}
