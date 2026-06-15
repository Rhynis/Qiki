import { loginAs } from './helpers'
import { expect, test } from './fixtures'

test.describe('logged-in customer', () => {
  test.beforeEach(async ({ context }) => {
    await loginAs(context, 'customer')
  })

  test('/account shows the profile', async ({ page }) => {
    await page.goto('/account')
    await expect(page).toHaveURL(/\/account$/)
    await expect(page.getByText('customer@example.com')).toBeVisible()
  })

  test('"Đơn hàng của tôi" lists the orders', async ({ page }) => {
    await page.goto('/orders')
    await expect(page.getByRole('heading', { name: 'Đơn hàng của tôi' })).toBeVisible()
    await expect(page.getByText('QC-000123')).toBeVisible()
  })

  test('checkout prefills the account name + phone', async ({ page }) => {
    // Put a product in the cart, then advance to the delivery step.
    await page.goto('/products/elf-12')
    await page.getByRole('button', { name: 'Mua ngay' }).click()
    await page.getByRole('button', { name: 'Tiến hành thanh toán' }).click()
    await expect(page.locator('#customer_name')).toHaveValue('Khách Hàng Test')
    await expect(page.locator('#customer_phone')).toHaveValue('0903026306')
  })
})
