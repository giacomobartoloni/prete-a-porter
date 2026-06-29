'use client'

import { useLocale } from 'next-intl'
import { useTransition } from 'react'
import { setUserLocale } from '@/lib/locale'
import { useTranslations } from 'next-intl'
import { Languages } from 'lucide-react'

export function LocaleToggle() {
  const locale = useLocale()
  const t = useTranslations('locale')
  const [isPending, startTransition] = useTransition()
  const nextLocale = locale === 'it' ? 'en' : 'it'

  return (
    <button
      onClick={() => startTransition(() => setUserLocale(nextLocale))}
      disabled={isPending}
      className="flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors hover:bg-bg-overlay text-text-tertiary w-full"
      aria-label={t('switch_to')}
    >
      <Languages className="w-5 h-5 shrink-0" />
      <span className="text-sm whitespace-nowrap">{nextLocale.toUpperCase()}</span>
    </button>
  )
}
