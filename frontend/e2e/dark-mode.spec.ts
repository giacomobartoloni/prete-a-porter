import { test, expect, Page } from "@playwright/test"

/**
 * Helper: register a new user and navigate to /chat
 */
async function registerAndGoToChat(page: Page) {
  const email = `test-darkmode-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`
  await page.goto("/auth/register")
  await expect(page.locator("h1")).toContainText("Crea Account")
  await page.fill("input#name", "Dark Mode Test")
  await page.fill("input#email", email)
  await page.fill("input[id='password']", "password123")
  await page.fill("#confirmPassword", "password123")
  await page.click("button[type=submit]")
  await page.waitForURL(/\/chat/, { timeout: 15000 })
}

test.describe("Dark mode toggle", () => {
  test("theme toggle button is visible in chat header", async ({ page }) => {
    await registerAndGoToChat(page)
    const toggle = page.locator('button[aria-label="Toggle dark mode"]')
    await expect(toggle).toBeVisible()
  })

  test("clicking toggle toggles dark class on html element", async ({ page }) => {
    await registerAndGoToChat(page)

    const toggle = page.locator('button[aria-label="Toggle dark mode"]')
    await expect(toggle).toBeVisible()

    // Get initial state
    const wasDark = await page.locator("html").evaluate(el => el.classList.contains("dark"))

    // Click to toggle
    await toggle.click()
    const afterFirstClick = await page.locator("html").evaluate(el => el.classList.contains("dark"))
    expect(afterFirstClick).toBe(!wasDark)

    // Click to toggle back
    await toggle.click()
    const afterSecondClick = await page.locator("html").evaluate(el => el.classList.contains("dark"))
    expect(afterSecondClick).toBe(wasDark)
  })

  test("dark mode preference persists after page reload", async ({ page }) => {
    await registerAndGoToChat(page)

    const toggle = page.locator('button[aria-label="Toggle dark mode"]')
    const html = page.locator("html")

    // If not already dark, toggle to dark
    const isDark = await html.evaluate(el => el.classList.contains("dark"))
    if (!isDark) {
      await toggle.click()
    }
    await expect(html).toHaveClass(/dark/)

    // Reload
    await page.reload()
    await page.waitForURL(/\/chat/, { timeout: 15000 })

    // Must still be dark after reload
    await expect(html).toHaveClass(/dark/)
  })
})
