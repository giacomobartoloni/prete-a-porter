# Resend Design System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all dark mode styling with the Resend obsidian-black design system, upgrade Tailwind v3→v4, and share structural tokens (typography, spacing, radii, shadows) across both themes.

**Architecture:** Upgrade Tailwind from v3 to v4 (CSS-first config), define all design tokens as CSS custom properties in `globals.css` using `@theme`, use `:root`/`.dark` CSS variable switching so components reference single semantic class names instead of `dark:` variants. Remove `tailwind.config.ts`. Update ~18 component/ page files to use the new token system. Add dark mode support to 6 components that currently have none.

**Tech Stack:** Next.js 14.1, React 18, Tailwind CSS v4, `next-themes` (class-based dark mode), `@tailwindcss/typography` v0.6

---

### File Inventory

| # | File | Action | Why |
|---|------|--------|-----|
| 1 | `frontend/package.json` | Modify | Update tailwindcss, add @tailwindcss/postcss, update @tailwindcss/typography |
| 2 | `frontend/postcss.config.js` | Modify | Replace tailwindcss plugin with @tailwindcss/postcss |
| 3 | `frontend/tailwind.config.ts` | Delete | Replaced by Tailwind v4 CSS-first @theme |
| 4 | `frontend/src/app/globals.css` | Rewrite | @import tailwindcss + @theme + :root/.dark tokens + @custom-variant dark |
| 5 | `frontend/src/app/layout.tsx` | Modify | Update body classes |
| 6 | `frontend/src/app/chat/page.tsx` | Modify | Update dark: classes to new tokens |
| 7 | `frontend/src/app/auth/layout.tsx` | Modify | Add dark mode support |
| 8 | `frontend/src/app/auth/login/page.tsx` | Modify | Add dark mode support |
| 9 | `frontend/src/app/auth/register/page.tsx` | Modify | Add dark mode support |
| 10 | `frontend/src/app/chat/SignOutButton.tsx` | Modify | Add dark mode support |
| 11 | `frontend/src/components/Chat.tsx` | Modify | Update dark: and light classes to new tokens, add dark mode |
| 12 | `frontend/src/components/ThemeToggle.tsx` | Modify | Update to new tokens |
| 13 | `frontend/src/components/chat/ChatContainer.tsx` | Modify | Update to new tokens |
| 14 | `frontend/src/components/chat/MessageBubble.tsx` | Modify | Update to new tokens |
| 15 | `frontend/src/components/chat/MessageList.tsx` | Modify | Update to new tokens |
| 16 | `frontend/src/components/chat/InputArea.tsx` | Modify | Update to new tokens |
| 17 | `frontend/src/components/chat/ToolCall.tsx` | Modify | Update to new tokens |
| 18 | `frontend/src/components/auth/LoginForm.tsx` | Modify | Add dark mode support |
| 19 | `frontend/src/components/auth/RegisterForm.tsx` | Modify | Add dark mode support |
| 20 | `frontend/src/components/messages/LiturgicalCard.tsx` | Modify | Add dark mode support |
| 21 | `frontend/src/components/messages/HomilyDisplay.tsx` | Modify | Add dark mode support |
| 22 | `frontend/src/components/messages/PreferencePicker.tsx` | Modify | Add dark mode support |
| 23 | `frontend/src/components/messages/MessageRenderer.tsx` | Modify | Add dark mode support |
| 24 | `frontend/e2e/dark-mode.spec.ts` | Verify | Confirm tests still pass |

---

