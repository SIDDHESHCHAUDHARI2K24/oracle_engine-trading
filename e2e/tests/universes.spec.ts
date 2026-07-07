import { test, expect } from '@playwright/test'

const ADMIN_EMAIL = 'admin@mbilabs.io'
const ADMIN_PASSWORD = 'change-me-on-first-login'
const API_URL = process.env['API_URL'] ?? 'http://127.0.0.1:8000'

test.describe('S6 — Universes detail', () => {
  test.beforeAll(async ({ request }) => {
    let attempts = 0
    while (attempts < 30) {
      const res = await request.get(`${API_URL}/ready`)
      if (res.ok()) break
      await new Promise((r) => setTimeout(r, 2000))
      attempts++
    }
  })

  test('navigate to /universes, click a universe, verify detail page', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)

    await page.getByLabel('Email').fill(ADMIN_EMAIL)
    await page.getByLabel('Password').fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: /log in/i }).click()
    await expect(page).toHaveURL(/\/universes/, { timeout: 10_000 })

    await expect(page.getByText('S&P 500')).toBeVisible({ timeout: 10_000 })
    await page.getByText('S&P 500').click()

    await expect(page).toHaveURL(/\/universes\/[\w-]+/, { timeout: 10_000 })
    await expect(page.locator('text=Tickers').or(page.locator('text=Membership'))).toBeVisible({ timeout: 10_000 })
  })
})
