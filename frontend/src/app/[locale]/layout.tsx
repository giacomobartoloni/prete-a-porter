import { NextIntlClientProvider } from 'next-intl'
import { getMessages, getTranslations } from 'next-intl/server'
import '../globals.css'
import { SessionProvider, ThemeProvider } from '@/components/providers'
import Script from 'next/script'

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
      <script
        dangerouslySetInnerHTML={{
          __html:
            'window.sa_event=window.sa_event||function(){var a=[].slice.call(arguments);window.sa_event.q?window.sa_event.q.push(a):window.sa_event.q=[a]};',
        }}
      />
      <body className="font-sans">
        <NextIntlClientProvider messages={messages}>
          <SessionProvider>
            <ThemeProvider>{children}</ThemeProvider>
          </SessionProvider>
        </NextIntlClientProvider>
      </body>
      <Script
        src="https://scripts.simpleanalyticscdn.com/latest.js"
        strategy="afterInteractive"
      />
    </html>
  )
}
