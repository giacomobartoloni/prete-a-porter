# Frontend i18n Design

## Overview

Internationalizzare il frontend Next.js a supporto di italiano e inglese usando
`next-intl` (v4.8.3, già installato) con locale persistito via cookie, nessun
prefisso nella URL, e rilevamento automatico della lingua del browser al primo
accesso.

## Requirements

| # | Requisito | Accettazione |
|---|-----------|-------------|
| R1 | Tutte le stringhe UI in italiano sono spostate in file di traduzione | Zero stringhe hardcoded nei componenti |
| R2 | File traduzioni inglese (`en.json`) presenti e completi | Ogni chiave in `it.json` ha corrispondente in `en.json` |
| R3 | Locale rilevato automaticamente dall'`Accept-Language` del browser al primo accesso | Utente con browser in inglese vede UI inglese senza azioni manuali |
| R4 | Locale persiste via cookie tra sessioni | Dopo il primo accesso, il locale scelto rimane |
| R5 | Locale NON appare nella URL | `/chat` e non `/en/chat` o `/it/chat` |
| R6 | Utente può cambiare lingua manualmente | Selettore lingua nell'interfaccia |
| R7 | Date e numeri formattati secondo il locale corrente | `it-IT` per italiano, `en-US` per inglese |
| R8 | next-intl middleware composto con NextAuth middleware senza conflitti | Entrambi funzionano, auth non aggirabile via cambio lingua |
| R9 | Namespace annidati per organizzazione messaggi | `auth.login.title`, `liturgy.first_reading`, ecc. |
| R10 | Default locale: `it` | Se Accept-Language non contiene `it` o `en`, si usa `it` |

## Current State

- `next-intl` v4.8.3 installato in `package.json` ma **mai configurato**
- Tutte le stringhe UI sono hardcoded in italiano (~20 componenti)
- Mix incoerente: alcune pagine auth usano inglese
- `next.config.js` vuoto
- `layout.tsx` con `lang="it"` hardcoded
- `middleware.ts` contiene solo NextAuth, nessun routing i18n
- Nessun file di traduzione presente

### Stringhe hardcoded per componente

| Componente | File | # Stringhe |
|-----------|------|-----------|
| RootLayout | `layout.tsx` | 2 (title, description) |
| AuthLayout | `auth/layout.tsx` | 1 |
| LoginPage | `auth/login/page.tsx` | 5 |
| RegisterPage | `auth/register/page.tsx` | 6 |
| AuthError | `auth/error/page.tsx` | 4 (in inglese) |
| Chat | `Chat.tsx` | 6 |
| Sidebar | `Sidebar.tsx` | 6 |
| LoginForm | `auth/LoginForm.tsx` | 6 |
| RegisterForm | `auth/RegisterForm.tsx` | 8 |
| LogoutButton | `auth/LogoutButton.tsx` | 2 (in inglese) |
| InputArea | `chat/InputArea.tsx` | 1 |
| MessageList | `chat/MessageList.tsx` | 2 |
| ToolCall | `chat/ToolCall.tsx` | 4 |
| HomilyDisplay | `messages/HomilyDisplay.tsx` | 3 |
| LiturgicalCard | `messages/LiturgicalCard.tsx` | 8 |
| PreferencePicker | `messages/PreferencePicker.tsx` | 12 |
| MessageRenderer | `messages/MessageRenderer.tsx` | 1 |
| ThemeToggle | `ThemeToggle.tsx` | 1 |
| SignOutButton | `SignOutButton.tsx` | 1 |
| Prisma schema | `schema.prisma` | 1 (default title) |

## Target Architecture

### Nuovi file

```
frontend/
  src/
    i18n/
      routing.ts          # defineRouting — configurazione routing
      request.ts          # getRequestConfig — messaggi + locale detection
    messages/
      it.json             # Traduzioni italiano (da hardcoded esistente)
      en.json             # Traduzioni inglese
components/
  LocaleToggle.tsx       # Selettore lingua (client component)
```

### File modificati

| File | Modifica |
|------|----------|
| `next.config.js` | Aggiungere `createNextIntlPlugin()` |
| `middleware.ts` | Comporre `createMiddleware(routing)` + `auth()` |
| `layout.tsx` | Ricevere locale, `NextIntlClientProvider`, messages |
| `app/page.tsx` | Redirect localizzato |
| `app/chat/page.tsx` | `getTranslations()` |
| `app/auth/*/page.tsx` | `getTranslations()` |
| `app/auth/layout.tsx` | `getTranslations()` |
| `app/error/page.tsx` | `getTranslations()` |
| `components/Chat.tsx` | `useTranslations()` |
| `components/Sidebar.tsx` | `useTranslations()` |
| `components/auth/*.tsx` | `useTranslations()` |
| `components/chat/*.tsx` | `useTranslations()` |
| `components/messages/*.tsx` | `useTranslations()` |
| `components/ThemeToggle.tsx` | `useTranslations()` |
| `components/providers/index.ts` | Aggiungere `NextIntlClientProvider` |

