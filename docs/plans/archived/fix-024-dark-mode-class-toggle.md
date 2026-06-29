# Fix 024: Attivare Dark Mode (darkMode: 'class' + Toggle)

**Finding**: Dark mode classes compilano ma non si attivano mai.
**File**: `frontend/tailwind.config.ts`
**Severità**: Important
**Stato**: Da fare

---

## Descrizione

`tailwind.config.ts` non ha la proprietà `darkMode`. Tutti i `dark:` variant (65+
occorrenze in 5 componenti) sono **codice morto** — compilano ma restano inattivi.

Non esiste alcun meccanismo di attivazione: nessun toggle, nessuna libreria
tema (`next-themes` assente), nessuno script che aggiunge `class="dark"` all'HTML.

## Obiettivo

Aggiungere `darkMode: 'class'` a Tailwind e implementare un dark mode toggle
funzionante con persistenza e supporto alla preferenza OS.

---

## Piano di esecuzione

### Step 1: Aggiungere `darkMode: 'class'` a `tailwind.config.ts`

**File**: `frontend/tailwind.config.ts`

Aggiungere subito dopo `content: [...]`:

```ts
darkMode: 'class',
```

### Step 2: Installare `next-themes`

```bash
npm install next-themes
```

Motivo: libreria standard per Next.js App Router. Gestisce:
- Attributo `class` sull'HTML
- Persistenza in `localStorage`
- Rilevamento preferenza OS (`system`)
- FOUC prevention via `suppressHydrationWarning`

### Step 3: Creare `ThemeProvider` wrapper

**Nuovo file**: `frontend/src/components/providers/ThemeProvider.tsx`

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

Aggiornare `frontend/src/components/providers/index.ts` per esportare `ThemeProvider`.

### Step 4: Aggiornare root `layout.tsx`

**File**: `frontend/src/app/layout.tsx`

- Aggiungere `suppressHydrationWarning` all'elemento `<html>` (richiesto per SSR
  con next-themes — evita mismatch di attributi durante idratazione)
- Aggiungere classi per lo sfondo scuro globale al `<body>`:
  `dark:bg-slate-950 dark:text-slate-100`
- Wrappare `{children}` con `<ThemeProvider>`

```tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
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

### Step 5: Creare `ThemeToggle` component

**Nuovo file**: `frontend/src/components/ThemeToggle.tsx`

Client component che usa `useTheme` di next-themes:

```tsx
'use client'

import { useTheme } from 'next-themes'
import { Sun, Moon } from 'lucide-react'
import { useEffect, useState } from 'react'

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  useEffect(() => setMounted(true), [])

  if (!mounted) {
    return <div className="w-9 h-9" /> // placeholder per evitare layout shift
  }

  return (
    <button
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
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

### Step 6: Inserire toggle nel layout chat

**File**: `frontend/src/app/chat/page.tsx`

Importare `ThemeToggle` e aggiungerlo nell'header, accanto a `SignOutButton`:

```tsx
<ThemeToggle />
<SignOutButton />
```

Posizionamento: il toggle va prima del SignOutButton (o dopo, a seconda del
design). Entrambi sono client component, nessun problema di SSR.

### Step 7: Verifica

```bash
cd frontend
npm run lint
npm run build
```

Test manuale:
1. Cliccare il toggle — l'attributo `class="dark"` deve apparire su `<html>`
2. Verificare che le `dark:` variant si attivino visivamente
3. Ricaricare la pagina — la preferenza deve persistere
4. Testare con preferenza OS "dark" (se `defaultTheme="system"`)

---

## Note

- **Nessun componente esistente da modificare**: i 5 componenti (`ChatContainer`, `MessageList`, `MessageBubble`, `InputArea`, `ToolCall`) hanno già tutte le classi `dark:` necessarie.
- **next-themes** è la scelta standard per Next.js App Router. Alternativa: implementare manualmente con `useEffect` e `localStorage`, ma `next-themes` gestisce già edge case (FOUC, SSR hydration mismatch, system preference listener).
- Il `disableTransitionOnChange` su ThemeProvider evita transizioni CSS indesiderate durante il cambio tema.

## Dipendenze da aggiungere

- `next-themes` (runtime)

## Checklist

- [ ] Step 1: `darkMode: 'class'` in tailwind.config.ts
- [ ] Step 2: `npm install next-themes`
- [ ] Step 3: ThemeProvider wrapper
- [ ] Step 4: Layout con `suppressHydrationWarning` + body dark classi
- [ ] Step 5: ThemeToggle component
- [ ] Step 6: Toggle nel header chat
- [ ] Step 7: Lint + build + test manuale
