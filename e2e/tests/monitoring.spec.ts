import { test, expect } from '@playwright/test'

const ADMIN_EMAIL = 'admin@mbilabs.io'
const ADMIN_PASSWORD = 'change-me-on-first-login'
const API_URL = process.env['API_URL'] ?? 'http://127.0.0.1:8000'

test.describe('S6 — Monitoring', () => {
  test.beforeAll(async ({ request }) => {
    let attempts = 0
    while (attempts < 30) {
      const res = await request.get(`${API_URL}/ready`)
      if (res.ok()) break
      await new Promise((r) => setTimeout(r, 2000))
      attempts++
    }
  })

  test('monitoring tabs visible', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)

    await page.getByLabel('Email').fill(ADMIN_EMAIL)
    await page.getByLabel('Password').fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: /log in/i }).click()
    await expect(page).toHaveURL(/\/universes/, { timeout: 10_000 })

    await page.goto('/monitoring')
    await expect(page).toHaveURL(/\/monitoring/, { timeout: 10_000 })

    for (const tab of ['Overview', 'Coverage', 'Drift', 'Runs']) {
      await expect(page.locator(`button:has-text("${tab}"), a:has-text("${tab}"), [role="tab"]:has-text("${tab}")`)).toBeVisible({ timeout: 5_000 })
    }
  })

  test('health overview renders', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)

    await page.getByLabel('Email').fill(ADMIN_EMAIL)
    await page.getByLabel('Password').fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: /log in/i }).click()
    await expect(page).toHaveURL(/\/universes/, { timeout: 10_000 })

    await page.goto('/monitoring')
    await expect(page).toHaveURL(/\/monitoring/, { timeout: 10_000 })

    await expect(page.locator('text=Health').first()).toBeVisible({ timeout: 10_000 })
  })
})
