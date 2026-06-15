import { expect, test } from './fixtures'

test.describe('auth forms', () => {
  test('register shows the password rule + inline validation that clears', async ({ page }) => {
    await page.goto('/register')

    // The password rule (6 + uppercase + digit) is always shown.
    await expect(
      page.getByText('Mật khẩu tối thiểu 6 ký tự, có 1 chữ hoa và 1 chữ số.')
    ).toBeVisible()

    // A weak password surfaces an inline error on blur/submit...
    await page.locator('#full_name').fill('Nguyen Van Test')
    await page.locator('#email').fill('user@example.com')
    await page.locator('#password').fill('abc')
    await page.locator('#confirmPassword').fill('abc')
    await page.getByRole('button', { name: 'Đăng ký' }).click()
    await expect(page.locator('p.text-red-600').filter({ hasText: /Mật khẩu/ })).toBeVisible()

    // ...and clears once the rule is satisfied.
    await page.locator('#password').fill('Abcdef1')
    await page.locator('#confirmPassword').fill('Abcdef1')
    await expect(page.getByText('Mật khẩu cần có ít nhất 1 chữ hoa')).toHaveCount(0)
  })

  test('register auto-formats the phone into 3-4-3 groups', async ({ page }) => {
    await page.goto('/register')
    await page.locator('#phone').fill('0903026306')
    await expect(page.locator('#phone')).toHaveValue('090 3026 306')
  })

  test('login surfaces an inline error for an invalid email', async ({ page }) => {
    await page.goto('/login')
    await page.locator('#email').fill('not-an-email')
    await page.locator('#password').fill('Abcdef1')
    await page.getByRole('button', { name: 'Đăng nhập' }).click()
    await expect(page.locator('p.text-red-600').first()).toBeVisible()
  })

  test('forgot-password shows an inline success message (not a toast)', async ({ page }) => {
    await page.goto('/forgot-password')
    await page.locator('#email').fill('user@example.com')
    await page.getByRole('button', { name: /Gửi/ }).click()
    await expect(
      page.getByText('Nếu email tồn tại, hướng dẫn đặt lại mật khẩu đã được gửi.')
    ).toBeVisible()
  })
})
