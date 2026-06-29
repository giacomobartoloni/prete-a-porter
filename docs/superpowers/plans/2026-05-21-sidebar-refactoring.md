# Sidebar Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace top navbar with a collapsible left sidebar containing logo, user email, theme toggle, and sign-out button.

**Architecture:** A new `Sidebar` client component with `useState` for expand/collapse, rendered inside the flex layout on desktop and as a fixed overlay on mobile. Two existing components (`ThemeToggle`, `SignOutButton`) gain a `showLabel` prop. The chat page layout is simplified to a horizontal flex container.

**Tech Stack:** Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS v4, lucide-react, next-themes, next-auth/react

---

### File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/components/ThemeToggle.tsx` | Modify | Add `showLabel` prop |
| `frontend/src/app/chat/SignOutButton.tsx` | Modify | Add `showLabel` prop |
| `frontend/src/components/Sidebar.tsx` | **Create** | Collapsible sidebar |
| `frontend/src/app/chat/page.tsx` | Modify | Remove header, use Sidebar + flex layout |

---

### Task 1: Add `showLabel` prop to ThemeToggle

**Files:**
- Modify: `frontend/src/components/ThemeToggle.tsx`

- [ ] **Step 1: Add `showLabel` prop and render label when true**

Replace the existing `ThemeToggle` function with one that accepts an optional `showLabel` prop and renders "Tema" next to the icon:

```tsx
'use client'

import { useTheme } from 'next-themes'
import { Sun, Moon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

interface ThemeToggleProps {
  showLabel?: boolean
}

export function ThemeToggle({ showLabel = false }: ThemeToggleProps) {
  const { theme, resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return <div className="w-9 h-9" />
  }

  const isDark = resolvedTheme === 'dark'

  return (
    <button
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      className={cn(
        'flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors',
        'hover:bg-bg-overlay text-text-tertiary w-full',
      )}
      aria-label="Toggle dark mode"
    >
      {isDark ? (
        <Sun className="w-5 h-5 shrink-0" />
      ) : (
        <Moon className="w-5 h-5 shrink-0" />
      )}
      {showLabel && (
        <span className="text-sm whitespace-nowrap">Tema</span>
      )}
    </button>
  )
}
```

- [ ] **Step 2: Verify build compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: no errors (or only errors unrelated to this change)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ThemeToggle.tsx
git commit -m "feat: add showLabel prop to ThemeToggle"
```

---

### Task 2: Add `showLabel` prop to SignOutButton

**Files:**
- Modify: `frontend/src/app/chat/SignOutButton.tsx`

- [ ] **Step 1: Add `showLabel` prop**

```tsx
"use client"

import { signOut } from "next-auth/react"
import { LogOut } from "lucide-react"

interface SignOutButtonProps {
  showLabel?: boolean
}

export function SignOutButton({ showLabel = false }: SignOutButtonProps) {
  return (
    <button
      onClick={() => signOut({ redirectTo: "/auth/login" })}
      className="flex items-center gap-2 px-2 py-1.5 text-sm font-medium text-text-tertiary hover:text-danger bg-transparent rounded-lg hover:bg-danger/10 transition-all w-full"
    >
      <LogOut size={16} className="shrink-0" />
      {showLabel && (
        <span className="whitespace-nowrap">Esci</span>
      )}
    </button>
  )
}
```

The outer button removes the `bg-bg-card border border-border` since the sidebar bottom section provides its own background. The `rounded-xl` becomes `rounded-lg` to match the ThemeToggle. `w-full` makes it fill the sidebar width.

- [ ] **Step 2: Verify build compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/chat/SignOutButton.tsx
git commit -m "feat: add showLabel prop to SignOutButton"
```

---

### Task 3: Create Sidebar component

**Files:**
- Create: `frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Write the Sidebar component**

```tsx
"use client"

import { useState } from "react"
import Image from "next/image"
import { PanelLeftClose, PanelLeft } from "lucide-react"
import { ThemeToggle } from "@/components/ThemeToggle"
import { SignOutButton } from "@/app/chat/SignOutButton"
import { cn } from "@/lib/utils"

interface SidebarProps {
  email: string | null | undefined
}

