import { expect, test } from './fixtures'

test.describe('guest checkout', () => {
  test('a guest orders end-to-end with no /login redirect', async ({ page }) => {
    // Record every main-frame URL so we can assert the journey never bounced to /login.
    const visited: string[] = []
    page.on('framenavigated', (frame) => {
      if (frame === page.mainFrame()) visited.push(frame.url())
    })

    // Add a product and jump straight to checkout ("Mua ngay").
    await page.goto('/products/elf-12')
    await page.getByRole('button', { name: 'Mua ngay' }).click()
    await expect(page).toHaveURL(/\/checkout$/)

    // Step 1 — cart review.
    await page.getByRole('button', { name: 'Tiến hành thanh toán' }).click()

    // Step 2 — customer + delivery. City is TP.HCM and the wards are the real
    // served set (Bình Thạnh / Thủ Đức), no Quận 1/3/7.
    await expect(page.getByRole('option', { name: 'Bình Lợi Trung' })).toHaveCount(1)
    await expect(page.getByRole('option', { name: 'Quận 1' })).toHaveCount(0)
    await page.locator('#customer_name').fill('Nguyen Van Test')
    await page.locator('#customer_phone').fill('0903026306')
    await page.locator('#delivery_address').fill('15 đường số 5, khu phố 32')
    await page.selectOption('#delivery_ward', { label: 'Bình Lợi Trung' })
    await page.getByRole('button', { name: 'Tiếp tục' }).click()

    // Step 3 — payment (COD).
    await page.getByText('Thanh toán khi nhận hàng').click()
    await page.getByRole('button', { name: 'Tiếp tục' }).click()

    // Step 4 — confirm → order created (mocked) → success page.
    await page.getByRole('button', { name: 'Xác nhận đặt hàng' }).click()
    await expect(page).toHaveURL(/\/checkout\/success\//)

    expect(visited.some((url) => url.includes('/login'))).toBe(false)
  })
})
