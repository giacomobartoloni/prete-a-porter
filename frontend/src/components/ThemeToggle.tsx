'use client'

import { useTheme } from 'next-themes'
import { Sun, Moon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { cn } from '@/lib/utils'

interface ThemeToggleProps {
  showLabel?: boolean
}

export function ThemeToggle({ showLabel = false }: ThemeToggleProps) {
  const { theme, resolvedTheme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  const t = useTranslations('sidebar')

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
      aria-label={t('theme')}
    >
      {isDark ? (
        <Sun className="w-5 h-5 shrink-0" />
      ) : (
        <Moon className="w-5 h-5 shrink-0" />
      )}
      {showLabel && (
        <span className="text-sm whitespace-nowrap">{t('theme')}</span>
      )}
    </button>
  )
}
