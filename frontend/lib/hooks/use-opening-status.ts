'use client'

import { useEffect, useState } from 'react'

export type OpeningStatus = {
  isOpen: boolean
}

/**
 * Tính trạng thái mở/đóng cửa theo giờ Việt Nam (UTC+7), không phụ thuộc múi giờ
 * trình duyệt. Khung giờ: T2-T6 mở 06:30, T7-CN mở 07:30, đóng 20:00.
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

/** Trả về trạng thái mở/đóng cửa, tự cập nhật mỗi phút. */
export function useOpeningStatus(): OpeningStatus {
  const [status, setStatus] = useState<OpeningStatus>(getOpeningStatus)

  useEffect(() => {
    const updateStatus = () => setStatus(getOpeningStatus())
    const mountUpdateId = window.setTimeout(updateStatus, 0)
    const intervalId = window.setInterval(updateStatus, 60_000)
    return () => {
      window.clearTimeout(mountUpdateId)
      window.clearInterval(intervalId)
    }
  }, [])

  return status
}