### Task 1: Upgrade Dependencies to Tailwind v4

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/postcss.config.js`
- Delete: `frontend/tailwind.config.ts`

- [ ] **Step 1: Update package.json**

Replace:
```json
"@tailwindcss/typography": "^0.5.19",
"autoprefixer": "^10.0.1",
"tailwindcss": "^3.4.0",
```

With:
```json
"@tailwindcss/typography": "^0.6.0",
"@tailwindcss/postcss": "^4.1.0",
"tailwindcss": "^4.1.0",
```

- [ ] **Step 2: Update postcss.config.js**

Replace entire file:
```js
const config = {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}
export default config
```

- [ ] **Step 3: Delete tailwind.config.ts**

Run: `rm frontend/tailwind.config.ts`

- [ ] **Step 4: Install new deps**

Run: `cd frontend && npm install`

Expected: installs tailwindcss v4, @tailwindcss/postcss, @tailwindcss/typography v0.6

- [ ] **Step 5: Commit**

```
git add frontend/package.json frontend/package-lock.json frontend/postcss.config.js
git rm frontend/tailwind.config.ts
git commit -m "build: upgrade tailwindcss v3 to v4"
```

---

### Task 2: Define Design Tokens in globals.css

**Files:**
- Rewrite: `frontend/src/app/globals.css`

This is the largest single change. All design tokens live here. No more `tailwind.config.ts`.

- [ ] **Step 1: Write the new globals.css**

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
@import "tailwindcss";
@plugin "@tailwindcss/typography";

@custom-variant dark (&:where(.dark, .dark *));

@theme {
  /* Typography — Font Families */
  --font-inter: 'Inter', ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  --font-serif: Georgia, Cambria, "Times New Roman", Times, serif;

  /* Type Scale */
  --text-caption: 12px;
  --text-caption--line-height: 1.33;
  --text-body-sm: 14px;
  --text-body-sm--line-height: 1.43;
  --text-body: 16px;
  --text-body--line-height: 1.5;
  --text-subheading: 18px;
  --text-subheading--line-height: 1.6;
  --text-heading-sm: 20px;
  --text-heading-sm--line-height: 1.3;
  --text-heading: 24px;
  --text-heading--line-height: 1.33;

  /* Font Weights */
  --font-weight-regular: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;

  /* Spacing (4px base) */
  --spacing-4: 4px;
  --spacing-8: 8px;
  --spacing-12: 12px;
  --spacing-16: 16px;
  --spacing-20: 20px;
  --spacing-24: 24px;
  --spacing-28: 28px;
  --spacing-32: 32px;
  --spacing-40: 40px;
  --spacing-48: 48px;
  --spacing-64: 64px;
  --spacing-80: 80px;
  --spacing-96: 96px;
  --spacing-104: 104px;
  --spacing-144: 144px;

  /* Border Radius */
  --radius-md: 6px;
  --radius-lg: 10px;
  --radius-2xl: 16px;
  --radius-3xl: 24px;

  /* Shadows */
  --shadow-subtle: rgba(176, 199, 217, 0.145) 0px 0px 0px 1px;
  --shadow-subtle-2: rgb(0, 0, 0) 0px 0px 0px 8px;
  --shadow-subtle-3: rgba(0, 0, 0, 0.1) 0px 1px 3px 0px, rgba(0, 0, 0, 0.1) 0px 1px 2px -1px;

  /* Semantic Color Tokens (point to CSS variables) */
  --color-bg-canvas: var(--bg-canvas);
  --color-bg-raised: var(--bg-raised);
  --color-bg-card: var(--bg-card);
  --color-bg-overlay: var(--bg-overlay);
  --color-text-primary: var(--text-primary);
  --color-text-secondary: var(--text-secondary);
  --color-text-tertiary: var(--text-tertiary);
  --color-text-muted: var(--text-muted);
  --color-border: var(--border);
  --color-border-subtle: var(--border-subtle);
  --color-accent: var(--accent);
  --color-accent-violet: var(--accent-violet);
  --color-accent-blue: var(--accent-blue);
  --color-success: var(--success);
  --color-danger: var(--danger);
  --color-warning: var(--warning);
  --color-info: var(--info);

  /* Legacy liturgy palette — kept for backward compat of light mode */
  --color-liturgy-50: #fdf8f0;
  --color-liturgy-100: #f9eddb;
  --color-liturgy-200: #f2d8b0;
  --color-liturgy-300: #e9bd7c;
  --color-liturgy-400: #e0a34e;
  --color-liturgy-500: #d4892e;
  --color-liturgy-600: #c06e22;
  --color-liturgy-700: #a0531e;
  --color-liturgy-800: #82431f;
  --color-liturgy-900: #6a381c;
  --color-liturgy-950: #3a1b0c;

  --color-violet-50: #f5f0ff;
  --color-violet-100: #ede1ff;
  --color-violet-200: #dcc3ff;
  --color-violet-300: #c29bff;
  --color-violet-400: #a568ff;
  --color-violet-500: #8b3aff;
  --color-violet-600: #7c1dff;
  --color-violet-700: #6d0ef7;
  --color-violet-800: #5b0ad0;
  --color-violet-900: #4c0daa;
  --color-violet-950: #2d0674;
}

/* Light mode defaults — warm liturgical palette */
:root {
  --bg-canvas: #fdf8f0;
  --bg-raised: #ffffff;
  --bg-card: #ffffff;
  --bg-overlay: #f9eddb;
  --text-primary: #3a1b0c;
  --text-secondary: #82431f;
  --text-tertiary: #a0531e;
  --text-muted: #d4892e;
  --border: #f2d8b0;
  --border-subtle: #e9bd7c;
  --accent: #7c1dff;
  --accent-violet: #8b3aff;
  --accent-blue: #3b9eff;
  --success: #22c55e;
  --danger: #ef4444;
  --warning: #f59e0b;
  --info: #3b9eff;
}

/* Dark mode — Resend obsidian palette */
.dark {
  --bg-canvas: #000000;
  --bg-raised: #0b0e14;
  --bg-card: #000000;
  --bg-overlay: #1b1b1b;
  --text-primary: #f0f0f0;
  --text-secondary: #a1a4a5;
  --text-tertiary: #6c6c6c;
  --text-muted: #6e727a;
  --border: #292d30;
  --border-subtle: #464a4d;
  --accent: #9281f7;
  --accent-violet: #9281f7;
  --accent-blue: #3b9eff;
  --success: #3ad389;
  --danger: #ff9592;
  --warning: #ffca16;
  --info: #70b8ff;
}

@layer base {
  body {
    margin: 0;
    padding: 0;
    background-color: var(--bg-canvas);
    color: var(--text-primary);
    font-family: var(--font-inter);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  h1, h2, h3, h4 {
    font-family: var(--font-serif);
  }
}
```

