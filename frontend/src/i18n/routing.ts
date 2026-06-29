import { defineRouting } from 'next-intl/routing'

export const routing = defineRouting({
  locales: ['it', 'en'],
  defaultLocale: 'it',
  localePrefix: 'never',
  localeDetection: true,
  localeCookie: {
    name: 'NEXT_LOCALE',
    maxAge: 60 * 60 * 24 * 365,
    partitioned: false,
  },
})
