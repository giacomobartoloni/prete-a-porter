# Sidebar Refactoring Design

## Overview

Remove the top navigation bar from the chat page and move its contents (logo, user email, theme toggle, sign-out button) into a collapsible left sidebar following the Resend design system.

## Current Layout

```
main.min-h-screen
  div.flex.flex-col.h-screen.max-w-6xl.mx-auto
    header              ← 56px top bar with logo, title, email, toggle, logout
    div.flex-1          ← Chat component
```

## Target Layout

```
main.flex.h-screen.bg-bg-canvas
  Sidebar               ← collapsible, w-[280px] ↔ w-[48px]
  div.flex-1.flex.flex-col.min-w-0
    Chat                 ← same component, full remaining width
```

## Sidebar Component

**File**: `frontend/src/components/Sidebar.tsx`
**Type**: Client component (`"use client"`)

### Internal Layout

```
┌──────────────────────┐  ← w-[280px] expanded / w-[48px] collapsed
│ [logo]          [☰]  │  ← top: 56px, flex items-center px-3
│                       │
│                       │  ← flex-1 (spazio centrale, vuoto)
│                       │
│ ───────────────────── │  ← border-t border-border
│ [email]               │  ← bottom: p-3 flex flex-col gap-2
│ [☾ theme]  [logout]  │
└──────────────────────┘
```

### States

| State | Width | Logo | Title | Toggle | Email | Theme | Logout |
|-------|-------|------|-------|--------|-------|-------|--------|
| Expanded | w-[280px] | w-10 h-10 + label | visible | PanelLeftClose | visible | icon + "Tema" | icon + "Esci" |
| Collapsed | w-[48px] | w-8 h-8 only | hidden | PanelLeft | hidden | icon only | icon only |

### Transition

- `transition-all duration-300` on sidebar width
- Inner elements use conditional rendering or `overflow-hidden` for smooth animation
- No transition on the chat container — it reflows instantly

### Collapse Mechanism

- Pulsante all'interno della sidebar, all'altezza del logo, lato destro
- Icona: `PanelLeftClose` (lucide-react) quando espansa, `PanelLeft` quando collassata
- Stato iniziale: espansa

## Modified Files

### `frontend/src/app/chat/page.tsx`
- Remove `<header>` block (logo, title, email, ThemeToggle, SignOutButton)
- Remove `max-w-6xl mx-auto` container
- Import `<Sidebar />` component
- Pass `user` session to Sidebar as prop
- Layout: `main className="flex h-screen bg-bg-canvas"` → `Sidebar` + `div.flex-1.min-w-0`

### `frontend/src/components/Chat.tsx`
- No structural changes
- Chat area naturally fills the remaining space

## Component Migration

| Element | Current Location | New Location |
|---------|-----------------|--------------|
| Logo (Image) | `page.tsx` header | `Sidebar.tsx` top |
| Titolo "Prete-a-porter" | `page.tsx` header | `Sidebar.tsx` top, expanded only |
| Subtitle "Assistente per omelie" | `page.tsx` header | **removed** (sidebar too narrow) |
| User email | `page.tsx` header | `Sidebar.tsx` bottom |
| ThemeToggle | `page.tsx` header | `Sidebar.tsx` bottom |
| SignOutButton | `page.tsx` header | `Sidebar.tsx` bottom |
| Toggle button | — | `Sidebar.tsx` top-right |

## Session Data Flow

- `page.tsx` calls `auth()` server-side and gets `user`
- Sidebar receives `user` as a prop (serializable, no session context on client)
- SignOutButton uses `next-auth/react` `signOut()` client-side

## Mobile Behavior

- On `<768px`: sidebar becomes a fixed overlay (position fixed, z-index above chat)
- Backdrop: semi-transparent dark overlay (`bg-black/50`)
- Tap backdrop or close button to dismiss
- State persists via local `useState` within session

## Edge Cases

- **Loading state**: sidebar renders immediately with fixed widths; no async dependency
- **Error state**: if user session missing, page redirects before sidebar mounts
- **Empty email**: show fallback "Utente" label if email is null/undefined
- **Resize**: on resize to mobile while sidebar open, switch to overlay mode
- **Focus trap**: minimal — close button in overlay mode dismisses on Escape

## Future-Proofing

- Central `flex-1` space in sidebar left empty for future navigation links
- Bottom section pattern allows adding more user menu items
- Sidebar is a standalone component, easy to reuse in other authenticated pages