> **Key naming convention:** Components now use `bg-bg-canvas`, `text-text-primary`, `border-border`, etc. instead of `bg-liturgy-50`, `dark:bg-slate-950`. The CSS variable switching under `.dark` handles the thematic shift automatically — no need for `dark:` variants for background/text/border colors.

- [ ] **Step 2: Verify build compiles**

Run: `cd frontend && npm run build`
Expected: Build succeeds (may have warnings about unknown utilities if any old class names remain — these are expected and will be fixed in subsequent tasks)

- [ ] **Step 3: Commit**

```
git add frontend/src/app/globals.css
git commit -m "feat: add Resend design tokens as CSS variables in globals.css"
```

---

### Task 3: Update Root Layout

**Files:**
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Update body classes**

Replace:
```tsx
<body className="bg-liturgy-50 text-gray-900 dark:bg-slate-950 dark:text-slate-100 font-sans">
```

With:
```tsx
<body className="font-sans">
```

(The body background/text are now set via CSS variables in `@layer base`.)

- [ ] **Step 2: Commit**

```
git add frontend/src/app/layout.tsx
git commit -m "refactor: remove explicit dark classes from root layout (now handled by CSS vars)"
```

---

### Task 4: Update Chat Page

**Files:**
- Modify: `frontend/src/app/chat/page.tsx`

This file mixes liturgy palette classes with dark classes. Convert to semantic tokens.

- [ ] **Step 1: Replace all Tailwind classes**

Old classes → New classes mapping:

| Old | New |
|-----|-----|
| `bg-gradient-to-br from-liturgy-50 via-white to-liturgy-100 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950` | `bg-bg-canvas` |
| `bg-white/80 backdrop-blur-sm border-b border-liturgy-100 px-6 py-3 dark:bg-slate-900/80 dark:border-slate-700/60` | `bg-bg-raised/80 backdrop-blur-sm border-b border-border px-6 py-3` |
| `bg-gradient-to-br from-liturgy-600 to-violet-600` | `bg-gradient-to-br from-liturgy-600 to-violet-600` (keep liturgy/violet palette for the P icon — brand element) |
| `text-lg font-serif font-semibold text-liturgy-900 dark:text-liturgy-100` | `text-lg font-serif font-semibold text-text-primary` |
| `text-xs text-liturgy-500` | `text-xs text-text-tertiary` |
| `text-sm text-liturgy-600 hidden sm:block dark:text-liturgy-400` | `text-sm text-text-secondary hidden sm:block` |

The full updated return:

