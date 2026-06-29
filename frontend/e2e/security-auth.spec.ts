import { test, expect } from "@playwright/test"

function uniqueEmail(): string {
  return `sec-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`
}

test.describe("WebSocket auth security", () => {
  test("token JWT invalido mostra errore di autenticazione", async ({ page }) => {
    const email = uniqueEmail()

    await page.goto("/auth/register")
    await page.fill("input#name", "Security Test")
    await page.fill("input#email", email)
    await page.fill("input[id='password']", "password123")
    await page.fill("#confirmPassword", "password123")

    await page.route("**/api/auth/ws-token", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ token: "invalid.jwt.token.here" }),
      })
    })

    await page.click("button[type=submit]")
    await page.waitForURL(/\/chat/, { timeout: 15000 })
    await expect(page.getByText(/Sessione scaduta|Errore di autenticazione/)).toBeVisible({ timeout: 15000 })
  })

  test("token JWT scaduto mostra errore di autenticazione", async ({ page }) => {
    const email = uniqueEmail()

    await page.goto("/auth/register")
    await page.fill("input#name", "Security Test")
    await page.fill("input#email", email)
    await page.fill("input[id='password']", "password123")
    await page.fill("#confirmPassword", "password123")

    await page.route("**/api/auth/ws-token", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          token: "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0IiwidHlwZSI6IndzX3RpY2tldCIsImlhdCI6MTUwMDAwMDAwMCwiZXhwIjoxNTAwMDAwMDMwfQ.fake-signature",
        }),
      })
    })

    await page.click("button[type=submit]")
    await page.waitForURL(/\/chat/, { timeout: 15000 })
    await expect(page.getByText(/Sessione scaduta|Errore di autenticazione/)).toBeVisible({ timeout: 15000 })
  })

  test("API ws-token senza sessione restituisce 401", async ({ page }) => {
    const response = await page.request.post("/api/auth/ws-token")
    expect(response.status()).toBe(401)
  })

  test("connessione WebSocket con token manomesso viene rifiutata", async ({ page }) => {
    const email = uniqueEmail()

    await page.goto("/auth/register")
    await page.fill("input#name", "Security Test")
    await page.fill("input#email", email)
    await page.fill("input[id='password']", "password123")
    await page.fill("#confirmPassword", "password123")

    await page.route("**/api/auth/ws-token", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          token: "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0IiwidHlwZSI6IndzX3RpY2tldCIsImlhdCI6MTc0NzUwMDAwMCwiZXhwIjo5OTk5OTk5OTk5fQ.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        }),
      })
    })

    await page.click("button[type=submit]")
    await page.waitForURL(/\/chat/, { timeout: 15000 })
    await expect(page.getByText(/Sessione scaduta|Errore di autenticazione/)).toBeVisible({ timeout: 15000 })
  })

  test("WebSocket con token valido si connette (happy path)", async ({ page }) => {
    const email = uniqueEmail()

    await page.goto("/auth/register")
    await page.fill("input#name", "Security Test")
    await page.fill("input#email", email)
    await page.fill("input[id='password']", "password123")
    await page.fill("#confirmPassword", "password123")
    await page.click("button[type=submit]")
    await page.waitForURL(/\/chat/, { timeout: 15000 })
    await expect(page.getByText("Connesso")).toBeVisible({ timeout: 15000 })
  })
})
