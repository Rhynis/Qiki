import { expect, test } from './fixtures'
import { expectNoHorizontalScroll } from './helpers'

// These layout guards matter most on the mobile projects, but no horizontal
// overflow is a valid invariant on desktop too, so they run on every project.
const pagesWithoutOverflow: Array<{ name: string; path: string }> = [
  { name: 'home', path: '/' },
  { name: 'products', path: '/products' },
  { name: 'product detail', path: '/products/elf-12' },
  { name: 'cart', path: '/cart' },
  { name: 'checkout', path: '/checkout' },
  { name: 'track', path: '/track' },
  { name: 'login', path: '/login' },
  { name: 'register', path: '/register' },
]

test.describe('mobile layout', () => {
  for (const { name, path } of pagesWithoutOverflow) {
    test(`no horizontal overflow on ${name}`, async ({ page }) => {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      await expectNoHorizontalScroll(page)
    })
  }

  test('chat widget opens near full-width and stays on-screen', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Mở chat hỗ trợ' }).click()

    const window = page.getByText('Trợ lý Gas Quốc Cường')
    await expect(window).toBeVisible()
    await expectNoHorizontalScroll(page)
  })

  test('header navigation is reachable', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('button', { name: 'Sản phẩm' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Giỏ hàng' })).toBeVisible()
  })

  test('login success toast does not cover the header menu', async ({ page }) => {
    await page.goto('/login')
    await page.locator('#identifier').fill('0903026306')
    await page.locator('#password').fill('Abcdef1')
    await page.getByRole('button', { name: 'Đăng nhập' }).click()

    await expect(page.getByText('Đăng nhập thành công')).toBeVisible()
    // The header menu must stay actionable (trial click fails if the toast covers it).
    await page.getByRole('button', { name: 'Sản phẩm' }).click({ trial: true })
  })
})
