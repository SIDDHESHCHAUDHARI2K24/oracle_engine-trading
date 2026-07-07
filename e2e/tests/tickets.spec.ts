import { test, expect } from '@playwright/test'

const ADMIN_EMAIL = 'admin@mbilabs.io'
const ADMIN_PASSWORD = 'change-me-on-first-login'
const API_URL = process.env['API_URL'] ?? 'http://127.0.0.1:8000'

test.describe('S6 — Conviction Tickets', () => {
  test.beforeAll(async ({ request }) => {
    let attempts = 0
    while (attempts < 30) {
      const res = await request.get(`${API_URL}/ready`)
      if (res.ok()) break
      await new Promise((r) => setTimeout(r, 2000))
      attempts++
    }
  })

  test('tickets inbox renders', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)

    await page.getByLabel('Email').fill(ADMIN_EMAIL)
    await page.getByLabel('Password').fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: /log in/i }).click()
    await expect(page).toHaveURL(/\/universes/, { timeout: 10_000 })

    await page.goto('/tickets')
    await expect(page).toHaveURL(/\/tickets/, { timeout: 10_000 })

    await expect(page.locator('table, [role="table"], [data-testid="tickets-table"]').first()).toBeVisible({ timeout: 10_000 })
  })

  test('click a ticket and verify detail page', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)

    await page.getByLabel('Email').fill(ADMIN_EMAIL)
    await page.getByLabel('Password').fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: /log in/i }).click()
    await expect(page).toHaveURL(/\/universes/, { timeout: 10_000 })

    await page.goto('/tickets')
    await expect(page).toHaveURL(/\/tickets/, { timeout: 10_000 })

    const ticketLink = page.locator('table tbody tr a, [role="table"] [role="row"] a').first()
    if (await ticketLink.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await ticketLink.click()
      await expect(page).toHaveURL(/\/tickets\/[\w-]+/, { timeout: 10_000 })
    }
  })
})
