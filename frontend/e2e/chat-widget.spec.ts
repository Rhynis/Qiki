import { expect, test } from './fixtures'

test.describe('chat widget', () => {
  test('opens, sends a message and renders the assistant reply', async ({ page }) => {
    await page.goto('/')

    await page.getByRole('button', { name: 'Mở chat hỗ trợ' }).click()
    await expect(page.getByText('Trợ lý Gas Quốc Cường')).toBeVisible()

    const input = page.getByPlaceholder('Nhập tin nhắn...')
    await input.fill('Giá gas 12kg bao nhiêu?')
    await input.press('Enter')

    // The user message echoes and the (mocked) assistant reply renders.
    await expect(page.getByText('Giá gas 12kg bao nhiêu?')).toBeVisible()
    await expect(
      page.getByText('Dạ Qiki đã nhận tin nhắn của bạn, cửa hàng sẽ hỗ trợ ngay ạ.')
    ).toBeVisible()
  })
})
