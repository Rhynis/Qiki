import type { Metadata } from 'next'
import { Toaster } from 'sonner'
import { ChatWidget } from '@/components/chat/chat-widget'
import { Providers } from '@/components/providers'
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>
        <Providers>
          <div className="min-h-screen bg-slate-50">
            <Header />
            <main>{children}</main>
            <Footer />
            <FloatingContact />
            <ChatWidget />
          </div>
          <Toaster richColors position="top-right" />
        </Providers>
      </body>
    </html>
  )
}
