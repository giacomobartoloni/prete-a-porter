import { NextIntlClientProvider } from 'next-intl'
import { getMessages, getTranslations } from 'next-intl/server'
import '../globals.css'
import { SessionProvider, ThemeProvider } from '@/components/providers'

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
