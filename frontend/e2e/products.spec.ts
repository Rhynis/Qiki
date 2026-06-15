import { expect, test } from './fixtures'

test.describe('products', () => {
  test('renders the catalog from the (mocked) API', async ({ page }) => {
    await page.goto('/products')
    await expect(page.getByRole('heading', { name: 'Bình gas Elf 12kg (đỏ)' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Nước Hoàn Hảo 20 lít' })).toBeVisible()
  })

  test('header "Sản phẩm" dropdown filters to Nước Uống', async ({ page }) => {
    await page.goto('/products')
    await page.getByRole('button', { name: 'Sản phẩm' }).hover()
    const nuoc = page.getByRole('menuitem', { name: 'Nước Uống' })
    await nuoc.waitFor({ state: 'visible' })
    await nuoc.click()

    await expect(page).toHaveURL(/category=nuoc_uong/)
    await expect(page.getByRole('heading', { name: 'Nước Hoàn Hảo 20 lít' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Bình gas Elf 12kg (đỏ)' })).toHaveCount(0)
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
})
