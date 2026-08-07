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

  test('a grouped water card shows the "Nhiều lựa chọn" hint and links to a selector', async ({
    page,
  }) => {
    await page.goto('/products')
    // Vihawa's two same-size, different-form bottles collapse into ONE card
    // (cheapest variant as representative) advertising options (#342).
    await expect(page.getByText('Nhiều lựa chọn màu/loại').first()).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Nước Vihawa 20 lít' })).toBeVisible()
    // Only the cheapest variant's own card renders — its sibling is folded in.
    await expect(
      page.getByRole('heading', { name: 'Nước Vihawa 20 lít (bình nóng lạnh)' })
    ).toHaveCount(0)

    await page.getByRole('link', { name: 'Xem chi tiết Nước Vihawa 20 lít' }).click()
    await expect(page).toHaveURL(/\/products\/vihawa-normal$/)
    await expect(page.getByRole('radiogroup')).toBeVisible()
    await expect(page.getByRole('radio', { name: /Bình nóng lạnh/ })).toBeVisible()
  })

  test('a gas product card never shows the "Nhiều lựa chọn" hint', async ({ page }) => {
    await page.goto('/products?category=gas')
    // Elf 12kg/6kg share a brand parent in the DB, but gas is listed
    // individually — no "from"/"multiple options" hint on gas cards (#342).
    await expect(page.getByRole('heading', { name: 'Bình gas Elf 12kg (đỏ)' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Bình gas Elf 6kg' })).toBeVisible()
    await expect(page.getByText('Nhiều lựa chọn màu/loại')).toHaveCount(0)
  })

  test('a gas detail page never shows a variant selector', async ({ page }) => {
    await page.goto('/products/elf-12')

    // The headline price (rendered by PriceDisplay) always matches this exact
    // product — gas never offers a selector to switch to a sibling size (#342).
    const headlinePrice = page.locator('span.text-3xl.text-primary')
    await expect(headlinePrice).toHaveText(/710\.000/)
    await expect(page.getByRole('heading', { name: 'Bình gas Elf 12kg (đỏ)' })).toBeVisible()
    await expect(page.getByText('SKU ELF-12KG')).toBeVisible()
    await expect(page.getByRole('radiogroup')).toHaveCount(0)
  })

  test('the water variant selector switches the detail price and stock', async ({ page }) => {
    await page.goto('/products/vihawa-normal')

    const headlinePrice = page.locator('span.text-3xl.text-primary')
    await expect(headlinePrice).toHaveText(/55\.000/)

    // Vihawa's two variants (same size, different bottle form); selecting the
    // hot-cold option updates the price.
    const hotCold = page.getByRole('radio', { name: /Bình nóng lạnh/ })
    await hotCold.click()
    await expect(hotCold).toHaveAttribute('aria-checked', 'true')
    await expect(headlinePrice).toHaveText(/65\.000/)
  })
})