```tsx
return (
  <main className="min-h-screen bg-bg-canvas">
    <div className="flex flex-col h-screen max-w-6xl mx-auto">
      <header className="bg-bg-raised/80 backdrop-blur-sm border-b border-border px-6 py-3">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-liturgy-600 to-violet-600 flex items-center justify-center shadow-subtle">
              <span className="text-sm text-white font-serif font-bold">P</span>
            </div>
            <div>
              <h1 className="text-lg font-serif font-semibold text-text-primary">Prete-a-porter</h1>
              <p className="text-xs text-text-tertiary">Assistente per omelie</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-text-secondary hidden sm:block">{user.email}</span>
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
```

- [ ] **Step 2: Commit**

```
git add frontend/src/app/chat/page.tsx
git commit -m "refactor: update chat page to use semantic CSS variable tokens"
```

---

### Task 5: Update ChatContainer, MessageList, MessageBubble, InputArea, ToolCall

**Files:**
- Modify: `frontend/src/components/chat/ChatContainer.tsx`
- Modify: `frontend/src/components/chat/MessageList.tsx`
- Modify: `frontend/src/components/chat/MessageBubble.tsx`
- Modify: `frontend/src/components/chat/InputArea.tsx`
- Modify: `frontend/src/components/chat/ToolCall.tsx`

These are the 5 chat sub-components. Each follows the same pattern: replace `dark:bg-slate-*`, `dark:text-slate-*`, `dark:border-slate-*` with the semantic tokens and remove the `dark:` prefix.

- [ ] **Step 1: Update ChatContainer.tsx**

Replace the entire file content with the same component but using new tokens:

`ChatContainer`:
```tsx
<div className={cn('flex flex-col h-screen max-w-4xl mx-auto bg-bg-canvas', className)}>
```

`ChatHeader`:
```tsx
<header className={cn('bg-bg-raised/80 backdrop-blur-sm border-b border-border px-6 py-4', className)}>
...
<h1 className="text-xl font-semibold text-text-primary">{title}</h1>
...
<span className={cn('text-sm font-medium', isConnected ? 'text-text-secondary' : 'text-danger')}>
```

`ChatFooter`:
```tsx
<footer className={cn('bg-bg-raised/80 backdrop-blur-sm border-t border-border px-6 py-4', className)}>
```

- [ ] **Step 2: Update MessageList.tsx**

Replace all classes:
- `text-slate-400 dark:text-slate-500` → `text-text-tertiary`
- `bg-slate-100 dark:bg-slate-800` → `bg-bg-overlay`
- `bg-white border border-slate-200/60 dark:bg-slate-800 dark:border-slate-700/60` → `bg-bg-card border border-border`
- `text-slate-500 dark:text-slate-400` → `text-text-secondary`

- [ ] **Step 3: Update MessageBubble.tsx**

Replace all classes:
- `text-xs text-slate-400 dark:text-slate-500` → `text-xs text-text-tertiary`
- `bg-white border border-slate-200/60 text-slate-900 dark:bg-slate-800 dark:border-slate-700/60 dark:text-slate-100` → `bg-bg-card border border-border text-text-primary`
- `bg-slate-100 dark:bg-slate-800` → `bg-bg-overlay`
- `text-xs text-slate-600 dark:text-slate-400` → `text-xs text-text-secondary`

- [ ] **Step 4: Update InputArea.tsx**

Replace all classes:
- `bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700` → `bg-bg-card border border-border`
- `text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300` → `text-text-tertiary hover:text-text-secondary`
- `hover:bg-slate-100 dark:hover:bg-slate-700` → `hover:bg-bg-overlay`
- `text-slate-900 dark:text-slate-100` → `text-text-primary`
- `placeholder:text-slate-400 dark:placeholder:text-slate-500` → `placeholder:text-text-tertiary`
- `text-amber-500 dark:text-amber-400` → `text-warning`
- `bg-slate-100 dark:bg-slate-700 text-slate-400 dark:text-slate-500` → `bg-bg-overlay text-text-tertiary`
- `bg-blue-500 text-white hover:bg-blue-600 shadow-sm shadow-blue-500/30` → Keep as accent action button styling
- `text-xs text-slate-400 dark:text-slate-500` → `text-xs text-text-tertiary`
- `bg-slate-100 dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-700` → `bg-bg-overlay rounded border border-border`

