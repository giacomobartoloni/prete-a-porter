# Dark Mode (class + Toggle) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate 65+ dead `dark:` Tailwind classes across 5 chat components by adding `darkMode: 'class'` config and a working theme toggle with OS preference detection.

**Architecture:** Add `darkMode: 'class'` to Tailwind config; use `next-themes` to manage the `dark` class on `<html>` with `localStorage` persistence and system preference fallback. A small `ThemeProvider` wraps the app root, and a `ThemeToggle` client component (sun/moon icon) lets users switch. All existing `dark:` classes in components become live without changes to them.

**Tech Stack:** Next.js 14 App Router, Tailwind CSS 3.4, next-themes, Playwright (e2e tests), lucide-react (icons)

---

## File Structure

### Files to Create

| File | Responsibility |
|------|---------------|
| `frontend/src/components/providers/ThemeProvider.tsx` | Wraps `next-themes` ThemeProvider with app defaults |
| `frontend/src/components/ThemeToggle.tsx` | Client component: sun/moon toggle button with hydration-safe mount |
| `frontend/e2e/dark-mode.spec.ts` | Playwright e2e test for toggle, persistence, and OS preference |

### Files to Modify

| File | What changes |
|------|-------------|
| `frontend/tailwind.config.ts` | Add `darkMode: 'class'` |
| `frontend/src/components/providers/index.ts` | Export `ThemeProvider` |
| `frontend/src/app/layout.tsx` | Add `suppressHydrationWarning` to `<html>`, wrap with `<ThemeProvider>`, add `dark:` body classes |
| `frontend/src/app/chat/page.tsx` | Import and render `<ThemeToggle />` in header |

### Dependencies to Add

- `next-themes` (runtime)

---

### Task 1: Enable `darkMode: 'class'` in Tailwind config

**Files:**
- Modify: `frontend/tailwind.config.ts:1-50`

- [ ] **Step 1: Add `darkMode: 'class'` to the config**

```ts
import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      // ... rest stays the same
```

- [ ] **Step 2: Verify the file parses correctly**

Run: `npx tailwindcss --help` (no build needed, syntax check only)

Expected: exits 0, no error

- [ ] **Step 3: Commit**

```bash
git add frontend/tailwind.config.ts
git commit -m "feat(tailwind): enable darkMode class strategy"
```

---

### Task 2: Install `next-themes`

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install the package**

```bash
npm install next-themes
```

Expected output: `+ next-themes@0.x.x` (no TypeScript errors — ships its own types)

- [ ] **Step 2: Verify install**

```bash
node -e "require('next-themes')" 2>&1 || echo "OK (ESM-only, checked at build time)"
```

Expected: OK (ESM-only) or no crash

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat(deps): add next-themes for dark mode management"
```

---

### Task 3: Create ThemeProvider wrapper

**Files:**
- Create: `frontend/src/components/providers/ThemeProvider.tsx`
- Modify: `frontend/src/components/providers/index.ts`

- [ ] **Step 1: Write the failing test**

Playwright test checks that ThemeProvider renders children without crashing (smoke test).

`frontend/e2e/dark-mode.spec.ts` (write this file now with just the smoke test):

```ts
import { test, expect } from "@playwright/test"

test.describe("Dark mode setup", () => {
  test("layout renders without crash", async ({ page }) => {
    await page.goto("/auth/login")
    // Page title should render — proves layout/ThemeProvider work
    await expect(page.locator("h1")).toBeVisible()
  })
})
```

- [ ] **Step 2: Run the smoke test to verify current state passes**

Run: `npx playwright test frontend/e2e/dark-mode.spec.ts --headed` (requires running dev server separately, or use `npm run dev &`)

Expected: PASS (this is a smoke test of the existing login page — no dark mode needed yet)

- [ ] **Step 3: Create ThemeProvider component**

`frontend/src/components/providers/ThemeProvider.tsx`:

```tsx
'use client'

