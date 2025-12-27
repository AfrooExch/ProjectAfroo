import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import '@/styles/globals.css'
import { AuthProvider } from '@/contexts/AuthContext'
import TransitionProvider from '@/components/TransitionProvider'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Afroo Exchange',
  description: 'Trade cryptocurrencies securely with trusted exchangers. BTC, ETH, SOL, USDT, and more.',
  keywords: 'cryptocurrency, exchange, trading, BTC, ETH, SOL, USDT, secure',
  icons: {
    icon: '/favicon.ico',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <AuthProvider>
          <TransitionProvider>
            {children}
          </TransitionProvider>
        </AuthProvider>
      </body>
    </html>
  )
}
