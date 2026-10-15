import type { Metadata } from 'next'
import localFont from 'next/font/local'
import './globals.css'
import { Sidebar } from '@/components/sidebar'

const inter = localFont({
  src: './fonts/inter-latin-wght-normal.woff2',
  weight: '100 900',
  variable: '--font-sans',
})

const sourceSerif = localFont({
  src: [
    { path: './fonts/source-serif-4-latin-400-normal.woff2', weight: '400', style: 'normal' },
    { path: './fonts/source-serif-4-latin-400-italic.woff2', weight: '400', style: 'italic' },
    { path: './fonts/source-serif-4-latin-500-normal.woff2', weight: '500', style: 'normal' },
    { path: './fonts/source-serif-4-latin-500-italic.woff2', weight: '500', style: 'italic' },
  ],
  variable: '--font-display',
})

export const metadata: Metadata = {
  title: 'Lebanon NH — Admin',
  description: 'Internal admin dashboard',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${sourceSerif.variable} ${inter.className} flex h-screen overflow-hidden bg-background`}>
        <Sidebar />
        <main className="flex flex-1 flex-col min-w-0 overflow-auto">
          <div className="flex-1 px-6 py-6">
            {children}
          </div>
        </main>
      </body>
    </html>
  )
}
