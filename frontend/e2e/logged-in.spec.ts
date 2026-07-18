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

  test('user menu opens on hover and closes on mouse leave', async ({ page, isMobile }) => {
    test.skip(isMobile, 'Hover behavior is covered by the desktop project.')

    await page.goto('/')
    // The name/avatar is a link to /account; hovering the row opens the menu.
    const nameLink = page.getByRole('link', { name: /Khách Hàng Test/ })
    await nameLink.hover()

    await expect(page.getByRole('menuitem', { name: 'Tài khoản' })).toBeVisible()

    await page.mouse.move(0, 0)
    await expect(page.getByRole('menuitem', { name: 'Tài khoản' })).toBeHidden()

    // Clicking the name navigates straight to the account page.
    await nameLink.click()
    await expect(page).toHaveURL(/\/account$/)
  })

  test('user menu opens on tap for touch viewports', async ({ page, isMobile }) => {
    test.skip(!isMobile, 'Tap behavior is covered by the mobile projects.')

    await page.goto('/')
    // Touch has no hover, so the dedicated caret button opens the menu.
    await page.getByRole('button', { name: 'Mở menu tài khoản' }).click()

    await expect(page.getByRole('menuitem', { name: 'Tài khoản' })).toBeVisible()
  })
})
