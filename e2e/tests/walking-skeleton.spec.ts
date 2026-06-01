import { test, expect } from '@playwright/test'

const ADMIN_EMAIL = 'admin@mbi.local'
const ADMIN_PASSWORD = 'AdminPass1!'
const API_URL = process.env['API_URL'] ?? 'http://localhost:8000'

test.describe('Walking Skeleton — S0 critical path', () => {
  test.beforeAll(async ({ request }) => {
    // Wait until backend /ready returns 200
    let attempts = 0
    while (attempts < 30) {
      const res = await request.get(`${API_URL}/ready`)
      if (res.ok()) break
      await new Promise((r) => setTimeout(r, 2000))
      attempts++
    }
  })

  test('login and see S&P 500 universe', async ({ page }) => {
    // Navigate to app root — should redirect to /login
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)

    // Fill in login form
    await page.getByLabel('Email').fill(ADMIN_EMAIL)
    await page.getByLabel('Password').fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: /log in/i }).click()

    // Should redirect to /universes
    await expect(page).toHaveURL(/\/universes/, { timeout: 10_000 })

    // S&P 500 universe should be visible
    await expect(page.getByText('S&P 500')).toBeVisible({ timeout: 10_000 })
  })
})
