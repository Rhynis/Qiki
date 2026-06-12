'use client'

import { useEffect, useState } from 'react'

export type OpeningStatus = {
  isOpen: boolean
}

/**
 * Compute the open/closed status in Vietnam time (UTC+7), independent of the
 * browser timezone. Hours: Mon-Fri open 06:30, Sat-Sun open 07:30, close 20:00.
 */
export function getOpeningStatus(): OpeningStatus {
  const vietnamTime = new Date(Date.now() + 7 * 60 * 60 * 1000)
  const day = vietnamTime.getUTCDay()
  const minutes = vietnamTime.getUTCHours() * 60 + vietnamTime.getUTCMinutes()
  const isWeekend = day === 0 || day === 6
  const opensAt = isWeekend ? 7 * 60 + 30 : 6 * 60 + 30
  const closesAt = 20 * 60

  return { isOpen: minutes >= opensAt && minutes < closesAt }
}

/** Return the open/closed status, refreshing every minute. */
export function useOpeningStatus(): OpeningStatus | null {
  const [status, setStatus] = useState<OpeningStatus | null>(null)

  useEffect(() => {
    const updateStatus = () => setStatus(getOpeningStatus())
    updateStatus()
    const intervalId = window.setInterval(updateStatus, 60_000)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        updateStatus()
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      window.clearInterval(intervalId)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [])

  return status
}