### Struttura rotte (nessuna modifica visibile)

```
/               → redirect a /chat o /auth/login
/chat           → [locale]/chat/page.tsx (rewrite interno)
/auth/login     → [locale]/auth/login/page.tsx (rewrite interno)
/auth/register  → [locale]/auth/register/page.tsx
/auth/error     → [locale]/auth/error/page.tsx
/api/*          → escluso dal middleware i18n
```

Le pagine vengono spostate sotto `src/app/[locale]/` ma la URL utente
rimane invariata grazie a `localePrefix: 'never'`.

## Configurazione

### 1. Routing (`src/i18n/routing.ts`)

```typescript
import { defineRouting } from 'next-intl/routing'

export const routing = defineRouting({
  locales: ['it', 'en'],
  defaultLocale: 'it',
  localePrefix: 'never',
  localeDetection: true,
  localeCookie: {
    name: 'NEXT_LOCALE',
    maxAge: 60 * 60 * 24 * 365,
  },
})
```

| Proprietà | Valore | Effetto |
|-----------|--------|---------|
| `locales` | `['it', 'en']` | Lingue supportate |
| `defaultLocale` | `'it'` | Fallback |
| `localePrefix` | `'never'` | Nessun prefisso nella URL |
| `localeDetection` | `true` | Accept-Language + cookie |
| `localeCookie.maxAge` | 1 anno | Persistenza跨-sessione |

### 2. Request (`src/i18n/request.ts`)

```typescript
import { getRequestConfig } from 'next-intl/server'
import { hasLocale } from 'next-intl'
import { routing } from './routing'

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale
  const locale = hasLocale(routing.locales, requested)
    ? requested
    : routing.defaultLocale

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  }
})
```

`requestLocale` viene popolato automaticamente da next-intl middleware
con il risultato della negoziazione (Accept-Language → cookie → default).

### 3. Plugin (`next.config.js`)

```javascript
const createNextIntlPlugin = require('next-intl/plugin')

const withNextIntl = createNextIntlPlugin()

/** @type {import('next').NextConfig} */
const nextConfig = {}

module.exports = withNextIntl(nextConfig)
```

### 4. Layout (`src/app/[locale]/layout.tsx`)

```typescript
import { NextIntlClientProvider } from 'next-intl'
import { getMessages, getTranslations } from 'next-intl/server'

export async function generateMetadata() {
  const t = await getTranslations('common')
  return {
    title: t('app_title'),
    description: t('app_description'),
  }
}

export default async function LocaleLayout({
  children,
  params: { locale },
}: {
  children: React.ReactNode
  params: { locale: string }
}) {
  const messages = await getMessages()

  return (
    <html lang={locale} suppressHydrationWarning>
      <body className="font-sans">
        <NextIntlClientProvider messages={messages}>
          <SessionProvider>
            <ThemeProvider>{children}</ThemeProvider>
          </SessionProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
```

### 5. Middleware (`src/middleware.ts`)

```typescript
import { auth } from '@/lib/auth'
import createMiddleware from 'next-intl/middleware'
import { routing } from './i18n/routing'
import { NextRequest, NextResponse } from 'next/server'

const handleI18n = createMiddleware(routing)

export default auth(async (req: NextRequest) => {
  const { pathname } = req.nextUrl

  // Escludi API routes dal routing i18n
  if (pathname.startsWith('/api/')) {
    return NextResponse.next()
  }

  // Esegue routing i18n (locale detection, cookie, rewrite)
  return handleI18n(req)
})

export const config = {
  matcher: '/((?!api|trpc|_next|_vervex|.*\\..*).*)',
}
```

**Come funziona la composizione:**
1. `auth()` NextAuth v5 intercetta la request, aggiunge `req.auth`
2. Se l'utente non è autenticato su route protetta, NextAuth reindirizza a `/auth/login` (prima che i18n tocchi la request)
3. Se autenticato, passa a `handleI18n()` che fa rewrite interno a `/[locale]/...`
4. next-intl non sovrascrive `req.auth` — nessun conflitto
5. Le route API (`/api/*`) sono escluse dal matcher

**Locale detection flow (middleware):**
1. Cookie `NEXT_LOCALE` presente? → usa quel valore
2. No cookie? → legge `Accept-Language` header
3. Nessun match? → `defaultLocale: 'it'`
4. Il middleware fa rewrite della request a `/[locale]/path` internamente
5. `request.ts` riceve `requestLocale` dal rewrite e carica i messaggi giusti

