import { test, expect } from "@playwright/test"

test("dopo la registrazione il WebSocket si connette e mostra Connesso", async ({ page }) => {
  const email = `test-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`

  await page.goto("/auth/register")
  await expect(page.locator("h1")).toContainText("Crea Account")

  await page.fill("input#name", "WS Test User")
  await page.fill("input#email", email)
  await page.fill("input[id='password']", "password123")
  await page.fill("#confirmPassword", "password123")

  await page.click("button[type=submit]")
  await page.waitForURL(/\/chat/, { timeout: 15000 })
  await expect(page).toHaveURL(/\/chat/)

  await expect(page.getByText("Connesso")).toBeVisible({ timeout: 15000 })
  await expect(page.getByText("Disconnesso")).not.toBeVisible()
})

test("navigazione rapida da chat durante la connessione WebSocket non lascia leak", async ({ page }) => {
  const email = `leak-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`

  await page.goto("/auth/register")
  await page.fill("input#name", "Leak Test")
  await page.fill("input#email", email)
  await page.fill("input[id='password']", "password123")
  await page.fill("#confirmPassword", "password123")

  const wsTokenPromise = page.waitForResponse("**/api/auth/ws-token")

  await page.click("button[type=submit]")
  await page.waitForURL(/\/chat/, { timeout: 15000 })
  await wsTokenPromise

  await page.goto("/")
  await expect(page.locator("h1")).toContainText("Prete-a-porter")

  await page.goto("/chat")
  await expect(page.getByText("Connesso")).toBeVisible({ timeout: 15000 })
})
