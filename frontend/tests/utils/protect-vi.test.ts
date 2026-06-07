import { describe, expect, it } from 'vitest'
import { protectVi } from '@/lib/utils'

describe('protectVi', () => {
  it('keeps trong gio mo cua phrase together', () => {
    expect(protectVi('Nhận đơn qua Zalo trong giờ mở cửa.')).toContain(
      'trong\u00a0giờ\u00a0mở\u00a0cửa'
    )
  })
})
