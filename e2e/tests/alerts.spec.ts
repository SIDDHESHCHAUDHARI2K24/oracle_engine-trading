import { test, expect } from '@playwright/test'

const ADMIN_EMAIL = 'admin@mbilabs.io'
const ADMIN_PASSWORD = 'change-me-on-first-login'
const API_URL = process.env['API_URL'] ?? 'http://127.0.0.1:8000'

test.describe('S6 — Alerts', () => {
  test.beforeAll(async ({ request }) => {
    let attempts = 0
    while (attempts < 30) {
      const res = await request.get(`${API_URL}/ready`)
      if (res.ok()) break
      await new Promise((r) => setTimeout(r, 2000))
      attempts++
    }
  })

  test('navigate to /monitoring/alerts and verify page renders', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)

    await page.getByLabel('Email').fill(ADMIN_EMAIL)
    await page.getByLabel('Password').fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: /log in/i }).click()
    await expect(page).toHaveURL(/\/universes/, { timeout: 10_000 })

    await page.goto('/monitoring/alerts')
    await expect(page).toHaveURL(/\/monitoring\/alerts/, { timeout: 10_000 })

    const hasContent = await Promise.race([
      page.locator('table, [role="table"]').first().waitFor({ state: 'visible', timeout: 8_000 }).then(() => true),
      page.locator('text=No alerts, text=empty, text=No data').first().waitFor({ state: 'visible', timeout: 8_000 }).then(() => true),
    ]).catch(() => false)

    expect(hasContent).toBeTruthy()
  })
})
