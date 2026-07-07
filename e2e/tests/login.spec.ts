import { test, expect } from '@playwright/test'

const ADMIN_EMAIL = 'admin@mbilabs.io'
const ADMIN_PASSWORD = 'change-me-on-first-login'
const API_URL = process.env['API_URL'] ?? 'http://127.0.0.1:8000'

test.describe('S6 — Login / Logout', () => {
  test.beforeAll(async ({ request }) => {
    let attempts = 0
    while (attempts < 30) {
      const res = await request.get(`${API_URL}/ready`)
      if (res.ok()) break
      await new Promise((r) => setTimeout(r, 2000))
      attempts++
    }
  })

  test('login as admin redirects to /universes', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)

    await page.getByLabel('Email').fill(ADMIN_EMAIL)
    await page.getByLabel('Password').fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: /log in/i }).click()

    await expect(page).toHaveURL(/\/universes/, { timeout: 10_000 })
  })

  test('logout redirects to /login', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)

    await page.getByLabel('Email').fill(ADMIN_EMAIL)
    await page.getByLabel('Password').fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: /log in/i }).click()
    await expect(page).toHaveURL(/\/universes/, { timeout: 10_000 })

    const userMenu = page.locator('[data-testid="user-menu"]')
    if (await userMenu.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await userMenu.click()
      await page.getByRole('button', { name: /log out|sign out/i }).click()
    }

    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 })
  })
})