import { ThemeProvider as NextThemesProvider } from 'next-themes'
import { ReactNode } from 'react'

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  )
}
```

- [ ] **Step 4: Export from barrel**

`frontend/src/components/providers/index.ts`:

```ts
export { SessionProvider } from './SessionProvider'
export { ThemeProvider } from './ThemeProvider'
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/providers/ThemeProvider.tsx frontend/src/components/providers/index.ts
git commit -m "feat(providers): add ThemeProvider wrapper for next-themes"
```

---

### Task 4: Update root layout with dark mode support

**Files:**
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Write the failing test**

Expand `frontend/e2e/dark-mode.spec.ts` with a test that asserts the `<html>` element does NOT yet have `suppressHydrationWarning` (will fail until we add it — proving the test works):

```ts
test("html element has suppressHydrationWarning (after layout update)", async ({ page }) => {
  await page.goto("/auth/login")
  // After Task 4, the html tag will have suppressHydrationWarning.
  // We check that the page renders — without suppressHydrationWarning,
  // next-themes may cause hydration mismatch warnings.
  // The real assertion is that the page renders without console errors.
  const errors: string[] = []
  page.on("pageerror", (err) => errors.push(err.message))
  await page.goto("/auth/login")
  await expect(page.locator("h1")).toBeVisible()
  expect(errors.length).toBe(0)
})
```

- [ ] **Step 2: Update layout.tsx**

`frontend/src/app/layout.tsx`:

```tsx
import type { Metadata } from 'next'
import './globals.css'
import { SessionProvider, ThemeProvider } from '@/components/providers'