### 6. Struttura messaggi

#### `messages/it.json`

```json
{
  "common": {
    "app_title": "Prete-a-porter",
    "app_description": "Il ghostwriter per un'omelia perfetta"
  },
  "auth": {
    "login": {
      "title": "Bentornato",
      "subtitle": "Accedi per preparare la tua omelia",
      "email_placeholder": "Email",
      "password_placeholder": "Password",
      "submit": "Accedi",
      "loading": "Accesso in corso...",
      "no_account": "Non hai un account?",
      "register_link": "Registrati"
    },
    "register": {
      "title": "Crea Account",
      "subtitle": "Registrati per iniziare",
      "name_placeholder": "Nome",
      "email_placeholder": "Email",
      "password_placeholder": "Password",
      "submit": "Crea Account",
      "loading": "Creazione account...",
      "has_account": "Hai già un account?",
      "login_link": "Accedi"
    },
    "error": {
      "title": "Errore di Autenticazione",
      "description": "Si è verificato un errore durante l'autenticazione.",
      "back": "Torna al login",
      "try_again": "Riprova"
    },
    "logout": {
      "button": "Esci",
      "signing_out": "Uscita in corso..."
    }
  },
  "chat": {
    "input_placeholder": "Scrivi il tuo messaggio...",
    "start_conversation": "Inizia una conversazione...",
    "generating": "Sto generando...",
    "connected": "Connesso",
    "disconnected": "Disconnesso",
    "today_readings": "Letture di oggi",
    "sunday_homily": "Omelia per domenica",
    "wedding_readings": "Letture nozze"
  },
  "sidebar": {
    "new_conversation": "Nuova conversazione",
    "today": "Oggi",
    "yesterday": "Ieri",
    "no_conversations": "Nessuna conversazione",
    "theme": "Tema",
    "logout": "Esci",
    "collapse": "Collassa sidebar",
    "expand": "Espandi sidebar",
    "delete_conversation": "Elimina conversazione",
    "default_title": "Nuova conversazione"
  },
  "liturgy": {
    "title": "Letture del Giorno",
    "first_reading": "Prima Lettura",
    "psalm": "Salmo",
    "second_reading": "Seconda Lettura",
    "gospel": "Vangelo",
    "alleluia": "Alleluia",
    "season": {
      "advent": "Avvento",
      "christmas": "Natale",
      "lent": "Quaresima",
      "easter": "Pasqua",
      "ordinary": "Tempo Ordinario"
    },
    "color": {
      "green": "Verde",
      "purple": "Viola",
      "white": "Bianco",
      "red": "Rosso",
      "rose": "Rosa"
    }
  },
  "homily": {
    "title": "Omelia Generata",
    "preferences": "Preferenze Omelia",
    "target_audience": "Destinatari",
    "tone": "Tono",
    "length": "Durata",
    "themes": "Temi",
    "metaphors": "Metafore",
    "parables": "Parabole",
    "occasion": {
      "mass": "Messa",
      "marriage": "Matrimonio",
      "baptism": "Battesimo",
      "funeral": "Funerale"
    },
    "audience": {
      "adults": "Adulti",
      "youth": "Giovani",
      "children": "Bambini",
      "mixed": "Misto"
    },
    "tone_options": {
      "formal": "Formale",
      "conversational": "Conversazionale",
      "poetic": "Poetico",
      "consolatory": "Consolatorio",
      "celebratory": "Celebrativo"
    },
    "length_options": {
      "short": "Breve (5-7 min)",
      "medium": "Media (10-12 min)",
      "long": "Lunga (15+ min)"
    }
  },
  "tool_call": {
    "pending": "In attesa",
    "running": "In esecuzione",
    "completed": "Completato",
    "error": "Errore"
  },
  "locale": {
    "switch_to": "Switch to English",
    "current": "Italiano"
  },
  "messages": {
    "unknown_type": "Messaggio non riconosciuto"
  }
}
```

#### `messages/en.json`

Struttura identica, valori in inglese.

### 7. Componente cambio lingua (`components/LocaleToggle.tsx`)

```typescript
'use client'

import { useLocale } from 'next-intl'
import { setUserLocale } from '@/lib/locale'
import { useTransition } from 'react'

export function LocaleToggle() {
  const locale = useLocale()
  const [isPending, startTransition] = useTransition()
  const nextLocale = locale === 'it' ? 'en' : 'it'

  return (
    <button
      onClick={() => startTransition(() => setUserLocale(nextLocale))}
      disabled={isPending}
      aria-label={nextLocale === 'en' ? 'Switch to English' : 'Passa all\'italiano'}
    >
      {nextLocale.toUpperCase()}
    </button>
  )
}
```

