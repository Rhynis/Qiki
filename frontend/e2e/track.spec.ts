import { expect, test } from './fixtures'

test.describe('track order', () => {
  test('a guest looks up an order by number + phone', async ({ page }) => {
    await page.goto('/track')

    await page.locator('#order_number').fill('QC-000123')
    await page.locator('#phone').fill('0903026306')
    await page.getByRole('button', { name: 'Tra cứu' }).click()

    await expect(page.getByText('QC-000123')).toBeVisible()
    await expect(page.getByText(/Trạng thái:/)).toBeVisible()
    await expect(page.getByRole('link', { name: 'Xem chi tiết' })).toBeVisible()
  })
})