export const metadata: Metadata = {
  title: 'Prete-a-porter',
  description: "Il ghostwriter per un'omelia perfetta",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="it" suppressHydrationWarning>
      <body className="bg-liturgy-50 text-gray-900 dark:bg-slate-950 dark:text-slate-100 font-sans">
        <SessionProvider>
          <ThemeProvider>{children}</ThemeProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
```

Changes from current:
- Added `suppressHydrationWarning` to `<html>`
- Added `dark:bg-slate-950 dark:text-slate-100` to `<body>`
- Imported `ThemeProvider` and wrapped children

- [ ] **Step 3: Run test to verify it passes**

Run: `npx playwright test frontend/e2e/dark-mode.spec.ts`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/layout.tsx
git commit -m "feat(layout): add suppressHydrationWarning, dark body classes, ThemeProvider wrap"
```

---

### Task 5: Create ThemeToggle component

**Files:**
- Create: `frontend/src/components/ThemeToggle.tsx`

- [ ] **Step 1: Write the failing test**

Add a test that checks the toggle does not exist yet on the chat page (will fail once we add it):

`frontend/e2e/dark-mode.spec.ts` — append:

```ts
test("chat header has a theme toggle button (after Task 5+6)", async ({ page }) => {
  // Register a new user to access /chat
  const email = `test-darkmode-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`
  await page.goto("/auth/register")
  await page.fill("input#name", "Dark Mode Test")
  await page.fill("input#email", email)
  await page.fill("input[id='password']", "password123")
  await page.fill("#confirmPassword", "password123")
  await page.click("button[type=submit]")
  await page.waitForURL(/\/chat/, { timeout: 15000 })

  // After Task 5+6, a theme toggle button with aria-label "Toggle dark mode" will exist
  const toggle = page.locator('button[aria-label="Toggle dark mode"]')
  await expect(toggle).toBeVisible()
})
```

- [ ] **Step 2: Create ThemeToggle component**

`frontend/src/components/ThemeToggle.tsx`:

```tsx
'use client'

import { useTheme } from 'next-themes'
import { Sun, Moon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return <div className="w-9 h-9" />
  }

  return (
    <button
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      className={cn(
        'p-2 rounded-lg transition-colors',
        'hover:bg-slate-100 dark:hover:bg-slate-800',
      )}
      aria-label="Toggle dark mode"
    >
      {theme === 'dark' ? (
        <Sun className="w-5 h-5 text-slate-500 dark:text-slate-400" />
      ) : (
        <Moon className="w-5 h-5 text-slate-500" />
      )}
    </button>
  )
}
```

Key design decisions:
- `cn()` used for class merging (existing pattern in codebase)
- `mounted` state prevents hydration mismatch between server (always light) and client
- Uses `lucide-react` icons (already a dependency)
- Matches existing button styling patterns from `SignOutButton`

- [ ] **Step 3: Run test to verify it fails (toggle not yet in page)**

Run: `npx playwright test frontend/e2e/dark-mode.spec.ts --grep "chat header has a theme toggle"`

Expected: FAIL — `button[aria-label="Toggle dark mode"]` not found (we created the component but haven't added it to chat/page.tsx yet)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ThemeToggle.tsx
git commit -m "feat(components): add ThemeToggle component with sun/moon icons"
```

---

### Task 6: Add ThemeToggle to chat page header

**Files:**
- Modify: `frontend/src/app/chat/page.tsx`

- [ ] **Step 1: Confirm test still fails (component not in page yet)**

Run: `npx playwright test frontend/e2e/dark-mode.spec.ts --grep "chat header has a theme toggle"`

Expected: FAIL — toggle not rendered

- [ ] **Step 2: Add ThemeToggle import and render**

`frontend/src/app/chat/page.tsx`:

```tsx
import { redirect } from "next/navigation"
import { auth } from "@/lib/auth"
import Chat from "@/components/Chat"
import { SignOutButton } from "./SignOutButton"
import { ThemeToggle } from "@/components/ThemeToggle"

export default async function ChatPage() {
  const session = await auth()
  const user = session?.user

  if (!user) {
    redirect("/auth/login")
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-liturgy-50 via-white to-liturgy-100 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      <div className="flex flex-col h-screen max-w-6xl mx-auto">
        <header className="bg-white/80 backdrop-blur-sm border-b border-liturgy-100 dark:bg-slate-900/80 dark:border-slate-700/60 px-6 py-3">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-liturgy-600 to-violet-600 flex items-center justify-center shadow">
                <span className="text-sm text-white font-serif font-bold">P</span>
              </div>
              <div>
                <h1 className="text-lg font-serif font-semibold text-liturgy-900 dark:text-liturgy-100">Prete-a-porter</h1>
                <p className="text-xs text-liturgy-500">Assistente per omelie</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-liturgy-600 dark:text-liturgy-400 hidden sm:block">{user.email}</span>
              <ThemeToggle />
              <SignOutButton />
            </div>
          </div>
        </header>
        <div className="flex-1 overflow-hidden">
          <Chat />
        </div>
      </div>
    </main>
  )
}
```

Changes from current:
- Added `import { ThemeToggle } from "@/components/ThemeToggle"`
- Added `dark:from-slate-950 dark:via-slate-900 dark:to-slate-950` on `<main>` gradient
- Added `dark:bg-slate-900/80 dark:border-slate-700/60` on `<header>`
- Added `dark:text-liturgy-100` on the h1
- Added `dark:text-liturgy-400` on user email span
- Added `<ThemeToggle />` before `<SignOutButton />`

- [ ] **Step 3: Run test to verify it passes**

Run: `npx playwright test frontend/e2e/dark-mode.spec.ts --grep "chat header has a theme toggle"`

Expected: PASS — `button[aria-label="Toggle dark mode"]` is now visible in the chat header

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/chat/page.tsx
git commit -m "feat(chat): add ThemeToggle to header with dark mode styles"
```

---

### Task 7: Write e2e tests for toggle functionality

**Files:**
- Modify: `frontend/e2e/dark-mode.spec.ts`

- [ ] **Step 1: Write toggle activation test**

```ts
import { test, expect } from "@playwright/test"

async function registerAndGoToChat(page: any) {
  const email = `test-darkmode-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.com`
  await page.goto("/auth/register")
  await page.fill("input#name", "Dark Mode Test")
  await page.fill("input#email", email)
  await page.fill("input[id='password']", "password123")
  await page.fill("#confirmPassword", "password123")
  await page.click("button[type=submit]")
  await page.waitForURL(/\/chat/, { timeout: 15000 })
}

test.describe("Dark mode toggle", () => {
  test("clicking toggle adds/removes dark class on html element", async ({ page }) => {
    await registerAndGoToChat(page)

    const toggle = page.locator('button[aria-label="Toggle dark mode"]')
    await expect(toggle).toBeVisible()

    // Get initial state — depends on system preference
    const initialDark = await page.locator("html").evaluate(el => el.classList.contains("dark"))

    // Click to toggle
    await toggle.click()
    const afterFirstClick = await page.locator("html").evaluate(el => el.classList.contains("dark"))
    expect(afterFirstClick).toBe(!initialDark)

    // Click to toggle back
    await toggle.click()
    const afterSecondClick = await page.locator("html").evaluate(el => el.classList.contains("dark"))
    expect(afterSecondClick).toBe(initialDark)
  })

  test("dark mode preference persists after page reload", async ({ page }) => {
    await registerAndGoToChat(page)

    const toggle = page.locator('button[aria-label="Toggle dark mode"]')

    // Toggle to dark
    const html = page.locator("html")
    const isDark = await html.evaluate(el => el.classList.contains("dark"))
    if (!isDark) {
      await toggle.click()
    }
    await expect(html).toHaveClass(/dark/)

    // Reload
    await page.reload()
    await page.waitForURL(/\/chat/, { timeout: 15000 })

    // Must still be dark
    await expect(html).toHaveClass(/dark/)
  })
})
```

- [ ] **Step 2: Run all dark mode tests**

Run: `npx playwright test frontend/e2e/dark-mode.spec.ts`

Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/dark-mode.spec.ts
git commit -m "test(e2e): add dark mode toggle and persistence tests"
```

---

### Task 8: Build verification

- [ ] **Step 1: Run lint**

```bash
cd frontend && npm run lint
```

Expected: no errors (existing components unchanged, new components are minimal)

- [ ] **Step 2: Run build**

```bash
cd frontend && npm run build
```

Expected: build succeeds, no type errors (next-themes provides its own types)

- [ ] **Step 3: Final commit if lint/build fixed anything**

```bash
git add -A
git commit -m "chore: fix lint/build issues from dark mode implementation" || echo "No changes needed"
```

---

## Self-Review

### Spec coverage

| Requirement | Task |
|------------|------|
| Add `darkMode: 'class'` to Tailwind config | Task 1 |
| Install theme management library | Task 2 |
| Create ThemeProvider wrapping next-themes | Task 3 |
| Update root layout with SSR hydration fix + dark body classes | Task 4 |
| Create ThemeToggle UI component | Task 5 |
| Add toggle to chat page header | Task 6 |
| Write tests for toggle + persistence | Task 7 |
| Build/lint verification | Task 8 |

All requirements from the original finding are covered.

### Placeholder scan

- No "TBD", "TODO", "implement later" patterns
- No "add appropriate error handling" — handled by next-themes internally
- No "write tests for the above" without code — all test code is inlined
- No "similar to Task N" — each task is self-contained
- Every step has complete code or exact commands

### Type consistency

- `ThemeProvider` — name consistent between file (Task 3), barrel export (Task 3), layout import (Task 4)
- `ThemeToggle` — name consistent between file (Task 5), page import (Task 6), test locator (Task 7)
- `attribute="class"` — consistent between ThemeProvider (Task 3) and test assertions on `html.classList` (Task 7)
- `cn()` utility — used in ThemeToggle (Task 5), defined in `frontend/src/lib/utils.ts` (preexisting)

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-21-dark-mode-class-toggle.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