Dove `setUserLocale` imposta il cookie `NEXT_LOCALE` e ricarica la pagina:

```typescript
// src/lib/locale.ts
'use server'

import { cookies } from 'next/headers'

export async function setUserLocale(locale: string) {
  const cookieStore = await cookies()
  cookieStore.set('NEXT_LOCALE', locale, {
    maxAge: 60 * 60 * 24 * 365,
    path: '/',
  })
}
```

In alternativa, se si vuole evitare il ricaricamento della pagina, si può
usare `useRouter` di next-intl con `router.refresh()`, ma per semplicità
iniziale il cookie + refresh è più robusto.

### 8. Pattern di migrazione componenti

#### Server Component

```typescript
// Prima
export const metadata = {
  title: 'Prete-a-porter',
  description: "Il ghostwriter per un'omelia perfetta",
}

// Dopo
import { getTranslations } from 'next-intl/server'

export async function generateMetadata() {
  const t = await getTranslations('common')
  return {
    title: t('app_title'),
    description: t('app_description'),
  }
}
```

#### Client Component

```typescript
// Prima
<button>{'Accedi'}</button>

// Dopo
import { useTranslations } from 'next-intl'
// ...
const t = useTranslations('auth.login')
<button>{t('submit')}</button>
```

### 9. Formattazione date

Sostituire hardcoded `it-IT` con il locale corrente:

```typescript
// Prima
new Date(date).toLocaleDateString('it-IT', { ... })

// Dopo
import { useLocale } from 'next-intl'
// ...
const locale = useLocale()
new Date(date).toLocaleDateString(locale === 'it' ? 'it-IT' : 'en-US', { ... })
```

## Ordine di implementazione

| Fase | Task | Dipende da |
|------|------|-----------|
| 1 | Creare `src/i18n/routing.ts` | — |
| 2 | Creare `src/i18n/request.ts` | routing.ts |
| 3 | Aggiornare `next.config.js` | — |
| 4 | Creare `messages/it.json` | — |
| 5 | Creare `messages/en.json` | — |
| 6 | Spostare pagine sotto `src/app/[locale]/` | — |
| 7 | Aggiornare `middleware.ts` (composizione) | routing.ts |
| 8 | Aggiornare `layout.tsx` → `[locale]/layout.tsx` | request.ts, messages |
| 9 | Migrare componenti stringa per stringa | messages, layout |
| 10 | Aggiungere `LocaleToggle` | — |
| 11 | Type safety: `createMessagesDeclaration` | messages |
| 12 | Test: cambio lingua, persistenza, auth flow | Tutto |

## Edge Cases

| Caso | Comportamento |
|------|-------------|
| Primo accesso, browser in inglese | `Accept-Language: en` → locale `en`, cookie impostato |
| Primo accesso, browser in tedesco | `Accept-Language: de` → nessun match → fallback `it` |
| Cookie scaduto | Come primo accesso (Accept-Language) |
| Cookie corrotto | `hasLocale` fallisce → fallback `it` |
| API routes | Escluse dal matcher middleware i18n |
| 404 page | Mostrata nella lingua corrente |
| Cambio lingua rapido | `useTransition` previene click multipli |
| Nessun messaggio per chiave | next-intl lancia errore in dev, fallback a chiave in prod |
| Static Generation | Cookie-based locale impedisce SSG completo (dynamic rendering) |

## Trade-offs

| Decisione | Pro | Contro |
|-----------|-----|--------|
| `localePrefix: 'never'` | URL pulite, nessun impatto SEO | Le pagine non sono prefissate per locale — SSG impossibile, tutto dynamic |
| next-intl middleware | Locale detection automatica, nessun boilerplate | Un middleware in più da comporre con NextAuth |
| Cookie persistente | L'utente non perde la scelta | Richiede cookie, potrebbe essere bloccato in ambienti restrittivi |
| `Accept-Language` al primo accesso | Zero configurazione utente | La prima richiesta è leggermente più lenta (middleware) |

## Test Plan

| Test | Cosa verificare | Strumento |
|------|----------------|-----------|
| Cambio lingua | Click toggle → UI in inglese, ricarica → persiste | Manuale |
| Primo accesso (browser EN) | UI in inglese senza azione manuale | Playwright + `page.setExtraHTTPHeaders` |
| Primo accesso (browser IT) | UI in italiano | Playwright |
| Auth flow con cambio lingua | Login in italiano, poi cambio → chat in inglese | Playwright |
| Date formatting | Formato `it-IT` con italiano, `en-US` con inglese | Unit test |
| Fallback lingua non supportata | Browser con `Accept-Language: fr` → UI in italiano | Playwright |
| next-intl locale switch | `setUserLocale` + refresh → pagina nella lingua corretta | Manuale |
