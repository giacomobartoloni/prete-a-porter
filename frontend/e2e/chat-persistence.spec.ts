import { test, expect } from "@playwright/test"

test("nuova conversazione viene creata al caricamento della pagina chat", async ({ page }) => {
  const email = `persist-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`

  await page.goto("/auth/register")
  await expect(page.locator("h1")).toContainText("Crea Account")

  await page.fill("input#name", "Persist Test")
  await page.fill("input#email", email)
  await page.fill("input[id='password']", "password123")
  await page.fill("#confirmPassword", "password123")

  await page.click("button[type=submit]")
  await page.waitForURL(/\/chat/, { timeout: 15000 })

  // The page auto-creates a conversation and updates URL with convId
  await expect(page).toHaveURL(/\/chat\?convId=/)
})

test("conversazione creata appare nella sidebar", async ({ page }) => {
  const email = `sidebar-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`

  await page.goto("/auth/register")
  await page.fill("input#name", "Sidebar Test")
  await page.fill("input#email", email)
  await page.fill("input[id='password']", "password123")
  await page.fill("#confirmPassword", "password123")
  await page.click("button[type=submit]")
  await page.waitForURL(/\/chat/, { timeout: 15000 })

  // Sidebar should show the conversation with default title
  await expect(page.getByText("Conversazione")).toBeVisible({ timeout: 10000 })
})

test("conversazione persiste dopo navigazione e ritorno", async ({ page }) => {
  const email = `nav-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`

  // Create user and let the chat page create a conversation
  await page.goto("/auth/register")
  await page.fill("input#name", "Nav Test")
  await page.fill("input#email", email)
  await page.fill("input[id='password']", "password123")
  await page.fill("#confirmPassword", "password123")
  await page.click("button[type=submit]")
  await page.waitForURL(/\/chat/, { timeout: 15000 })
  await expect(page).toHaveURL(/\/chat\?convId=/)

  // Extract the conversation ID from URL
  const url = page.url()
  const convId = new URL(url).searchParams.get("convId")

  // Navigate away
  await page.goto("/")
  await expect(page.locator("h1")).toContainText("Prete-a-porter")

  // Navigate back to chat — the sidebar should still show the conversation
  await page.goto("/chat")
  await expect(page.getByText("Conversazione")).toBeVisible({ timeout: 10000 })
})

test("conversazione esistente viene caricata con convId in URL", async ({ page }) => {
  const email = `load-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`

  // Create user and let the chat page create a conversation
  await page.goto("/auth/register")
  await page.fill("input#name", "Load Test")
  await page.fill("input#email", email)
  await page.fill("input[id='password']", "password123")
  await page.fill("#confirmPassword", "password123")
  await page.click("button[type=submit]")
  await page.waitForURL(/\/chat/, { timeout: 15000 })
  const url = page.url()
  const convId = new URL(url).searchParams.get("convId")

  // Navigate directly back with the convId
  await page.goto(`/chat?convId=${convId}`)
  // Should still have the convId in URL
  await expect(page).toHaveURL(/\/chat\?convId=/)
})

test("cancellazione conversazione dalla sidebar la rimuove", async ({ page }) => {
  const email = `delete-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`

  await page.goto("/auth/register")
  await page.fill("input#name", "Delete Test")
  await page.fill("input#email", email)
  await page.fill("input[id='password']", "password123")
  await page.fill("#confirmPassword", "password123")
  await page.click("button[type=submit]")
  await page.waitForURL(/\/chat/, { timeout: 15000 })

  // Wait for conversation to appear
  await expect(page.getByText("Conversazione")).toBeVisible({ timeout: 10000 })

  // Click delete button (it has aria-label "Elimina conversazione")
  const deleteButton = page.locator('button[aria-label="Elimina conversazione"]')
  await expect(deleteButton).toBeVisible()
  await deleteButton.click()

  // Conversation should be removed — "Nessuna conversazione" should appear
  await expect(page.getByText("Nessuna conversazione")).toBeVisible({ timeout: 10000 })
})