For the `CompactInputArea`:
- `bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700` → `bg-bg-overlay border border-border`
- `text-sm text-slate-900 dark:text-slate-100` → `text-sm text-text-primary`
- `placeholder:text-slate-400 dark:placeholder:text-slate-500` → `placeholder:text-text-tertiary`
- `text-slate-400 hover:text-blue-500 hover:bg-slate-100 dark:hover:bg-slate-700` → `text-text-tertiary hover:text-accent-blue hover:bg-bg-overlay`

- [ ] **Step 5: Update ToolCall.tsx**

Replace all classes in the statusConfig and in the render:

Status config colors:
```ts
pending: {
  icon: Clock,
  color: 'text-text-tertiary',
  bg: 'bg-bg-overlay',
  border: 'border-border',
  label: 'In attesa'
},
running: {
  icon: Loader2,
  color: 'text-warning',
  bg: 'bg-bg-overlay',
  border: 'border-border',
  label: 'In esecuzione'
},
success: {
  icon: CheckCircle,
  color: 'text-success',
  bg: 'bg-bg-overlay',
  border: 'border-border',
  label: 'Completato'
},
error: {
  icon: XCircle,
  color: 'text-danger',
  bg: 'bg-bg-overlay',
  border: 'border-border',
  label: 'Errore'
}
```

And replace all other dark/light classes systematically:
- `text-slate-700 dark:text-slate-300` → `text-text-primary`
- `text-slate-500 dark:text-slate-400` → `text-text-secondary`
- `text-slate-400 dark:text-slate-500` → `text-text-tertiary`
- `bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700` → `bg-bg-card border border-border`
- `hover:bg-black/5 dark:hover:bg-white/5` → `hover:bg-bg-overlay`
- `border-slate-200 dark:border-slate-700` → `border-border`
- `bg-rose-50 dark:bg-rose-900/20` → `bg-danger/10`
- `text-rose-600 dark:text-rose-400` → `text-danger`
- `text-rose-700 dark:text-rose-300` → `text-danger`

- [ ] **Step 6: Commit the chat components batch**

```
git add frontend/src/components/chat/
git commit -m "refactor: update chat components to use semantic CSS variable tokens"
```

---

### Task 6: Update ThemeToggle

**Files:**
- Modify: `frontend/src/components/ThemeToggle.tsx`

- [ ] **Step 1: Update classes**

Replace:
```tsx
className={cn(
  'p-2 rounded-lg transition-colors',
  'hover:bg-slate-100 dark:hover:bg-slate-800',
)}
```

With:
```tsx
className={cn(
  'p-2 rounded-lg transition-colors',
  'hover:bg-bg-overlay',
)}
```

And:
```tsx
{isDark ? (
  <Sun className="w-5 h-5 text-text-tertiary" />
) : (
  <Moon className="w-5 h-5 text-text-tertiary" />
)}
```

- [ ] **Step 2: Commit**

```
git add frontend/src/components/ThemeToggle.tsx
git commit -m "refactor: update ThemeToggle to use semantic tokens"
```

---

### Task 7: Update Old Chat Component

**Files:**
- Modify: `frontend/src/components/Chat.tsx`

This is the old inline chat component (still wired in `chat/page.tsx`). It has extensive hardcoded liturgy/warm colors and zero dark mode support via `dark:`.

- [ ] **Step 1: Update classes in the render**

Replace these patterns:

