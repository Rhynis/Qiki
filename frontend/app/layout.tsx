import type { Metadata } from 'next'
import { NextIntlClientProvider } from 'next-intl'
import { getLocale } from 'next-intl/server'
import { Toaster } from 'sonner'
import { ChatWidget } from '@/components/chat/chat-widget'
import { Providers } from '@/components/providers'
import { DemoModeBanner } from '@/components/shared/demo-mode-banner'
import { FloatingContact } from '@/components/shared/floating-contact'
import { Footer } from '@/components/shared/footer'
import { Header } from '@/components/shared/header'
import './globals.css'

export const metadata: Metadata = {
  title: 'Gas Quốc Cường',
  description: 'Mua gas LPG an toàn tại Bình Thạnh và Thủ Đức',
  openGraph: {
    title: 'Gas Quốc Cường',
    description: 'Mua gas LPG an toàn tại Bình Thạnh và Thủ Đức',
    locale: 'vi_VN',
    type: 'website',
  },
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale()
  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider>
          <Providers>
            <div className="min-h-screen bg-slate-50">
              <DemoModeBanner />
              <Header />
              <main>{children}</main>
              <Footer />
              <FloatingContact />
              <ChatWidget />
            </div>
            <Toaster richColors position="top-right" offset="80px" />
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
