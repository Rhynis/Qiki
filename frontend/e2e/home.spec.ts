import { expect, test } from './fixtures'

test.describe('home', () => {
  test('loads the hero, CTAs and footer', async ({ page }) => {
    await page.goto('/')

    const main = page.getByRole('main')
    await expect(main.getByRole('button', { name: 'Chat với Qiki' })).toBeVisible()
    await expect(main.getByRole('link', { name: 'Xem sản phẩm' })).toBeVisible()
    await expect(page.getByText('Bình Thạnh').first()).toBeVisible()
    await expect(page.getByRole('contentinfo')).toBeVisible()
  })

  test('"Xem sản phẩm" navigates to the products page', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('main').getByRole('link', { name: 'Xem sản phẩm' }).click()
    await expect(page).toHaveURL(/\/products$/)
    await expect(page.getByText(/sản phẩm/i).first()).toBeVisible()
  })
})
