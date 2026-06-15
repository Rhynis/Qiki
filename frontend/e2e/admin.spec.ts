import { loginAs } from './helpers'
import { expect, test } from './fixtures'

// Admin tables are intentionally horizontally scrollable, so these run on the
// desktop (chromium) project only — the mobile projects testIgnore this file.
test.describe('admin', () => {
  test.beforeEach(async ({ context }) => {
    await loginAs(context, 'admin')
  })

  test('dashboard renders the KPI cards', async ({ page }) => {
    await page.goto('/admin')
    await expect(page).toHaveURL(/\/admin$/)
    await expect(page.getByText('Đơn hôm nay')).toBeVisible()
    await expect(page.getByText('Doanh thu hôm nay')).toBeVisible()
  })

  test('products list loads (no infinite "Đang tải...")', async ({ page }) => {
    await page.goto('/admin/products')
    await expect(page.getByText('Bình gas Elf 12kg (đỏ)')).toBeVisible()
    await expect(page.getByText('Đang tải...')).toHaveCount(0)
  })

  test('orders page opens an order detail', async ({ page }) => {
    await page.goto('/admin/orders')
    await page.getByText('QC-000123').click()
    await expect(page.getByText('15 đường số 5, khu phố 32')).toBeVisible()
  })

  test('chat list renders with a status filter', async ({ page }) => {
    await page.goto('/admin/chat')
    await expect(page.getByRole('button', { name: 'Cần hỗ trợ' })).toBeVisible()
    await expect(page.getByText('0903026306')).toBeVisible()
  })

  test('users list loads', async ({ page }) => {
    await page.goto('/admin/users')
    await expect(page.getByText('customer@example.com')).toBeVisible()
  })

  test('knowledge base page loads', async ({ page }) => {
    await page.goto('/admin/knowledge-base')
    await expect(page).toHaveURL(/\/admin\/knowledge-base$/)
  })
})