| Old | New |
|-----|-----|
| `bg-gradient-to-br from-liturgy-100 to-liturgy-200` | `bg-bg-overlay` |
| `text-liturgy-600` | `text-accent-violet` |
| `text-xl font-serif font-semibold text-liturgy-800` | `text-xl font-serif font-semibold text-text-primary` |
| `text-liturgy-500 max-w-md text-sm` | `text-text-tertiary max-w-md text-sm` |
| `p-3 rounded-xl border border-liturgy-200 bg-white hover:bg-liturgy-50 hover:border-liturgy-300` | `p-3 rounded-xl border border-border bg-bg-card hover:bg-bg-overlay` |
| `text-sm font-medium text-liturgy-800` | `text-sm font-medium text-text-primary` |
| `text-xs text-liturgy-500 mt-0.5` | `text-xs text-text-tertiary mt-0.5` |
| `bg-gradient-to-br from-liturgy-600 to-violet-600 text-white rounded-2xl rounded-br-md` | `bg-gradient-to-br from-liturgy-600 to-violet-600 text-white rounded-2xl rounded-br-md` (keep user bubble brand gradient) |
| `bg-white border border-liturgy-100 text-gray-800 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm` | `bg-bg-card border border-border text-text-primary rounded-2xl rounded-bl-md px-4 py-3` |
| `text-xs font-medium text-liturgy-600` | `text-xs font-medium text-text-secondary` |
| `bg-gradient-to-br from-liturgy-500 to-violet-500` | keep for the P avatar |
| `bg-white border border-liturgy-100 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm` | `bg-bg-card border border-border rounded-2xl rounded-bl-md px-4 py-3` |
| `bg-liturgy-300`, `bg-liturgy-400`, `bg-liturgy-500` (bouncing dots) | `bg-bg-overlay` for all dots (keep animation) |
| `bg-red-50 border border-red-200 text-red-700` | `bg-danger/10 border border-danger/30 text-danger` |
| `text-red-600 hover:text-red-800` | `text-danger hover:text-danger/80` |
| `bg-white/80 backdrop-blur-sm border-t border-liturgy-100` | `bg-bg-raised/80 backdrop-blur-sm border-t border-border` |
| `bg-white rounded-2xl border border-liturgy-200 px-4 py-2 focus-within:border-liturgy-400 focus-within:ring-2 focus-within:ring-liturgy-100` | `bg-bg-card rounded-2xl border border-border px-4 py-2 focus-within:border-accent-blue focus-within:ring-2 focus-within:ring-accent-blue/20` |
| `placeholder:text-gray-400 text-sm` | `placeholder:text-text-tertiary text-sm text-text-primary` |
| `bg-gradient-to-br from-liturgy-600 to-violet-600 text-white rounded-xl hover:from-liturgy-700 hover:to-violet-700 disabled:from-gray-300 disabled:to-gray-300` | Keep send button gradient-branded in both themes |
| `bg-green-500` / `bg-red-400` | `bg-success` / `bg-danger` |
| `text-xs text-gray-400` | `text-xs text-text-tertiary` |

- [ ] **Step 2: Commit**

```
git add frontend/src/components/Chat.tsx
git commit -m "refactor: update Chat component to use semantic CSS tokens"
```

---

### Task 8: Add Dark Mode to LiturgicalCard, HomilyDisplay, PreferencePicker

**Files:**
- Modify: `frontend/src/components/messages/LiturgicalCard.tsx`
- Modify: `frontend/src/components/messages/HomilyDisplay.tsx`
- Modify: `frontend/src/components/messages/PreferencePicker.tsx`

These three have zero dark mode support. They use hardcoded light colors (`bg-white`, `text-gray-*`, `border-gray-*`).

- [ ] **Step 1: Update LiturgicalCard.tsx**

Replace color classes:

```tsx
// Main card
<div className={`rounded-lg border ${colorClass} p-4 max-w-2xl`}>
```

Change `colorMap` to use semantic tokens instead of bg-* + border-* per color:

```tsx
const colorMap: Record<string, string> = {
  White: 'border-border',
  Green: 'border-success/50',
  Red: 'border-danger/50',
  Purple: 'border-accent-violet/50',
  Violet: 'border-accent-violet/50',
  Pink: 'border-accent-violet/30',
};
```

And add card background class `bg-bg-card`. The overall card becomes:
```tsx
<div className={`rounded-lg border bg-bg-card ${colorClass} p-4 max-w-2xl`}>
```

Replace all other hardcoded colors:
- `text-gray-900` → `text-text-primary`
- `text-gray-600` → `text-text-secondary`
- `text-gray-400` → `text-text-tertiary`
- `border-gray-200` → `border-border`
- `text-gray-500` → `text-text-tertiary`
- `text-gray-700` → `text-text-secondary`
- `text-gray-800 italic` → `text-text-primary italic`
- `text-yellow-50`, `text-yellow-400` etc. (gospel highlight) → Keep as accent but use semantic:
  - `bg-yellow-50` → `bg-warning/10`
  - `border-yellow-400` → `border-warning/50`
  - `text-yellow-700` → `text-warning`
  - `text-yellow-800` → `text-warning`

- [ ] **Step 2: Update HomilyDisplay.tsx**

Replace:
- `bg-white rounded-lg border border-gray-200 p-4` → `bg-bg-card rounded-lg border border-border p-4`
- `text-gray-600` → `text-text-secondary`
- `text-gray-900` → `text-text-primary`
- `text-gray-400` → `text-text-tertiary`
- `border-gray-200` → `border-border`
- `text-gray-500` → `text-text-tertiary`
- `bg-gray-100 text-gray-600` → `bg-bg-overlay text-text-secondary`

