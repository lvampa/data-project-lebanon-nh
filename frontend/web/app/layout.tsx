import type { Metadata, Viewport } from 'next'
import localFont from 'next/font/local'
import './globals.css'
import { SiteHeader } from '@project/ui/components/site/site-header'
import { SiteFooter } from '@project/ui/components/site/site-footer'

const plexSans = localFont({
  src: [
    { path: './fonts/ibm-plex-sans-latin-400-normal.woff2', weight: '400' },
    { path: './fonts/ibm-plex-sans-latin-500-normal.woff2', weight: '500' },
    { path: './fonts/ibm-plex-sans-latin-600-normal.woff2', weight: '600' },
    { path: './fonts/ibm-plex-sans-latin-700-normal.woff2', weight: '700' },
  ],
  variable: '--font-sans',
})

const plexMono = localFont({
  src: [
    { path: './fonts/ibm-plex-mono-latin-400-normal.woff2', weight: '400' },
    { path: './fonts/ibm-plex-mono-latin-500-normal.woff2', weight: '500' },
  ],
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
