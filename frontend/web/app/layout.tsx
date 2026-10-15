import type { Metadata, Viewport } from 'next'
import { IBM_Plex_Mono, IBM_Plex_Sans } from 'next/font/google'
import './globals.css'
import { SiteHeader } from '@project/ui/components/site/site-header'
import { SiteFooter } from '@project/ui/components/site/site-footer'

const plexSans = IBM_Plex_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-sans',
})

const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
})

export const metadata: Metadata = {
  title: 'Lebanon Data Project',
  description: 'Police incidents, properties, and city staff for Lebanon, NH',
  icons: {
    icon: [
      { url: '/favicon.ico', sizes: '48x48' },
      { url: '/favicon.svg', type: 'image/svg+xml' },
    ],
    apple: '/apple-touch-icon.png',
  },
  manifest: '/site.webmanifest',
}

export const viewport: Viewport = {
  themeColor: '#14233c',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body
        className={`${plexSans.variable} ${plexMono.variable} ${plexSans.className} flex min-h-dvh flex-col`}
      >
        <SiteHeader />
        <main className="max-w-7xl w-full mx-auto px-4 py-6 flex-1">{children}</main>
        <SiteFooter />
      </body>
    </html>
  )
}