Update the `variantStyles`:
```tsx
const variantStyles = {
  intro: {
    bg: 'bg-accent-blue/10',
    border: 'border-l-accent-blue',
    icon: 'text-accent-blue',
  },
  reflection: {
    bg: 'bg-warning/10',
    border: 'border-l-warning',
    icon: 'text-warning',
  },
  application: {
    bg: 'bg-success/10',
    border: 'border-l-success',
    icon: 'text-success',
  },
  conclusion: {
    bg: 'bg-danger/10',
    border: 'border-l-danger',
    icon: 'text-danger',
  },
};
```

- [ ] **Step 3: Update PreferencePicker.tsx**

Replace:
- `bg-white rounded-lg border border-gray-200 p-4` → `bg-bg-card rounded-lg border border-border p-4`
- `text-gray-600` → `text-text-secondary`
- `text-gray-900` → `text-text-primary`
- `border-gray-100` → `border-border`
- `text-gray-700` → `text-text-secondary`
- `text-amber-500` → `text-warning`
- `bg-amber-50 text-amber-700` → `bg-warning/10 text-warning`
- `text-rose-500` → `text-danger`
- `bg-rose-50 text-rose-700` → `bg-danger/10 text-danger`
- `text-blue-500` → `text-accent-blue`
- `bg-blue-50 text-blue-700` → `bg-accent-blue/10 text-accent-blue`

- [ ] **Step 4: Commit**

```
git add frontend/src/components/messages/
git commit -m "feat: add dark mode support to LiturgicalCard, HomilyDisplay, PreferencePicker"
```

---

### Task 9: Update MessageRenderer

**Files:**
- Modify: `frontend/src/components/messages/MessageRenderer.tsx`

- [ ] **Step 1: Update the fallback text**

Replace:
```tsx
<p className="text-gray-500">Messaggio non riconosciuto</p>
```
With:
```tsx
<p className="text-text-tertiary">Messaggio non riconosciuto</p>
```

- [ ] **Step 2: Commit**

```
git add frontend/src/components/messages/MessageRenderer.tsx
git commit -m "refactor: update MessageRenderer fallback to use semantic token"
```

---

### Task 10: Add Dark Mode to Auth Pages

**Files:**
- Modify: `frontend/src/app/auth/layout.tsx`
- Modify: `frontend/src/app/auth/login/page.tsx`
- Modify: `frontend/src/app/auth/register/page.tsx`
- Modify: `frontend/src/app/chat/SignOutButton.tsx`

- [ ] **Step 1: Update auth/layout.tsx**

Replace:
```tsx
<div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-liturgy-50 via-white to-liturgy-100 py-12 px-4">
```
With:
```tsx
<div className="min-h-screen flex items-center justify-center bg-bg-canvas py-12 px-4">
```

Replace:
```tsx
<div className="text-3xl font-bold bg-gradient-to-r from-liturgy-700 to-violet-700 bg-clip-text text-transparent">
```
With:
```tsx
<div className="text-3xl font-bold text-text-primary">
```

Replace:
```tsx
<p className="mt-2 text-sm text-liturgy-600 font-medium">
```
With:
```tsx
<p className="mt-2 text-sm text-text-secondary font-medium">
```

- [ ] **Step 2: Update auth/login/page.tsx and auth/register/page.tsx**

Replace:
```tsx
<h1 className="text-2xl font-serif font-semibold text-gray-900">
```
With:
```tsx
<h1 className="text-2xl font-serif font-semibold text-text-primary">
```

Replace:
```tsx
<p className="text-liturgy-600 mt-1 text-sm">
```
With:
```tsx
<p className="text-text-secondary mt-1 text-sm">
```

Replace:
```tsx
<div className="bg-white rounded-2xl shadow-lg border border-liturgy-100 p-8">
```
With:
```tsx
<div className="bg-bg-card rounded-2xl shadow-subtle border border-border p-8">
```

Replace:
```tsx
<p className="text-center text-xs text-gray-400 mt-6">
```
With:
```tsx
<p className="text-center text-xs text-text-tertiary mt-6">
```

