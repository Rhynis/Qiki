import { expect, test } from './fixtures'

test.describe('products', () => {
  test('renders the catalog from the (mocked) API', async ({ page }) => {
    await page.goto('/products')
    await expect(page.getByRole('heading', { name: 'Bình gas Elf 12kg (đỏ)' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Nước Hoàn Hảo 20 lít' })).toBeVisible()
  })

  test('header "Sản phẩm" dropdown filters to Nước Uống', async ({ page }) => {
    await page.goto('/products')
    await page.getByRole('link', { name: 'Sản phẩm', exact: true }).hover()
    const nuoc = page.getByRole('menuitem', { name: 'Nước Uống' })
    await nuoc.waitFor({ state: 'visible' })
    await nuoc.click()

    await expect(page).toHaveURL(/category=nuoc_uong/)
    await expect(page.getByRole('heading', { name: 'Nước Hoàn Hảo 20 lít' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Bình gas Elf 12kg (đỏ)' })).toHaveCount(0)
  })

  test('header "Sản phẩm" link opens the all-products page', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('link', { name: 'Sản phẩm', exact: true }).click()

    await expect(page).toHaveURL(/\/products$/)
    await expect(page.getByRole('heading', { name: 'Bình gas Elf 12kg (đỏ)' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Nước Hoàn Hảo 20 lít' })).toBeVisible()
  })

  test('sort by price (asc) reorders via the URL', async ({ page }) => {
    await page.goto('/products')
    await page.getByRole('combobox', { name: 'Sắp xếp' }).click()
    await page.getByRole('option', { name: 'Giá tăng dần' }).click()

    await expect(page).toHaveURL(/sort_by=price/)
    await expect(page).toHaveURL(/sort_order=asc/)
    // Cheapest gas (6kg) is now part of the (re-fetched) list.
    await expect(page.getByRole('heading', { name: 'Bình gas Elf 6kg' })).toBeVisible()
  })

  test('clicking a product opens its detail page with add-to-cart', async ({ page }) => {
    await page.goto('/products')
    await page.getByRole('link', { name: 'Xem chi tiết Bình gas Elf 12kg (đỏ)' }).click()

    await expect(page).toHaveURL(/\/products\/elf-12$/)
    await expect(page.getByRole('heading', { name: 'Bình gas Elf 12kg (đỏ)' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Thêm vào giỏ' })).toBeVisible()
  })

  test('a grouped product card shows the "Nhiều lựa chọn" hint', async ({ page }) => {
    await page.goto('/products')
    // Elf 12kg belongs to a parent with siblings, so its card advertises options.
    await expect(page.getByText('Nhiều lựa chọn màu/loại').first()).toBeVisible()
  })

  test('the variant selector switches the detail price and stock', async ({ page }) => {
    await page.goto('/products/elf-12')

    // The headline price paragraph reflects the currently selected variant.
    const headlinePrice = page.locator('p.text-3xl.text-primary')
    await expect(headlinePrice).toHaveText(/710\.000/)

    // The parent has two variants; selecting the 6kg option updates the price.
    const sixKg = page.getByRole('radio', { name: /6 kg/ })
    await sixKg.click()
    await expect(sixKg).toHaveAttribute('aria-checked', 'true')
    await expect(headlinePrice).toHaveText(/350\.000/)
  })
})
