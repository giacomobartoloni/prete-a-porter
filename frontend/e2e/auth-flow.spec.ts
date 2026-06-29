import { test, expect } from "@playwright/test"

test("un nuovo utente può registrarsi ed essere reindirizzato a /chat", async ({ page }) => {
  const email = `test-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`

  await page.goto("/auth/register")
  await expect(page.locator("h1")).toContainText("Crea Account")

  await page.fill("input#name", "Test User")
  await page.fill("input#email", email)
  await page.fill("input[id='password']", "password123")
  await page.fill("#confirmPassword", "password123")

  await page.click("button[type=submit]")

  await page.waitForURL(/\/chat/, { timeout: 15000 })
  await expect(page).toHaveURL(/\/chat/)

  await expect(page.getByText("Errore di autenticazione")).not.toBeVisible()
})