export function Sidebar({ email }: SidebarProps) {
  const [expanded, setExpanded] = useState(true)

  return (
    <>
      {/* Backdrop (mobile only) */}
      {expanded && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setExpanded(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "flex flex-col h-screen border-r border-border bg-bg-raised/80 backdrop-blur-sm transition-all duration-300 overflow-hidden shrink-0",
          // Desktop: part of flex flow
          "md:relative",
          // Mobile: fixed overlay above chat
          "fixed inset-y-0 left-0 z-50",
          // Visibility: desktop always visible, mobile toggles via translate
          expanded ? "translate-x-0" : "-translate-x-full md:translate-x-0",
          // Width
          expanded ? "w-[280px]" : "md:w-[48px]",
        )}
      >
        {/* Top section: logo + toggle */}
        <div className="flex items-center justify-between h-14 px-3 shrink-0">
          <div className="flex items-center gap-3 overflow-hidden">
            <Image
              src="/logo.png"
              alt="Prete-a-porter"
              width={512}
              height={512}
              className={cn("logo-glow shrink-0", expanded ? "w-10 h-10" : "w-8 h-8")}
            />
            {expanded && (
              <span className="text-lg font-serif font-semibold text-text-primary whitespace-nowrap">
                Prete-a-porter
              </span>
            )}
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="shrink-0 p-1.5 rounded-lg hover:bg-bg-overlay transition-colors text-text-tertiary"
            aria-label={expanded ? "Collassa sidebar" : "Espandi sidebar"}
          >
            {expanded ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
          </button>
        </div>

        {/* Central empty space (future nav) */}
        <div className="flex-1" />

        {/* Divider */}
        <div className="border-t border-border" />

        {/* Bottom section: email, theme, logout */}
        <div className="p-3 flex flex-col gap-1">
          {expanded && email && (
            <span className="text-sm text-text-secondary truncate px-2 pb-1">{email}</span>
          )}
          {expanded && !email && (
            <span className="text-sm text-text-secondary px-2 pb-1">Utente</span>
          )}
          <ThemeToggle showLabel={expanded} />
          <SignOutButton showLabel={expanded} />
        </div>
      </aside>
    </>
  )
}
```

- [ ] **Step 2: Verify build compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "feat: add collapsible Sidebar component"
```

---

### Task 4: Update ChatPage layout

**Files:**
- Modify: `frontend/src/app/chat/page.tsx`

- [ ] **Step 1: Replace header + max-w-6xl with Sidebar + flex layout**

```tsx
import { redirect } from "next/navigation"
import { auth } from "@/lib/auth"
import Chat from "@/components/Chat"
import { Sidebar } from "@/components/Sidebar"

export default async function ChatPage() {
  const session = await auth()
  const user = session?.user

  if (!user) {
    redirect("/auth/login")
  }

  return (
    <main className="flex h-screen bg-bg-canvas">
      <Sidebar email={user.email ?? null} />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Chat />
      </div>
    </main>
  )
}
```

Note: `Remove imports: Image, SignOutButton, ThemeToggle`
Note: `user.email ?? null` ensures we pass null instead of undefined.

- [ ] **Step 2: Verify build compiles**

Run: `cd frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: no errors

- [ ] **Step 3: Full build verification**

Run: `cd frontend && npm run build 2>&1 | tail -15`
Expected: build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/chat/page.tsx
git commit -m "refactor: replace top navbar with collapsible sidebar"
```

---

### Task 5: Self-review checklist

- [ ] All unused imports removed from `page.tsx`
- [ ] `SignOutButton` works without border/background (it's now inside the sidebar)
- [ ] `ThemeToggle` uses `w-full` to fill sidebar width
- [ ] Sidebar backdrop has `z-40`, sidebar has `z-50`, content has no z-index clash
- [ ] `min-w-0` on content div prevents flex overflow
- [ ] Sidebar `shrink-0` prevents it from being compressed by flex
- [ ] On mobile (<768px): sidebar overlays with backdrop; tap backdrop closes
- [ ] On desktop (>=768px): sidebar is part of layout, transitions 280px ↔ 48px
- [ ] When collapsed on desktop: logo is `w-8 h-8`, no title, icons-only bottom section
- [ ] Toggle icon: `PanelLeftClose` when expanded, `PanelLeft` when collapsed