Replace link class:
```tsx
className="text-liturgy-600 hover:text-liturgy-700 font-medium"
```
With:
```tsx
className="text-accent-violet hover:text-accent-violet/80 font-medium"
```

- [ ] **Step 3: Update SignOutButton.tsx**

Replace:
```tsx
className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-500 hover:text-red-600 bg-white border border-gray-200 rounded-xl hover:border-red-200 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-400 transition-all"
```
With:
```tsx
className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-text-tertiary hover:text-danger bg-bg-card border border-border rounded-xl hover:border-danger/30 hover:bg-danger/10 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-danger/50 transition-all"
```

- [ ] **Step 4: Commit**

```
git add frontend/src/app/auth/ frontend/src/app/chat/SignOutButton.tsx
git commit -m "feat: add dark mode support to auth pages and sign out button"
```

---

### Task 11: Update Auth Forms

**Files:**
- Modify: `frontend/src/components/auth/LoginForm.tsx`
- Modify: `frontend/src/components/auth/RegisterForm.tsx`

- [ ] **Step 1: Update LoginForm.tsx**

Replace:
- `bg-red-50 border border-red-200 text-red-700` → `bg-danger/10 border border-danger/30 text-danger`
- `text-sm font-medium text-gray-700` → `text-sm font-medium text-text-secondary`
- `text-liturgy-400` (icon color) → `text-accent-violet` (keep brand accent)
- `border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-liturgy-300 focus:border-liturgy-400 disabled:bg-gray-100 text-gray-900` → `border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-accent-violet/30 focus:border-accent-violet disabled:bg-bg-overlay text-text-primary`
- `bg-gradient-to-r from-liturgy-600 to-violet-600 text-white py-2.5 px-4 rounded-xl hover:from-liturgy-700 hover:to-violet-700 disabled:from-gray-300 disabled:to-gray-300` → Keep gradient but use semantic tokens: `bg-accent-violet text-white py-2.5 px-4 rounded-xl hover:bg-accent-violet/90 disabled:bg-bg-overlay disabled:text-text-tertiary`

- [ ] **Step 2: Update RegisterForm.tsx**

Same pattern as LoginForm — apply identical class replacements.

- [ ] **Step 3: Commit**

```
git add frontend/src/components/auth/
git commit -m "feat: add dark mode support to auth forms"
```

---

### Task 12: Verify and Fix Build

- [ ] **Step 1: Run the build**

Run: `cd frontend && npm run build`

Expected: Success. If any classes are unknown (e.g., old `shadow-sm` → Tailwind v4 uses `shadow-xs`, or `rounded-xl` → v4 changes might need audit), fix them:

| Tailwind v3 class | Tailwind v4 equivalent |
|---|---|
| `shadow-sm` | `shadow-xs` |
| `shadow-md` | `shadow-sm` |
| `shadow-lg` | `shadow-md` |

Search for these patterns in the modified files and update if the build reports errors.

- [ ] **Step 2: Run lint**

Run: `cd frontend && npm run lint`

Expected: No errors or warnings.

- [ ] **Step 3: Run E2E tests**

Run: `cd frontend && npx playwright test e2e/dark-mode.spec.ts`

Expected: All 3 tests pass (toggle visible, toggle toggles class, class persists on reload).

- [ ] **Step 4: Commit fixes**

```
git commit -am "fix: build and lint fixes after Tailwind v4 upgrade"
```

---

### Task 13: Final Polish

- [ ] **Step 1: Visual audit checklist**

Open the app in both light and dark modes and verify:
- [ ] Chat page renders cleanly in light mode (warm palette)
- [ ] Chat page renders cleanly in dark mode (black canvas, white text, #292d30 borders)
- [ ] Theme toggle works and persists
- [ ] Auth pages (login, register) render in both themes
- [ ] Liturgical card renders in both themes
- [ ] Homily display renders in both themes
- [ ] Preference picker renders in both themes
- [ ] Tool calls render in both themes
- [ ] Input area renders in both themes
- [ ] Sign out button renders in both themes
- [ ] All borders are 1px solid #292d30 in dark mode
- [ ] No text is hardcoded gray in dark mode (should be #f0f0f0 or #a1a4a5)
- [ ] Chat bubbles have proper contrast in dark mode

- [ ] **Step 2: Fix any visual issues found**

- [ ] **Step 3: Commit final polish**

```
git commit -am "fix: visual polish after Resend design system adoption"
```
